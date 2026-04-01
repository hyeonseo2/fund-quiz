from __future__ import annotations

from app.agents.schemas import QuizGenerationResult, QuizVerificationResult


FORBIDDEN_PATTERNS = ["수익 보장", "매수", "투자 추천", "반드시 가입", "단정적 수익"]


def verify_quiz(quiz: QuizGenerationResult, known_span_ids: set[str]) -> QuizVerificationResult:
    reasons: list[str] = []

    if not quiz.questions:
        return QuizVerificationResult(passed=False, reasons=["No questions generated"])

    if len(quiz.questions) > 5:
        reasons.append("Question count must not exceed 5")

    for idx, q in enumerate(quiz.questions):
        if not q.source_span_ids:
            reasons.append(f"Q{idx+1} missing source spans")
        elif not any(s in known_span_ids for s in q.source_span_ids):
            reasons.append(f"Q{idx+1} source span not in parsed blocks")

        if len(set(q.choices)) != len(q.choices):
            reasons.append(f"Q{idx+1} has duplicated choices")
        if not (0 <= q.answer_index < len(q.choices)):
            reasons.append(f"Q{idx+1} has invalid answer index")
        if any(p in q.prompt for p in FORBIDDEN_PATTERNS):
            reasons.append(f"Q{idx+1} prompt contains forbidden advice patterns")

    return QuizVerificationResult(passed=len(reasons) == 0, reasons=reasons)
