#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

OPENDART_BASE = "https://opendart.fss.or.kr/api"

MAJOR_MANAGER_NAMES = [
    "KB자산운용",
    "삼성자산운용",
    "미래에셋자산운용",
    "대신자산운용",
    "키움자산운용",
    "교보자산운용",
    "하나자산운용",
    "신한자산운용",
    "NH투자증권자산운용",
    "마이다스에셋자산운용",
]


@dataclass
class Disclosure:
    corp_code: str
    corp_name: str
    report_nm: str
    rcept_no: str
    rcept_dt: str


def fetch_major_corp_codes(api_key: str) -> list[str]:
    import io
    import zipfile
    import xml.etree.ElementTree as ET

    resp = requests.get(f"{OPENDART_BASE}/corpCode.xml", params={"crtfc_key": api_key}, timeout=60)
    resp.raise_for_status()
    content = resp.content

    if content[:2] == b"PK":
        zf = zipfile.ZipFile(io.BytesIO(content))
        xml_name = next((n for n in zf.namelist() if n.lower().endswith('.xml')), None)
        if not xml_name:
            return []
        xml_bytes = zf.read(xml_name)
    else:
        xml_bytes = content

    root = ET.fromstring(xml_bytes)
    name_to_code: dict[str, str] = {}
    for item in root.findall('list'):
        name = (item.findtext('corp_name') or '').strip()
        code = (item.findtext('corp_code') or '').strip()
        if name and code:
            name_to_code[name] = code

    out: list[str] = []
    for n in MAJOR_MANAGER_NAMES:
        code = name_to_code.get(n)
        if code:
            out.append(code)
    return out


def fetch_disclosures(api_key: str, corp_code: str, from_date: str, to_date: str, page_count: int = 20) -> list[Disclosure]:
    resp = requests.get(
        f"{OPENDART_BASE}/list.json",
        params={
            "crtfc_key": api_key,
            "corp_code": corp_code,
            "bgn_de": from_date,
            "end_de": to_date,
            "page_no": 1,
            "page_count": page_count,
            "last_reprt_at": "Y",
            "pblntf_ty": "G",
            "sort": "date",
            "sort_mth": "desc",
        },
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("status") != "000":
        return []

    out: list[Disclosure] = []
    for row in payload.get("list") or []:
        report_nm = str(row.get("report_nm") or "")
        if "투자설명서" not in report_nm and "일괄신고서" not in report_nm:
            continue
        out.append(
            Disclosure(
                corp_code=str(row.get("corp_code") or ""),
                corp_name=str(row.get("corp_name") or ""),
                report_nm=report_nm,
                rcept_no=str(row.get("rcept_no") or ""),
                rcept_dt=str(row.get("rcept_dt") or ""),
            )
        )
    return out


def fallback_quiz(title: str) -> dict[str, Any]:
    return {
        "title": "금융상품 이해 퀴즈",
        "questions": [
            {
                "difficulty": "easy",
                "prompt": f"다음 문서(\"{title[:40]}...\")에 대한 올바른 학습 태도로 가장 적절한 것은?",
                "choices": [
                    "공시 원문을 확인하고 판단한다",
                    "문서 확인 없이 수익을 단정한다",
                    "타인의 추천만으로 즉시 투자한다",
                    "위험 정보를 무시한다",
                ],
                "answer_index": 0,
                "explanation": "공시 문서의 투자목적·위험·수수료 항목을 확인하고 판단하는 것이 중요합니다.",
            },
            {
                "difficulty": "medium",
                "prompt": "공시 문서를 볼 때 우선 확인할 항목으로 가장 적절한 조합은?",
                "choices": [
                    "투자목적, 위험등급, 보수/수수료",
                    "유행 종목, 단기 소문, 커뮤니티 평판",
                    "광고 문구, 예상 수익률, 지인 추천",
                    "과거 최고 수익률만 단독 확인",
                ],
                "answer_index": 0,
                "explanation": "투자 판단 전 핵심 공시 항목(목적·위험·비용)을 함께 확인해야 합니다.",
            },
            {
                "difficulty": "hard",
                "prompt": "공시 기반 학습 퀴즈의 목적에 가장 가까운 것은?",
                "choices": [
                    "문서 이해도를 높여 합리적 판단을 돕기 위함",
                    "특정 상품 매수를 유도하기 위함",
                    "원금 보장을 약속하기 위함",
                    "미래 수익률을 확정하기 위함",
                ],
                "answer_index": 0,
                "explanation": "이 퀴즈는 공시 문서 이해와 금융 리터러시 향상을 위한 학습용입니다.",
            },
        ],
    }


def gemini_quiz(gemini_key: str, title: str) -> dict[str, Any] | None:
    prompt = (
        "다음 금융 공시 제목을 기반으로 학습용 객관식 퀴즈 3문항을 JSON으로만 생성하세요."
        "형식: {\"title\":\"...\",\"questions\":[{\"difficulty\":\"easy|medium|hard\",\"prompt\":\"...\",\"choices\":[\"...\",\"...\",\"...\",\"...\"],\"answer_index\":0,\"explanation\":\"...\"}]}"
        f"\n공시 제목: {title}"
    )
    try:
        resp = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent",
            params={"key": gemini_key},
            json={"contents": [{"role": "user", "parts": [{"text": prompt}]}]},
            timeout=40,
        )
        resp.raise_for_status()
        body = resp.json()
        text = ""
        for p in (body.get("candidates") or [{}])[0].get("content", {}).get("parts", []):
            text += p.get("text", "")
        s = text.find("{")
        e = text.rfind("}")
        if s == -1 or e == -1:
            return None
        parsed = json.loads(text[s : e + 1])
        qs = parsed.get("questions")
        if not isinstance(qs, list) or not qs:
            return None
        return parsed
    except Exception:
        return None


