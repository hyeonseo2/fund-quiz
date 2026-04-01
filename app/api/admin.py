from __future__ import annotations

from datetime import datetime, date, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import func, or_

from app.api.deps import require_admin_token
from app.clients.dart_client import DartClient
from app.core.config import Settings
from app.db import models
from app.db.session import get_session
from app.services.quiz_pipeline import sync_disclosures_for_corp, process_disclosure_pipeline
from app.schemas.admin import BackfillRequest, ReingestRequest, RegenerateRequest, JobOut

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin_token)])


def _job_to_out(row: models.AdminJob) -> JobOut:
    return JobOut(
        id=row.id,
        job_type=row.job_type,
        target_type=row.target_type,
        target_id=row.target_id,
        status=row.status,
        error_message=row.error_message,
    )


@router.get("/jobs", response_model=list[JobOut])
def list_jobs(limit: int = 50):
    with get_session() as sess:
        rows = sess.query(models.AdminJob).order_by(models.AdminJob.id.desc()).limit(limit).all()
        return [_job_to_out(r) for r in rows]


@router.post("/disclosures/backfill")
def backfill_disclosures(payload: BackfillRequest):
    with get_session() as sess:
        client = DartClient(Settings())
        try:
            bgn_de = (payload.from_date or date(2000, 1, 1)).strftime("%Y%m%d")
            end_de = (payload.to_date or datetime.utcnow().date()).strftime("%Y%m%d")
            created = sync_disclosures_for_corp(
                session=sess,
                client=client,
                corp_code=payload.corp_code,
                bgn_de=bgn_de,
                end_de=end_de,
            )
        except Exception as exc:
            return {"error": str(exc)}
        return {"created": len(created), "rcept_nos": [d.rcept_no for d in created]}


@router.post("/disclosures/reingest")
def reingest_disclosure(payload: ReingestRequest):
    with get_session() as sess:
        disc = sess.query(models.Disclosure).filter_by(rcept_no=payload.rcept_no).first()
        if not disc:
            return {"error": "not_found"}
        job = models.AdminJob(job_type="reingest", target_type="disclosure", target_id=str(disc.id), status="pending")
        sess.add(job)
        return {"job_id": job.id}


@router.post("/quizzes/regenerate")
def regenerate_quiz(payload: RegenerateRequest):
    with get_session() as sess:
        disc = sess.get(models.Disclosure, payload.disclosure_id)
        if not disc:
            return {"error": "not_found"}
        job = models.AdminJob(job_type="regenerate", target_type="disclosure", target_id=str(payload.disclosure_id), status="pending")
        sess.add(job)
        return {"job_id": job.id}


@router.post("/manager/sync")
def sync_corp_codes():
    with get_session() as sess:
        client = DartClient(Settings())
        try:
            rows = client.fetch_corp_codes()
        except Exception as exc:
            return {"error": str(exc)}

        for code, name in rows:
            existing = sess.query(models.AssetManager).filter_by(corp_code=code).one_or_none()
            if existing:
                existing.corp_name = name
                existing.updated_at = datetime.utcnow()
                existing.is_asset_manager = True
            else:
                sess.add(models.AssetManager(corp_code=code, corp_name=name, is_asset_manager=True))
        return {"count": len(rows)}


@router.post("/manager/prefill")
def prefill_managers_from_disclosures():
    """공지/공시 데이터에서 실제로 공시가 존재하는 운용사를 AssetManager 테이블에 반영한다."""
    with get_session() as sess:
        disclosure_rows = (
            sess.query(
                models.Disclosure.corp_code,
                func.max(models.Disclosure.corp_name).label("corp_name"),
            )
            .filter(models.Disclosure.corp_code.isnot(None))
            .group_by(models.Disclosure.corp_code)
            .all()
        )

        if not disclosure_rows:
            return {"count": 0, "message": "disclosures not found"}

        updated = 0
        for code, corp_name in disclosure_rows:
            if not code:
                continue
            name = (corp_name or "").strip()
            if not name:
                continue
            existing = sess.query(models.AssetManager).filter_by(corp_code=code).one_or_none()
            if existing:
                if existing.corp_name != name:
                    existing.corp_name = name
                existing.updated_at = datetime.utcnow()
                existing.is_asset_manager = True
            else:
                sess.add(models.AssetManager(corp_code=code, corp_name=name, is_asset_manager=True))
            updated += 1

        return {"count": updated}


