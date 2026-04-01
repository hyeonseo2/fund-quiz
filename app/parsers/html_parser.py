from __future__ import annotations

from dataclasses import dataclass
from bs4 import BeautifulSoup


@dataclass
class ParsedBlock:
    block_type: str
    section_path: str
    text: str
    table_rows: list[list[str]] | None = None


def parse_html_blocks(file_name: str, text: str) -> list[ParsedBlock]:
    soup = BeautifulSoup(text, "lxml")
    blocks: list[ParsedBlock] = []
    section_stack: list[str] = []

    def _section() -> str:
        return ">".join(section_stack) if section_stack else "문서"

    for tag in soup.find_all(["h1", "h2", "h3", "h4", "p", "li", "table"]):
        if tag.name and tag.name.startswith("h"):
            try:
                level = int(tag.name[1])
            except (TypeError, ValueError):
                level = 1
            title = tag.get_text(" ", strip=True)
            if title:
                section_stack = section_stack[: level - 1]
                section_stack.append(title)
            continue

        if tag.name == "p":
            text_line = tag.get_text(" ", strip=True)
            if text_line:
                blocks.append(ParsedBlock("paragraph", _section(), text_line))
        elif tag.name == "li":
            text_line = tag.get_text(" ", strip=True)
            if text_line:
                blocks.append(ParsedBlock("list", _section(), text_line))
        elif tag.name == "table":
            rows: list[list[str]] = []
            for tr in tag.find_all("tr"):
                cols = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
                if cols:
                    rows.append(cols)
            if rows:
                flat = "\n".join([" | ".join(r) for r in rows])
                blocks.append(ParsedBlock("table", _section(), f"[TABLE] {flat}", table_rows=rows))

    return blocks