def main() -> None:
    opendart_key = os.getenv("OPENDART_API_KEY", "").strip()
    if not opendart_key:
        raise SystemExit("OPENDART_API_KEY is required")

    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    corp_codes_env = [c.strip() for c in os.getenv("CORP_CODES", "").split(",") if c.strip()]
    corp_codes = corp_codes_env or fetch_major_corp_codes(opendart_key)
    if not corp_codes:
        corp_codes = ["00267526", "00260453"]

    major_limit = max(1, min(int(os.getenv("MAJOR_MANAGER_LIMIT", "10")), 20))
    corp_codes = corp_codes[:major_limit]

    per_corp = max(1, min(int(os.getenv("PER_CORP_LIMIT", "5")), 20))

    to_date = datetime.now(timezone.utc).date()
    from_date = to_date - timedelta(days=30)

    funds: list[dict[str, Any]] = []
    seq = 1
    for corp in corp_codes:
        items = fetch_disclosures(opendart_key, corp, from_date.strftime("%Y%m%d"), to_date.strftime("%Y%m%d"), 50)
        for d in items[:per_corp]:
            quiz = gemini_quiz(gemini_key, d.report_nm) if gemini_key else None
            if not quiz:
                quiz = fallback_quiz(d.report_nm)
            funds.append(
                {
                    "fund_id": seq,
                    "fund_name": d.report_nm,
                    "manager_name": d.corp_name,
                    "latest_disclosure_date": d.rcept_dt,
                    "rcept_no": d.rcept_no,
                    "viewer_url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={d.rcept_no}",
                    "quiz": quiz,
                }
            )
            seq += 1

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(funds),
        "funds": funds,
    }

    docs_data = Path("docs/data")
    docs_data.mkdir(parents=True, exist_ok=True)
    (docs_data / "funds.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote docs/data/funds.json ({len(funds)} items)")


if __name__ == "__main__":
    main()
