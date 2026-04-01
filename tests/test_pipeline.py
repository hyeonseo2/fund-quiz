from __future__ import annotations

import json
import zipfile
from pathlib import Path

from app.agents.extract_facts import extract_facts_from_blocks
from app.agents.generate_quiz import generate_quiz
from app.services.document_parser import parse_document_files
from app.services.quiz_pipeline import process_disclosure_pipeline
from app.db.models import Disclosure, Quiz, QuizQuestion
from app.db import models
from app.normalizers.report_name import normalize_report_name


def _make_zip_bytes(rcept_no: str, html: str) -> bytes:
    import io

    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w") as zf:
        zf.writestr("index.html", html)
    return bio.getvalue()


def _create_disclosure(session, payload):
    disc = Disclosure(
        rcept_no=payload["rcept_no"],
        corp_code="001",
        corp_name="테스트운용사",
        report_nm_raw=payload["report_nm"],
        normalized_document_family=normalize_report_name(payload["report_nm"]).family,
        rcept_dt=__import__("datetime").datetime.strptime(payload["rcept_dt"], "%Y%m%d").date(),
        status="listed",
        raw_payload=payload,
    )
    session.add(disc)
    session.flush()
    return disc


def test_report_name_classification() -> None:
    assert normalize_report_name("투자설명서(집합투자증권)").is_candidate is True
    assert normalize_report_name("[기재정정] 일괄신고서(집합투자증권-신탁형)").is_candidate is True
    assert normalize_report_name("효력발생안내(집합투자증권)").is_candidate is False


def test_parsing_and_fact_extraction_has_spans_for_fixture_r1() -> None:
    payload = json.loads(Path("tests/fixtures/r1.json").read_text())
    blocks = parse_document_files([("index.html", payload["doc_text"])])
    facts = extract_facts_from_blocks(1, blocks)
    assert any(f.source_span_ids for f in facts.facts)
    quiz = generate_quiz(facts)
    assert 1 <= len(quiz.questions) <= 5


def test_pipeline_with_three_sample_rcept_no(session, tmp_path, monkeypatch) -> None:
    # 3 fixtures = min sample requirement
    fixture_files = ["tests/fixtures/r1.json", "tests/fixtures/r2.json", "tests/fixtures/r3.json"]
    payloads = [json.loads(Path(fp).read_text()) for fp in fixture_files]

    for payload in payloads:
        _create_disclosure(session, payload)

    class FakeClient:
        def download_document_zip(self, rcept_no: str) -> bytes:
            p = {x["rcept_no"]: x for x in payloads}[rcept_no]
            return _make_zip_bytes(rcept_no, p["doc_text"])

    settings = __import__("app.core.config", fromlist=["Settings"]).Settings(STORAGE_ROOT=str(tmp_path / "storage"))
    from app.services.quiz_pipeline import process_disclosure_pipeline

    from app.core.config import Settings as _S
    cfg = _S(STORAGE_ROOT=str(tmp_path / "storage"))
    client = FakeClient()

    discs = session.query(models.Disclosure).all()
    assert len(discs) == 3
    for d in discs:
        ok, reason = process_disclosure_pipeline(session, cfg, client, d.id)
        assert ok, reason

        q = session.query(Quiz).filter_by(disclosure_id=d.id).first()
        assert q is not None
        qs = session.query(QuizQuestion).filter_by(quiz_id=q.id).all()
        assert 1 <= len(qs) <= 5
        for item in qs:
            assert item.source_span_ids
