from __future__ import annotations

from datetime import datetime, date, timedelta
import threading

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func

from app.clients.dart_client import DartClient
from app.core.config import Settings
from app.db import models
from app.db.session import get_session
from app.schemas.fund import FundSearchItem, FundOut, QuizOut, QuizQuestionOut, QuizAttemptIn, QuizAttemptOut
from app.services.quiz_pipeline import process_disclosure_pipeline, sync_disclosures_for_corp

router = APIRouter(prefix="/api", tags=["public"])

SAMPLE_MANAGER_CODES_DEFAULT = ["00260453", "00104500"]  # fallback
SAMPLE_ITEMS_PER_MANAGER = 10  # 샘플 동기화 시 각 운용사별 최대 수집 건수(최근 공시 기준)
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
MAJOR_MANAGER_NAME_SET = set(MAJOR_MANAGER_NAMES)
MAJOR_MANAGER_LIMIT = 10
SAMPLE_DAYS_LOOKBACK = 90  # major 매니저의 최신 공시 중 '최근 N일'만 미리 동기화

# 자산운용사 중심 샘플 수집 대상으로 사용하는 코루틴 초기 후보군
ASSET_MANAGER_KEYWORDS = ["자산운용", "자산운용사"]
# bootstrap에서 실제로 사용되는 코드목록(동적 갱신)
SAMPLE_MANAGER_CODES = list(SAMPLE_MANAGER_CODES_DEFAULT)
SAMPLE_BOOTSTRAP_INFLIGHT = False

def _discover_manager_codes_from_corp_codes(settings: Settings, limit: int = MAJOR_MANAGER_LIMIT) -> list[str]:
    """OpenDART 전체 법인목록에서 자산운용사 키워드로 보이는 회사코드(메이저 우선)로 반환한다."""
    try:
        client = DartClient(settings)
        major_codes: list[str] = []
        fallback_codes: list[str] = []
        seen: set[str] = set()

        for code, name in client.fetch_corp_codes():
            if not any(keyword in (name or "") for keyword in ASSET_MANAGER_KEYWORDS):
                continue
            if code in seen:
                continue
            seen.add(code)

            if name in MAJOR_MANAGER_NAME_SET:
                major_codes.append(code)
            else:
                fallback_codes.append(code)

            if len(major_codes) >= limit:
                return major_codes

        out = major_codes[:]
        for code in fallback_codes:
            if code not in out:
                out.append(code)
            if len(out) >= limit:
                break

        if out:
            return out
    except Exception:
        # 임시 오류 시 폴백 코드를 사용
        return list(SAMPLE_MANAGER_CODES_DEFAULT)

    return list(SAMPLE_MANAGER_CODES_DEFAULT)


def _refresh_sample_manager_codes(settings: Settings, force_fallback: bool = False) -> list[str]:
    global SAMPLE_MANAGER_CODES
    if force_fallback:
        SAMPLE_MANAGER_CODES = list(SAMPLE_MANAGER_CODES_DEFAULT)
        return SAMPLE_MANAGER_CODES

    codes = _discover_manager_codes_from_corp_codes(settings)
    SAMPLE_MANAGER_CODES = codes
    return SAMPLE_MANAGER_CODES

def _discover_manager_names_from_corp_codes(settings: Settings, limit: int = 500) -> list[str]:
    """OpenDART에서 자산운용사 키워드로 보이는 이름 목록을 바로 추려서 반환."""
    names: list[str] = []
    seen: set[str] = set()
    try:
        client = DartClient(settings)
        for _, name in client.fetch_corp_codes():
            if not name:
                continue
            if name in seen:
                continue
            if any(keyword in name for keyword in ASSET_MANAGER_KEYWORDS):
                names.append(name)
                seen.add(name)
            if len(names) >= limit:
                break
    except Exception:
        return ["KB자산운용", "삼성자산운용"]
    return names


def _sample_bootstrap_task(session, settings: Settings):
    global SAMPLE_BOOTSTRAP_INFLIGHT
    try:
        client = DartClient(settings)
        manager_codes = _refresh_sample_manager_codes(settings)
        end_de = datetime.utcnow().date()
        bgn_de = (end_de - timedelta(days=SAMPLE_DAYS_LOOKBACK)).strftime("%Y%m%d")
        end_de = end_de.strftime("%Y%m%d")
        for code in manager_codes:
            sync_disclosures_for_corp(
                session=session,
                client=client,
                corp_code=code,
                bgn_de=bgn_de,
                end_de=end_de,
                max_items=SAMPLE_ITEMS_PER_MANAGER,
            )
    finally:
        SAMPLE_BOOTSTRAP_INFLIGHT = False


