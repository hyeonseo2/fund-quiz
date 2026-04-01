from __future__ import annotations

import json
import random
import re
from typing import Any

import requests

from app.agents.schemas import FactExtractionResult, QuizGenerationResult, QuizQuestion
from app.core.config import Settings


_FACT_TO_QUESTION = {
    "principal_risk": "이 펀드의 위험 특성으로 가장 적절한 것은?",
    "fee": "이 펀드 문서에서 확인되는 보수/수수료 관련 내용으로 가장 적절한 것은?",
    "redemption": "이 펀드의 환매 관련 설명으로 맞는 것은?",
    "invest_objective": "이 펀드의 투자 목적에 대한 설명으로 적절하지 않은 것은?",
    "risk_warning": "다음 중 투자 시 유의사항으로 볼 수 있는 항목은?",
    "summary": "문서의 핵심 설명으로 가장 적절한 것은?",
}

FORBIDDEN = ["수익률", "앞으로", "추천", "좋은 시기", "매수"]


def _choices_for_fact(fact_type: str) -> tuple[list[str], int]:
    if fact_type == "principal_risk":
        return [
            "원금이 보장됨",
            "원금 손실이 발생할 수 있음",
            "정부가 수익률을 보장함",
            "만기 시 보유이익 보장",
        ], 1
    if fact_type == "redemption":
        return [
            "환매는 영업일 기준으로 지급됨",
            "원할 때 즉시 고금리로 지급됨",
            "환매는 불가능함",
            "최저 보유 기간이 10년인 경우만 가능",
        ], 0
    if fact_type == "fee":
        return [
            "보수는 수수료 항목으로 문서에 고지됨",
            "보수는 공개 의무사항이 아니어서 생략 가능",
            "매일 환율을 보장",
            "원금은 항상 100% 보존",
        ], 0
    return [
        "문서에 명시된 사실을 근거로 판단해야 함",
        "문서 밖 추정으로 판단",
        "개인 투자 성향에 따른 수익 보장 제공",
        "고정금리 예측이 가능함",
    ], 0


def _pick_difficulty(i: int) -> str:
    if i == 0 or i == 1:
        return "easy"
    if i == 2:
        return "hard"
    return "medium"


def _build_fallback_quiz(facts: FactExtractionResult) -> QuizGenerationResult:
    questions: list[QuizQuestion] = []
    ordered_facts = [f for f in facts.facts if f.fact_type not in {"summary"}]

    for i, fact in enumerate(ordered_facts[:5]):
        stem = _FACT_TO_QUESTION.get(fact.fact_type, "문서 근거로 판단하는 문제입니다.")
        choices, ans_idx = _choices_for_fact(fact.fact_type)
        fact_text = (fact.value_text or '').replace('\n', ' ').strip()
        if len(fact_text) > 180:
            fact_text = fact_text[:180] + '…'
        explanation = fact_text or '문서 근거를 확인하세요.'
        questions.append(
            QuizQuestion(
                question_type="single_choice",
                difficulty=_pick_difficulty(i),
                prompt=stem,
                choices=choices,
                answer_index=ans_idx,
                explanation=explanation,
                source_span_ids=fact.source_span_ids or ["span_0"],
            )
        )

    if not questions:
        questions.append(
            QuizQuestion(
                question_type="single_choice",
                difficulty="easy",
                prompt="다음 중 문서에서 언급된 내용으로 판단하기 적절한 것은?",
                choices=["문서 근거 확인 후 판단", "미확인 추정", "영업권장", "투자 권유"],
                answer_index=0,
                explanation="문서 블록 근거를 통해 판단해야 합니다.",
                source_span_ids=["span_0"],
            )
        )

    return QuizGenerationResult(quiz_title="펀드 설명서 이해도 퀴즈", questions=questions)


def _parse_gemini_response(text: str) -> list[dict[str, Any]]:
    # 1) strip markdown fences
    m = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    json_text = m.group(1) if m else text

    # 2) pick first JSON object
    start = json_text.find("{")
    end = json_text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON found in Gemini response")

    payload = json.loads(json_text[start : end + 1])
    questions = payload.get("questions")
    if not isinstance(questions, list):
        raise ValueError("Invalid questions payload")
    return questions


def _to_int(idx: int) -> int:
    try:
        return int(idx)
    except Exception:
        return 0


def _normalize_ai_choices(choices: list[Any]) -> list[str]:
    out = [str(c).strip() for c in choices[:4] if str(c).strip()]
    while len(out) < 4:
        out.append(f"보기 {len(out) + 1}")
    return out[:4]


