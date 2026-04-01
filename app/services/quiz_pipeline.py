from __future__ import annotations

import hashlib
from pathlib import Path
from datetime import datetime
from zipfile import BadZipFile

from sqlalchemy.orm import Session

from app.agents.extract_facts import extract_facts_from_blocks
from app.agents.generate_quiz import generate_quiz
from app.agents.verify_quiz import verify_quiz
from app.clients.dart_client import DartClient
from app.db import models
from app.db.models import NormalizedFact, Quiz, QuizQuestion, DocumentBlock, Disclosure
from app.normalizers.report_name import normalize_report_name
from app.parsers.zip_loader import extract_zip
from app.services.document_parser import parse_document_files, ParsedBlockPayload
from app.core.config import Settings


def sync_disclosures_for_corp(session: Session, client: DartClient, corp_code: str, bgn_de: str, end_de: str, max_items: int | None = None) -> list[models.Disclosure]:
    items = client.fetch_list_json(corp_code=corp_code, bgn_de=bgn_de, end_de=end_de, page_count=100)
    out = []
    for it in items:
        if max_items is not None and len(out) >= max_items:
            break
        cls = normalize_report_name(it.report_nm)
        if not cls.is_candidate:
            continue

        existing = session.query(models.Disclosure).filter_by(rcept_no=it.rcept_no).one_or_none()
        if existing:
            continue

        disclosure = models.Disclosure(
            rcept_no=it.rcept_no,
            corp_code=it.corp_code,
            corp_name=it.corp_name,
            report_nm_raw=it.report_nm,
            normalized_document_family=cls.family,
            correction_type=cls.correction_type,
            pblntf_ty=it.pblntf_ty,
            pblntf_detail_ty=it.pblntf_detail_ty,
            rcept_dt=datetime.strptime(it.rcept_dt, "%Y%m%d").date(),
            flr_nm=it.flr_nm,
            is_latest=True,
            status="listed",
            raw_payload=it.__dict__,
        )
        session.add(disclosure)
        out.append(disclosure)
    return out


def _write_and_parse_blocks(settings: Settings, disclosure: Disclosure, zip_bytes: bytes) -> list[ParsedBlockPayload]:
    try:
        extracted_files = extract_zip(settings.storage_root_path, disclosure.rcept_no, zip_bytes)
        return parse_document_files([(ef.file_name, ef.text) for ef in extracted_files])

    except BadZipFile:
        # 일부 공시문은 zip이 아닌 단일 텍스트/HTML/XML 응답으로 내려오기도 함
        decoded = zip_bytes.decode("utf-8", errors="ignore")
        decoded = decoded.strip()
        if not decoded:
            return []
        fallback_name = "document.xml"
        lowered = decoded.lstrip().lower()
        if lowered.startswith("<"):
            fallback_name = "document.xml" if lowered.startswith("<?xml") or "<html" in lowered[:20] or "<body" in lowered else "document.html"
        elif lowered.startswith("{"):
            # JSON 에러/예외 응답은 파싱 불가하므로 빈 결과로 빠르게 실패 처리
            return []
        return parse_document_files([(fallback_name, decoded)])

    except Exception:
        return []


def _persist_blocks(session: Session, disclosure_id: int, parsed_blocks: list[ParsedBlockPayload]) -> None:
    session.query(DocumentBlock).filter_by(disclosure_id=disclosure_id).delete(synchronize_session=False)
    for idx, b in enumerate(parsed_blocks):
        session.add(
            DocumentBlock(
                disclosure_id=disclosure_id,
                block_type=b.block_type,
                section_path=b.section_path,
                order_index=idx,
                text=b.text,
                table_json=b.table_json,
                char_start=b.char_start,
                char_end=b.char_end,
                source_locator=b.source_locator,
            )
        )


def process_disclosure_pipeline(
    session: Session,
    settings: Settings,
    client: DartClient,
    disclosure_id: int,
    *,
    question_count: int = 5,
    use_ai: bool = False,
) -> tuple[bool, str | None]:
    disclosure = session.get(models.Disclosure, disclosure_id)
    if not disclosure:
        return False, f"disclosure {disclosure_id} not found"

    try:
        disclosure.status = "downloading"
        zip_bytes = client.download_document_zip(disclosure.rcept_no)

        parsed_blocks = _write_and_parse_blocks(settings, disclosure, zip_bytes)
        if not parsed_blocks:
            disclosure.status = "failed"
            return False, "No parsable document text found (not a zip or plain text document)."
        _persist_blocks(session, disclosure.id, parsed_blocks)

        facts = extract_facts_from_blocks(disclosure.id, parsed_blocks)
        session.query(NormalizedFact).filter_by(disclosure_id=disclosure.id).delete(synchronize_session=False)
        for f in facts.facts:
            session.add(
                NormalizedFact(
                    disclosure_id=disclosure.id,
                    fact_type=f.fact_type,
                    value_text=f.value_text,
                    value_json=f.value_json,
                    confidence=f.confidence,
                    source_span_ids=f.source_span_ids,
                    status="verified",
                )
            )

        quiz_result = generate_quiz(facts, max_questions=question_count, use_ai=use_ai)
        span_ids = {f"span_{i}" for i, _ in enumerate(parsed_blocks)}
        verification = verify_quiz(quiz_result, span_ids)
        if not verification.passed:
            disclosure.status = "failed"
            return False, "; ".join(verification.reasons)

        # Replace prior quizzes for same disclosure
        existing = session.query(Quiz).filter_by(disclosure_id=disclosure.id).all()
        for old in existing:
            session.query(QuizQuestion).filter_by(quiz_id=old.id).delete(synchronize_session=False)
            session.delete(old)

        quiz = Quiz(
            disclosure_id=disclosure.id,
            version=1,
            title=quiz_result.quiz_title,
            question_count=len(quiz_result.questions),
            quality_score=1.0,
            publish_status="published" if all(q.source_span_ids for q in quiz_result.questions) else "draft",
            language=quiz_result.language,
        )
        session.add(quiz)
        session.flush()

        for idx, q in enumerate(quiz_result.questions):
            qq = QuizQuestion(
                quiz_id=quiz.id,
                order_index=idx,
                question_type=q.question_type,
                difficulty=q.difficulty,
                prompt=q.prompt,
                choices_json=q.choices,
                answer_index=q.answer_index,
                explanation=q.explanation,
                source_span_ids=q.source_span_ids,
                verification_status="passed",
            )
            session.add(qq)

        session.flush()

        disclosure.status = "parsed"
        return True, None

    except Exception as e:
        disclosure.status = "failed"
        return False, str(e)