@router.post("/sample/bootstrap")
def bootstrap_sample_data():
    """자산운용사 공시/상품 샘플 데이터를 동기화한다."""
    global SAMPLE_BOOTSTRAP_INFLIGHT
    if SAMPLE_BOOTSTRAP_INFLIGHT:
        return {"status": "running", "started": False}

    def run():
        from app.db.session import get_session
        with get_session() as sess:
            _sample_bootstrap_task(sess, Settings())

    SAMPLE_BOOTSTRAP_INFLIGHT = True
    threading.Thread(target=run, daemon=True).start()
    return {"status": "started", "started": True}


@router.get("/sample/bootstrap-status")
def sample_bootstrap_status():
    return {"inflight": SAMPLE_BOOTSTRAP_INFLIGHT}


@router.get("/ui-config")
def ui_config():
    s = Settings()
    return {
        "auto_ai_generate_count": max(0, min(int(s.auto_ai_generate_count or 1), 10))
    }



def _to_fund_item(sess, row: models.Disclosure) -> FundSearchItem:
    has_published_quiz = (
        sess.query(models.Quiz).filter_by(disclosure_id=row.id, publish_status="published").count() > 0
    )
    return FundSearchItem(
        fund_id=row.id,
        fund_name=row.report_nm_raw[:120],
        manager_name=row.corp_name,
        latest_disclosure_date=row.rcept_dt,
        has_published_quiz=bool(has_published_quiz),
    )


def _quiz_to_out(sess, quiz: models.Quiz) -> QuizOut:
    qs = (
        sess.query(models.QuizQuestion)
        .filter_by(quiz_id=quiz.id)
        .order_by(models.QuizQuestion.order_index)
        .all()
    )
    return QuizOut(
        quiz_id=quiz.id,
        disclosure_id=quiz.disclosure_id,
        title=quiz.title,
        question_count=len(qs),
        language=quiz.language,
        questions=[
            QuizQuestionOut(
                question_type=q.question_type,
                difficulty=q.difficulty,
                prompt=q.prompt,
                choices=list(q.choices_json or []),
                answer_index=q.answer_index,
                explanation=q.explanation,
                source_span_ids=list(q.source_span_ids or []),
            )
            for q in qs
        ],
    )


@router.get("/funds", response_model=list[FundSearchItem])
def list_funds(q: str | None = Query(default=None), manager: str | None = Query(default=None), limit: int = 200):
    """메인 화면용: 퀴즈 공개 가능한/전체 금융상품 목록 조회."""
    with get_session() as sess:
        query = sess.query(models.Disclosure)
        if q:
            qterm = f"%{q}%"
            query = query.filter(
                (models.Disclosure.report_nm_raw.ilike(qterm))
                | (models.Disclosure.corp_name.ilike(qterm))
            )
        if manager:
            manager_term = f"%{manager}%"
            query = query.filter(models.Disclosure.corp_name.ilike(manager_term))
        elif not q:
            active_sample_codes = [code for code in SAMPLE_MANAGER_CODES if code]
            if not active_sample_codes:
                active_sample_codes = SAMPLE_MANAGER_CODES_DEFAULT
            query = query.filter(models.Disclosure.corp_code.in_(active_sample_codes))

        rows = query.order_by(models.Disclosure.rcept_dt.desc(), models.Disclosure.id.desc()).limit(limit).all()
        return [_to_fund_item(sess, row) for row in rows]


@router.get("/funds/search", response_model=list[FundSearchItem])
def search_funds(q: str = Query(..., min_length=1), manager: str | None = Query(default=None)):
    with get_session() as sess:
        qterm = f"%{q}%"
        query = sess.query(models.Disclosure).filter(models.Disclosure.report_nm_raw.ilike(qterm))
        if manager:
            query = query.filter(models.Disclosure.corp_name.ilike(f"%{manager}%"))
        rows = (
            query
            .order_by(models.Disclosure.rcept_dt.desc(), models.Disclosure.id.desc())
            .limit(50)
            .all()
        )
        return [_to_fund_item(sess, row) for row in rows]