@router.get("/manager/lookup")
def lookup_manager(name: str, limit: int = 200, sample_limit: int = 0, only_disclosed: bool = False):
    """운용사명을 검색해 매칭되는 corp_code를 반환한다."""
    with get_session() as sess:
        query_term = (name or "").strip()
        if not query_term:
            return {"count": 0, "items": []}

        q = f"%{query_term}%"
        rows_query = (
            sess.query(
                models.AssetManager.corp_code,
                models.AssetManager.corp_name,
                func.count(models.Disclosure.id).label("disclosure_count"),
            )
            .outerjoin(models.Disclosure, models.Disclosure.corp_code == models.AssetManager.corp_code)
            .filter(models.AssetManager.is_asset_manager.is_(True))
            .filter(
                or_(
                    models.AssetManager.corp_name.ilike(q),
                    models.AssetManager.corp_code.ilike(q),
                )
            )
            .group_by(models.AssetManager.corp_code, models.AssetManager.corp_name)
            .order_by(
                func.count(models.Disclosure.id).desc(),
                models.AssetManager.corp_name.asc(),
            )
        )

        if sample_limit and sample_limit > 0 and only_disclosed:
            rows = rows_query.having(func.count(models.Disclosure.id) > 0).limit(min(sample_limit, limit)).all()
            if not rows:
                rows = rows_query.limit(min(sample_limit, limit)).all()
        else:
            rows = rows_query.limit(min(sample_limit, limit) if sample_limit > 0 else limit).all()

        return {
            "count": len(rows),
            "sample_limit": sample_limit if sample_limit and sample_limit > 0 else None,
            "items": [
                {
                    "corp_code": r[0],
                    "corp_name": r[1],
                    "disclosure_count": int(r[2] or 0),
                }
                for r in rows
            ],
        }


@router.get("/manager/list")
def list_managers(limit: int = 5000, sample_limit: int = 0, only_disclosed: bool = False):
    """운용사 목록을 미리 불러온 뒤, UI 자동완성에 쓰기 위한 목록 반환."""
    with get_session() as sess:
        q = (
            sess.query(
                models.AssetManager.corp_code,
                models.AssetManager.corp_name,
                func.count(models.Disclosure.id).label("disclosure_count"),
            )
            .outerjoin(models.Disclosure, models.Disclosure.corp_code == models.AssetManager.corp_code)
            .filter(models.AssetManager.is_asset_manager.is_(True))
            .group_by(models.AssetManager.corp_code, models.AssetManager.corp_name)
            .order_by(func.count(models.Disclosure.id).desc(), models.AssetManager.corp_name.asc())
        )

        if sample_limit and sample_limit > 0 and only_disclosed:
            rows = q.having(func.count(models.Disclosure.id) > 0).limit(min(sample_limit, limit)).all()
            has_any_disclosure = any((r[2] or 0) > 0 for r in rows)
            items = [
                {
                    "corp_code": r[0],
                    "corp_name": r[1],
                    "disclosure_count": int(r[2] or 0),
                }
                for r in rows
            ]
            if not items:
                rows = q.limit(min(sample_limit, limit)).all()
                has_any_disclosure = any((r[2] or 0) > 0 for r in rows)
                items = [
                    {
                        "corp_code": r[0],
                        "corp_name": r[1],
                        "disclosure_count": int(r[2] or 0),
                    }
                    for r in rows
                ]

            return {
                "count": len(items),
                "total_count": len(items),
                "showing_all_when_no_disclosure": False,
                "sample_limit": sample_limit,
                "items": items,
                "has_any_disclosure": has_any_disclosure,
            }

        rows = q.limit(limit).all()

        has_any_disclosure = any((r[2] or 0) > 0 for r in rows)
        items = [
            {
                "corp_code": r[0],
                "corp_name": r[1],
                "disclosure_count": int(r[2] or 0),
            }
            for r in rows
        ]

        return {
            "count": len(items),
            "total_count": len(items),
            "showing_all_when_no_disclosure": False,
            "items": items,
            "has_any_disclosure": has_any_disclosure,
        }


@router.post("/jobs/{job_id}/run")
def run_job(job_id: int):
    with get_session() as sess:
        job = sess.get(models.AdminJob, job_id)
        if not job:
            return {"error": "not_found"}
        if job.status not in {"pending", "failed"}:
            return {"error": "invalid_state"}

        if job.job_type in {"reingest", "regenerate"}:
            settings = Settings()
            job.status = "running"
            ok, reason = process_disclosure_pipeline(sess, settings, DartClient(settings), int(job.target_id))
            if ok:
                job.status = "done"
                job.error_message = None
            else:
                job.status = "failed"
                job.error_message = reason
            return {"ok": ok, "reason": reason}

        return {"error": "unsupported_job"}
