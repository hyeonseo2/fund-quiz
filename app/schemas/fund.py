from __future__ import annotations

from datetime import date
from typing import Any
from pydantic import BaseModel, Field


class FundSearchItem(BaseModel):
    fund_id: int
    fund_name: str
    manager_name: str
    latest_disclosure_date: date | None = None
    has_published_quiz: bool = False


class QuizQuestionOut(BaseModel):
    question_type: str
    difficulty: str
    prompt: str
    choices: list[str]
    answer_index: int
    explanation: str
    source_span_ids: list[str] = Field(default_factory=list)


class QuizOut(BaseModel):
    quiz_id: int
    disclosure_id: int
    title: str
    question_count: int
    language: str
    questions: list[QuizQuestionOut]


class FundOut(BaseModel):
    fund_id: int
    fund_name: str
    manager_name: str
    latest_disclosure_date: date | None = None
    latest_disclosure_rcept_no: str | None = None
    latest_document_type: str | None = None


class QuizAttemptIn(BaseModel):
    quiz_id: int
    answers: list[int]
    anonymous_session_id: str | None = None
    user_id: str | None = None


class QuizAttemptOut(BaseModel):
    quiz_id: int
    score: int
    total: int
    correct: list[bool]
    explanations: list[str]
    source_refs: dict[int, list[str]]
    source_snippets: dict[int, list[str]] = Field(default_factory=dict)