@router.get("/managers")
def list_managers(limit: int = MAJOR_MANAGER_LIMIT):
    with get_session() as sess:
        # 1) DB 기준으로 공개된 상품 개수가 많은 운용사(상위부터) 우선
        major_q = (
            sess.query(
                models.Disclosure.corp_name.label("corp_name"),
                func.count(models.Disclosure.id).label("cnt"),
            )
            .filter(models.Disclosure.corp_name.isnot(None))
            .filter(models.Disclosure.corp_name != "")
            .group_by(models.Disclosure.corp_name)
            .order_by(func.count(models.Disclosure.id).desc())
            .limit(limit)
            .all()
        )
        names = [r.corp_name for r in major_q]

        if len(names) < max(1, min(MAJOR_MANAGER_LIMIT, limit)):
            # warm-up or DB empty: fallback to pre-defined major list
            names = MAJOR_MANAGER_NAMES[:limit]

        names = [n for n in names if n][:limit]
        return names


@router.get("/funds/{fund_id}/document-preview")
def get_fund_document_preview(fund_id: int, limit_blocks: int = 20):
    with get_session() as sess:
        disc = sess.get(models.Disclosure, fund_id)
        if not disc:
            raise HTTPException(status_code=404, detail="Fund disclosure not found")

        rows = (
            sess.query(models.DocumentBlock)
            .filter_by(disclosure_id=disc.id)
            .order_by(models.DocumentBlock.order_index.asc(), models.DocumentBlock.id.asc())
            .limit(max(1, min(limit_blocks, 200)))
            .all()
        )

        has_more = (
            sess.query(models.DocumentBlock)
            .filter_by(disclosure_id=disc.id)
            .count() > len(rows)
        )

        text = "\n\n".join((r.text or "").strip() for r in rows if (r.text or "").strip())
        if not text:
            text = ""

        return {
            "fund_id": disc.id,
            "rcept_no": disc.rcept_no,
            "rcept_dt": disc.rcept_dt,
            "preview": text[:8000],
            "has_more": bool(has_more),
            "block_count": len(rows),
            "download_url": f"/api/funds/{disc.id}/document-download",
            "viewer_url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={disc.rcept_no}",
        }

@router.get("/funds/{fund_id}/document-download")
def download_fund_document(fund_id: int):
    """문서 블록 전체 텍스트를 txt로 다운로드한다 (임시 원문 추출물)."""
    with get_session() as sess:
        disc = sess.get(models.Disclosure, fund_id)
        if not disc:
            raise HTTPException(status_code=404, detail="Fund disclosure not found")

        rows = (
            sess.query(models.DocumentBlock)
            .filter_by(disclosure_id=disc.id)
            .order_by(models.DocumentBlock.order_index.asc(), models.DocumentBlock.id.asc())
            .all()
        )
        text = "\n\n".join((r.text or "").strip() for r in rows if (r.text or "").strip())
        if not text:
            raise HTTPException(status_code=404, detail="No document text extracted yet")

        # Return plain-text stream from extracted blocks
        import io

        filename = f"{disc.rcept_no}_document.txt"
        return StreamingResponse(
            io.BytesIO(text.encode("utf-8")),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename=\"{filename}\""},
        )

@router.get("/funds/{fund_id}", response_model=FundOut)
def read_fund(fund_id: int):
    with get_session() as sess:
        disc = sess.get(models.Disclosure, fund_id)
        if not disc:
            raise HTTPException(status_code=404, detail="Fund disclosure not found")
        return FundOut(
            fund_id=disc.id,
            fund_name=disc.report_nm_raw,
            manager_name=disc.corp_name,
            latest_disclosure_date=disc.rcept_dt,
            latest_disclosure_rcept_no=disc.rcept_no,
            latest_document_type=disc.normalized_document_family,
        )


@router.get("/funds/{fund_id}/quiz", response_model=QuizOut | None)
def get_fund_quiz(fund_id: int):
    with get_session() as sess:
        quiz = (
            sess.query(models.Quiz)
            .filter_by(disclosure_id=fund_id, publish_status="published")
            .order_by(models.Quiz.id.desc())
            .first()
        )
        if not quiz:
            return None
        return _quiz_to_out(sess, quiz)


