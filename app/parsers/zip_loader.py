from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
import hashlib
import zipfile


@dataclass
class ExtractedFile:
    file_name: str
    text: str
    mime_type: str


def _is_candidate(name: str) -> bool:
    low = name.lower()
    return low.endswith(('.html', '.htm', '.xml', '.txt', '.xhtml')) and not low.startswith(('__') )


def extract_zip(storage_root: Path, rcept_no: str, zip_bytes: bytes) -> list[ExtractedFile]:
    digest = hashlib.sha256(zip_bytes).hexdigest()
    raw_dir = storage_root / "documents" / rcept_no
    zip_path = raw_dir / f"{rcept_no}_{digest}.zip"
    raw_dir.mkdir(parents=True, exist_ok=True)
    zip_path.write_bytes(zip_bytes)

    out: list[ExtractedFile] = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for zinfo in zf.infolist():
            if zinfo.is_dir() or not _is_candidate(zinfo.filename):
                continue
            with zf.open(zinfo) as fh:  # type: ignore
                try:
                    text = fh.read().decode("utf-8", errors="ignore")
                except Exception:
                    text = ""
                low = zinfo.filename.lower()
                mime = "text/xml" if low.endswith('.xml') else "text/html" if low.endswith(('.html', '.htm', '.xhtml')) else "text/plain"
                out.append(ExtractedFile(zinfo.filename, text, mime))
    return out
