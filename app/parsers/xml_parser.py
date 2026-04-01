from __future__ import annotations

from dataclasses import dataclass
from bs4 import BeautifulSoup
from xml.etree import ElementTree as ET
from lxml import etree


@dataclass
class ParsedBlock:
    block_type: str
    section_path: str
    text: str


def parse_xml_blocks(file_name: str, text: str) -> list[ParsedBlock]:
    blocks: list[ParsedBlock] = []

    def _append(text_value: str, path: str) -> None:
        value = text_value.strip()
        if value and len(value) > 1:
            blocks.append(ParsedBlock("text", path or "문서", value))

    # 1) lxml with recovery for non-strict DART XML
    try:
        root = etree.fromstring(text.encode("utf-8", errors="ignore"), parser=etree.XMLParser(recover=True))

        def walk(node, path: str) -> None:
            name = str(node.tag).split("}")[-1]
            current = f"{path}/{name}" if path else name
            value = "".join(node.itertext()).strip()
            _append(value, current)
            for child in node:
                walk(child, current)

        walk(root, "")
        if blocks:
            return blocks
    except Exception:
        pass

    # 2) fallback: BeautifulSoup parser
    soup = BeautifulSoup(text, "xml")
    for tag in soup.find_all():
        if not tag.name:
            continue
        # Skip highly structural tags that rarely carry useful statements
        if tag.name.lower() in {"document", "body", "library", "tbody", "tr", "td", "table", "colgroup", "col", "thead", "tfoot"}:
            continue
        path = tag.name
        parent = tag.parent
        ppath = []
        while parent is not None and hasattr(parent, "name") and parent.name and parent.name != "[document]":
            ppath.append(parent.name)
            parent = parent.parent
        if ppath:
            path = "/".join(reversed(ppath + [path]))

        value = tag.get_text(separator=" ", strip=True)
        _append(value, path)

    # 3) final fallback: raw text lines from ElementTree parse
    if not blocks:
        try:
            rt = ET.fromstring(text)

            def walk_raw(node: ET.Element, path: str) -> None:
                name = node.tag.split("}")[-1]
                current = f"{path}/{name}" if path else name
                if node.text and node.text.strip():
                    _append(node.text, current)
                for child in list(node):
                    walk_raw(child, current)

            walk_raw(rt, "")
        except Exception:
            pass

    return blocks