@router.post("/funds/{fund_id}/quiz/generate", response_model=QuizOut)
def generate_fund_quiz(
    fund_id: int,
    count: int = 5,
    force: bool = False,
    use_ai: bool = False,
):
    """Generate quiz for selected disclosure from 설명서 immediately (동기 실행)."""
    with get_session() as sess:
        disclosure = sess.get(models.Disclosure, fund_id)
        if not disclosure:
            raise HTTPException(status_code=404, detail="Fund disclosure not found")

        existing_quiz = None
        quiz = (
            sess.query(models.Quiz)
            .filter_by(disclosure_id=disclosure.id, publish_status="published")
            .order_by(models.Quiz.id.desc())
            .first()
        )
        if quiz and not force:
            return _quiz_to_out(sess, quiz)

        question_count = min(max(int(count or 5), 1), 10)
        settings = Settings()
        ok, reason = process_disclosure_pipeline(
            sess,
            settings,
            DartClient(settings),
            disclosure.id,
            question_count=question_count,
            use_ai=use_ai,
        )
        if not ok:
            raise HTTPException(status_code=400, detail=f"Failed to generate quiz: {reason}")

        # fallback: return latest generated quiz even if not published yet (for UI retry flow)
        if not quiz:
            quiz = (
                sess.query(models.Quiz)
                .filter_by(disclosure_id=disclosure.id)
                .order_by(models.Quiz.id.desc())
                .first()
            )

        if not quiz:
            raise HTTPException(status_code=404, detail="Quiz generation did not produce any quiz")

        return _quiz_to_out(sess, quiz)


@router.get("/disclosures/{rcept_no}")
def get_disclosure(rcept_no: str):
    with get_session() as sess:
        disc = sess.query(models.Disclosure).filter_by(rcept_no=rcept_no).first()
        if not disc:
            raise HTTPException(status_code=404, detail="Disclosure not found")
        return {
            "rcept_no": disc.rcept_no,
            "report_nm": disc.report_nm_raw,
            "rcept_dt": disc.rcept_dt,
            "normalized_document_family": disc.normalized_document_family,
            "publish_status": sess.query(models.Quiz).filter_by(disclosure_id=disc.id, publish_status="published").count() > 0,
        }


@router.post("/quiz-attempts", response_model=QuizAttemptOut)
def submit_attempt(payload: QuizAttemptIn):
    with get_session() as sess:
        quiz = sess.get(models.Quiz, payload.quiz_id)
        if not quiz:
            return QuizAttemptOut(quiz_id=payload.quiz_id, score=0, total=0, correct=[], explanations=[], source_refs={}, source_snippets={})

        qs = sess.query(models.QuizQuestion).filter_by(quiz_id=quiz.id).order_by(models.QuizQuestion.order_index).all()

        correct: list[bool] = []
        explanations: list[str] = []
        source_refs: dict[int, list[str]] = {}
        source_snippets: dict[int, list[str]] = {}
        score = 0
        for idx, q in enumerate(qs):
            is_correct = idx < len(payload.answers) and payload.answers[idx] == q.answer_index
            if is_correct:
                score += 1
            correct.append(is_correct)
            explanations.append(q.explanation)
            refs = list(q.source_span_ids or [])
            source_refs[idx] = refs

            snippets: list[str] = []
            for ref in refs:
                if not isinstance(ref, str) or not ref.startswith('span_'):
                    continue
                try:
                    order_idx = int(ref.split('_', 1)[1])
                except (ValueError, IndexError):
                    continue
                block = (
                    sess.query(models.DocumentBlock)
                    .filter_by(disclosure_id=quiz.disclosure_id, order_index=order_idx)
                    .first()
                )
                if block and (block.text or '').strip():
                    snippets.append((block.text or '').strip()[:280])
            source_snippets[idx] = snippets

        sess.add(
            models.UserAttempt(
                user_id=payload.user_id,
                anonymous_session_id=payload.anonymous_session_id,
                quiz_id=payload.quiz_id,
                score=score,
                answers_json=payload.answers,
            )
        )

        return QuizAttemptOut(
            quiz_id=quiz.id,
            score=score,
            total=len(qs),
            correct=correct,
            explanations=explanations,
            source_refs=source_refs,
            source_snippets=source_snippets,
        )
