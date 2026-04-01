from __future__ import annotations

from datetime import datetime, date
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Date,
    ForeignKey,
    Boolean,
    JSON,
    Float,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class AssetManager(Base):
    __tablename__ = "asset_managers"

    id = Column(Integer, primary_key=True)
    corp_code = Column(String(20), unique=True, nullable=False)
    corp_name = Column(String(255), nullable=False)
    corp_eng_name = Column(String(255))
    stock_code = Column(String(30))
    is_asset_manager = Column(Boolean, default=False, nullable=False)
    raw_payload = Column(JSON)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class FundCatalog(Base):
    __tablename__ = "fund_catalog"

    id = Column(Integer, primary_key=True)
    fund_std_code = Column(String(100), unique=True)
    fund_name = Column(String(255), nullable=False)
    fund_name_normalized = Column(String(255), nullable=False)
    manager_name = Column(String(255), nullable=False)
    manager_name_normalized = Column(String(255), nullable=False)
    category = Column(String(60), default="fund", nullable=False)
    source = Column(String(60), default="dart")
    raw_payload = Column(JSON)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_fund_catalog_name", "fund_name_normalized"),
        Index("ix_fund_catalog_manager", "manager_name_normalized"),
    )


class Disclosure(Base):
    __tablename__ = "disclosures"

    id = Column(Integer, primary_key=True)
    rcept_no = Column(String(30), unique=True, nullable=False)
    corp_code = Column(String(20), nullable=False)
    corp_name = Column(String(255), nullable=False)
    report_nm_raw = Column(String(500), nullable=False)
    normalized_document_family = Column(String(80))
    correction_type = Column(String(40))
    pblntf_ty = Column(String(10))
    pblntf_detail_ty = Column(String(20))
    rcept_dt = Column(Date, nullable=False)
    flr_nm = Column(String(255))
    is_latest = Column(Boolean, default=False, nullable=False)
    status = Column(String(40), default="listed", nullable=False)
    raw_payload = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class DocumentFile(Base):
    __tablename__ = "document_files"

    id = Column(Integer, primary_key=True)
    disclosure_id = Column(Integer, ForeignKey("disclosures.id"), nullable=False)
    file_name = Column(String(255), nullable=False)
    mime_type = Column(String(64))
    storage_path = Column(String(500), nullable=False)
    sha256 = Column(String(128), nullable=False)
    is_original_zip = Column(Boolean, default=True, nullable=False)
    extracted_from_zip = Column(Boolean, default=False, nullable=False)
    size_bytes = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    disclosure = relationship("Disclosure")


class DocumentBlock(Base):
    __tablename__ = "document_blocks"

    id = Column(Integer, primary_key=True)
    disclosure_id = Column(Integer, ForeignKey("disclosures.id"), nullable=False)
    block_type = Column(String(32), nullable=False)
    section_path = Column(String(255), nullable=False)
    order_index = Column(Integer, default=0, nullable=False)
    text = Column(Text, nullable=False)
    table_json = Column(JSON)
    char_start = Column(Integer)
    char_end = Column(Integer)
    source_locator = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    disclosure = relationship("Disclosure")


class NormalizedFact(Base):
    __tablename__ = "normalized_facts"

    id = Column(Integer, primary_key=True)
    disclosure_id = Column(Integer, ForeignKey("disclosures.id"), nullable=False)
    fund_catalog_id = Column(Integer, ForeignKey("fund_catalog.id"))
    fact_type = Column(String(80), nullable=False)
    value_text = Column(Text, nullable=True)
    value_json = Column(JSON)
    confidence = Column(Float, default=0.7)
    source_span_ids = Column(JSON, nullable=False)
    status = Column(String(30), default="draft", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    disclosure = relationship("Disclosure")
    fund_catalog = relationship("FundCatalog")


class Quiz(Base):
    __tablename__ = "quizzes"

    id = Column(Integer, primary_key=True)
    disclosure_id = Column(Integer, ForeignKey("disclosures.id"), nullable=False)
    fund_catalog_id = Column(Integer, ForeignKey("fund_catalog.id"))
    version = Column(Integer, default=1)
    title = Column(String(255), nullable=False)
    language = Column(String(16), default="ko")
    question_count = Column(Integer, default=0)
    quality_score = Column(Float)
    publish_status = Column(String(30), default="draft", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    disclosure = relationship("Disclosure")


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id = Column(Integer, primary_key=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=False)
    order_index = Column(Integer, default=0)
    question_type = Column(String(40), default="single_choice")
    difficulty = Column(String(20), default="medium")
    prompt = Column(Text, nullable=False)
    choices_json = Column(JSON, nullable=False)
    answer_index = Column(Integer, nullable=False)
    explanation = Column(Text, nullable=False)
    source_span_ids = Column(JSON, nullable=False)
    verification_status = Column(String(20), default="pending")

    quiz = relationship("Quiz")


class UserAttempt(Base):
    __tablename__ = "user_attempts"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(120))
    anonymous_session_id = Column(String(120))
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=False)
    score = Column(Integer)
    answers_json = Column(JSON, nullable=False)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    quiz = relationship("Quiz")


class AdminJob(Base):
    __tablename__ = "admin_jobs"

    id = Column(Integer, primary_key=True)
    job_type = Column(String(80), nullable=False)
    target_type = Column(String(40), nullable=False)
    target_id = Column(String(80), nullable=False)
    status = Column(String(30), default="pending", nullable=False)
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    error_message = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
