from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class CanonicalFact(BaseModel):
    fact_type: str
    value_text: str | None
    value_json: dict[str, Any] | None = None
    source_span_ids: list[str] = Field(default_factory=list)
    confidence: float = 0.9


class FactExtractionResult(BaseModel):
    disclosure_id: int
    fund_name: str | None = None
    manager_name: str | None = None
    facts: list[CanonicalFact]


class QuizQuestion(BaseModel):
    question_type: str = "single_choice"
    difficulty: str = "medium"
    prompt: str
    choices: list[str]
    answer_index: int
    explanation: str
    source_span_ids: list[str]


class QuizGenerationResult(BaseModel):
    quiz_title: str
    questions: list[QuizQuestion]
    language: str = "ko"


class QuizVerificationResult(BaseModel):
    passed: bool
    reasons: list[str]
    suggestions: list[str] = Field(default_factory=list)