def _generate_with_gemini(facts: FactExtractionResult, max_questions: int) -> QuizGenerationResult:
    settings = Settings()
    if not settings.gemini_api_key:
        raise ValueError("GEMINI_API_KEY is not configured")

    fact_points = []
    allowed_spans: list[str] = []
    for f in facts.facts[: max(1, max_questions) * 2]:
        snippet = (f.value_text or "").replace("\n", " ")[:220]
        spans = [str(s) for s in (f.source_span_ids or []) if str(s).strip()]
        if spans:
            allowed_spans.extend(spans)
        span_label = ",".join(spans) if spans else "span_unknown"
        fact_points.append(f"[{span_label}] {f.fact_type}: {snippet}")
    if not fact_points:
        fact_points = ["문서 텍스트 기반 질문 생성"]

    allowed_span_text = ", ".join(sorted(set(allowed_spans))) if allowed_spans else "span_0, span_1, span_2"
    prompt = (
        "너는 금융상품 공시를 기반으로 객관식 퀴즈를 생성하는 모델이다. "
        "반드시 JSON만 반환한다. 응답 형식: \n"
        '{"quiz_title":"...","questions":[{"question_type":"single_choice","difficulty":"easy|medium|hard","prompt":"질문","choices":["...","...","...","..."],"answer_index":정수,"explanation":"근거 요약","source_span_ids":["span_x"]}, ...]}\n'
        f"키워드/팩트:\n{chr(10).join(fact_points)}\n"
        f"사용 가능한 근거 span 목록: {allowed_span_text}\n"
        "요구사항: 문제 수는 최대 3개, 각 문제는 객관식 4지선다, answer_index는 0~3 정수. explanation에는 근거 내용을 자연어로 요약하고, source_span_ids는 반드시 위 목록의 span만 사용."
    )

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 1200,
        },
    }

    r = requests.post(
        url,
        params={"key": settings.gemini_api_key},
        json=payload,
        timeout=settings.request_timeout_sec,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Gemini request failed {r.status_code}: {r.text[:200]}")

    body = r.json()
    candidates = body.get("candidates") or []
    if not candidates:
        raise RuntimeError("Gemini response has no candidates")

    text = ""
    parts = candidates[0].get("content", {}).get("parts", [])
    for p in parts:
        t = p.get("text")
        if t:
            text += t

    if not text:
        raise RuntimeError("Gemini response has empty text")

    rows = _parse_gemini_response(text)
    questions: list[QuizQuestion] = []
    for i, raw in enumerate(rows[:max_questions]):
        prompt = str(raw.get("prompt", "")).strip() or "문서 근거를 바탕으로 판단하세요."
        choices = _normalize_ai_choices(raw.get("choices", []))
        ans = _to_int(raw.get("answer_index", 0))
        if ans < 0 or ans >= len(choices):
            ans = 0
        difficulty = str(raw.get("difficulty", "medium")).strip().lower()
        if difficulty not in {"easy", "medium", "hard"}:
            difficulty = "medium"
        explanation = str(raw.get("explanation", "문서 근거를 확인하세요.")).strip()
        src = raw.get("source_span_ids")
        if isinstance(src, list):
            src_spans = [str(x) for x in src if str(x).strip()]
        else:
            src_spans = []

        allowed_set = set(allowed_spans)
        if allowed_set:
            src_spans = [s for s in src_spans if s in allowed_set]

        if not src_spans:
            fallback_from_fact = []
            if i < len(facts.facts):
                fallback_from_fact = [str(x) for x in (facts.facts[i].source_span_ids or []) if str(x).strip()]
            src_spans = fallback_from_fact or [f"span_{min(i, 2)}"]

        questions.append(
            QuizQuestion(
                question_type="single_choice",
                difficulty=difficulty,
                prompt=prompt,
                choices=choices,
                answer_index=ans,
                explanation=explanation,
                source_span_ids=src_spans,
            )
        )

    if not questions:
        raise RuntimeError("Gemini produced no valid questions")

    random.shuffle(questions)
    return QuizGenerationResult(quiz_title="AI 퀴즈", questions=questions)


def generate_quiz(
    facts: FactExtractionResult,
    *,
    max_questions: int = 5,
    use_ai: bool = False,
) -> QuizGenerationResult:
    # keep deterministic fallback if no AI
    if use_ai:
        try:
            return _generate_with_gemini(facts, max_questions)
        except Exception:
            # graceful fallback to rule-based generator
            pass

    base = _build_fallback_quiz(facts)
    return QuizGenerationResult(
        quiz_title=base.quiz_title,
        questions=base.questions[:max_questions],
        language=base.language,
    )
