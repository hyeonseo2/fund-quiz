from __future__ import annotations

import re
from dataclasses import dataclass


INCLUDE_PATTERNS = [
    (re.compile(r"간이투자설명서"), "prospectus_short"),
    (re.compile(r"투자설명서"), "prospectus"),
    (re.compile(r"증권신고서\(집합투자증권"), "registration_statement"),
    (re.compile(r"일괄신고서\(집합투자증권"), "shelf_registration"),
]

EXCLUDE_PATTERNS = [
    re.compile(r"효력발생안내"),
    re.compile(r"증권발행실적보고서"),
    re.compile(r"발행조건확정"),
    re.compile(r"정정안내"),
]

CORRECTION_PREFIX = re.compile(r"^\s*\[[^\]]+\]")

RANKING = {
    "prospectus_short": 1,
    "prospectus": 2,
    "registration_statement": 3,
    "shelf_registration": 4,
}


@dataclass(frozen=True)
class ReportClassification:
    family: str | None
    is_candidate: bool
    correction_type: str | None
    rank: int | None


def normalize_report_name(report_nm: str) -> ReportClassification:
    correction = CORRECTION_PREFIX.search(report_nm)
    correction_type = None
    if correction:
        correction_type = correction.group(0).strip("[]")

    for p in EXCLUDE_PATTERNS:
        if p.search(report_nm):
            return ReportClassification(None, False, correction_type, None)

    for p, family in INCLUDE_PATTERNS:
        if p.search(report_nm):
            return ReportClassification(family=family, is_candidate=True, correction_type=correction_type, rank=RANKING.get(family))

    return ReportClassification(None, False, correction_type, None)
