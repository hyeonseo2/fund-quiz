from __future__ import annotations

from app.agents.schemas import CanonicalFact, FactExtractionResult
from app.services.document_parser import ParsedBlockPayload


def _snippet_around(text: str, keys: list[str], width: int = 170) -> str:
    txt = (text or "").replace("\n", " ").strip()
    if not txt:
        return ""

    pos = -1
    hit = ""
    for k in keys:
        i = txt.find(k)
        if i >= 0 and (pos == -1 or i < pos):
            pos = i
            hit = k

    if pos == -1:
        return txt[: width * 2]

    start = max(0, pos - width)
    end = min(len(txt), pos + len(hit) + width)
    frag = txt[start:end].strip()
    if start > 0:
        frag = "…" + frag
    if end < len(txt):
        frag = frag + "…"
    return frag


def extract_facts_from_blocks(disclosure_id: int, blocks: list[ParsedBlockPayload]) -> FactExtractionResult:
    joined = "\n".join([b.text for b in blocks])
    kw_map = {
        "invest_objective": ["투자목적", "운용목적", "투자목적은"],
        "principal_risk": ["원금손실", "손실이 발생", "위험"],
        "fee": ["보수", "수수료", "판매수수료", "운용보수"],
        "redemption": ["환매", "환매일", "환매가격", "환매"],
        "risk_warning": ["중요한 사항", "주의사항", "유의사항"],
    }

    extracted: list[CanonicalFact] = []

    for fact_type, keys in kw_map.items():
        found_span = None
        sentence = None
        for idx, b in enumerate(blocks):
            if any(k in (b.text or "") for k in keys):
                found_span = f"span_{idx}"
                sentence = _snippet_around(b.text, keys)
                break
        if found_span and sentence:
            extracted.append(
                CanonicalFact(
                    fact_type=fact_type,
                    value_text=sentence,
                    source_span_ids=[found_span],
                    confidence=0.9,
                )
            )

    # fallback: create generic facts when nothing matched so pipeline still runs
    if not extracted:
        for idx, b in enumerate(blocks[:2]):
            if len(b.text) > 30:
                extracted.append(
                    CanonicalFact(
                        fact_type="summary",
                        value_text=b.text,
                        source_span_ids=[f"span_{idx}"],
                        confidence=0.6,
                    )
                )

    return FactExtractionResult(disclosure_id=disclosure_id, facts=extracted)
