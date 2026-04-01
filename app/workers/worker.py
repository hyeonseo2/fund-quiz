from __future__ import annotations

import os
import time
from datetime import datetime

from app.core.config import Settings
from app.core.logging import setup_logging
from app.db import models
from app.db.session import get_session, init_db
from app.clients.dart_client import DartClient
from app.services.quiz_pipeline import process_disclosure_pipeline

setup_logging("INFO")
settings = Settings()


def run_once() -> int:
    with get_session() as session:
        job = session.query(models.AdminJob).filter_by(status="pending").order_by(models.AdminJob.id).first()
        if not job:
            return 0

        job.status = "running"
        job.started_at = datetime.utcnow()

        failed = False
        if job.job_type in ("reingest", "regenerate"):
            target_id = int(job.target_id)
            ok, reason = process_disclosure_pipeline(session, settings, DartClient(settings), target_id)
            if not ok:
                failed = True
                job.error_message = reason
        else:
            failed = True
            job.error_message = f"Unsupported job type: {job.job_type}"

        job.status = "done" if not failed else "failed"
        job.finished_at = datetime.utcnow()
        return 1


def main() -> None:
    # Ensure schema exists when running as long-lived worker process.
    init_db()

    run_once_mode = (os.getenv("WORKER_ONCE", "true").lower() in {"1", "true", "yes", "on"})

    if run_once_mode:
        run_once()
        return

    while True:
        processed = run_once()
        if processed == 0:
            time.sleep(settings.worker_poll_interval_sec)


if __name__ == "__main__":
    main()
