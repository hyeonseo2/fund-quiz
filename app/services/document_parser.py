from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.normalizers.fund_name import normalize_name
from app.parsers.html_parser import parse_html_blocks
from app.parsers.xml_parser import parse_xml_blocks


@dataclass
class ParsedBlockPayload:
    block_type: str
    section_path: str
    text: str
    table_json: list[list[str]] | None
    char_start: int
    char_end: int
    source_locator: dict[str, Any]


def parse_document_files(files: list[tuple[str, str]]) -> list[ParsedBlockPayload]:
    out: list[ParsedBlockPayload] = []
    cursor = 0

    for idx, (file_name, text) in enumerate(files):
        low = file_name.lower()
        if low.endswith((".html", ".htm", ".xhtml")):
            blocks = parse_html_blocks(file_name, text)
            for b in blocks:
                normalized = normalize_name(b.text)
                if not normalized:
                    continue
                start = cursor
                end = cursor + len(b.text)
                cursor = end
                out.append(
                    ParsedBlockPayload(
                        block_type=b.block_type,
                        section_path=f"{file_name}::{b.section_path}",
                        text=b.text.strip(),
                        table_json=b.table_rows if b.table_rows else None,
                        char_start=start,
                        char_end=end,
                        source_locator={"block_index": len(out), "file_name": file_name},
                    )
                )
        elif low.endswith(".xml"):
            blocks = parse_xml_blocks(file_name, text)
            for b in blocks:
                normalized = normalize_name(b.text)
                if not normalized:
                    continue
                start = cursor
                end = cursor + len(b.text)
                cursor = end
                out.append(
                    ParsedBlockPayload(
                        block_type=b.block_type,
                        section_path=f"{file_name}::{b.section_path}",
                        text=b.text.strip(),
                        table_json=None,
                        char_start=start,
                        char_end=end,
                        source_locator={"block_index": len(out), "file_name": file_name},
                    )
                )
        else:
            # txt / 기타 텍스트
            for i, line in enumerate(text.splitlines()):
                if not line.strip():
                    continue
                normalized = normalize_name(line)
                if not normalized:
                    continue
                start = cursor
                end = cursor + len(line)
                cursor = end
                out.append(
                    ParsedBlockPayload(
                        block_type="paragraph",
                        section_path=f"{file_name}::본문",
                        text=line.strip(),
                        table_json=None,
                        char_start=start,
                        char_end=end,
                        source_locator={"block_index": len(out), "file_name": file_name, "line_no": i},
                    )
                )

    return out
