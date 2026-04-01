from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import requests
import time
from xml.etree import ElementTree as ET

from app.core.config import Settings

BASE_URL = "https://opendart.fss.or.kr/api"


class DartAPIError(RuntimeError):
    pass


@dataclass
class DartListItem:
    rcept_no: str
    report_nm: str
    corp_code: str
    corp_name: str
    rcept_dt: str
    pblntf_ty: str | None = None
    pblntf_detail_ty: str | None = None
    flr_nm: str | None = None


class DartClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session = requests.Session()

    def _get(self, url: str, params: dict[str, Any]) -> requests.Response:
        if not self.settings.opendart_api_key:
            raise DartAPIError("OPENDART_API_KEY is not configured")
        p = {"crtfc_key": self.settings.opendart_api_key, **params}
        attempt = 0
        while True:
            attempt += 1
            try:
                resp = self.session.get(url, params=p, timeout=self.settings.request_timeout_sec)
                if resp.status_code == 200:
                    return resp
                if resp.status_code in (429, 500, 502, 503, 504):
                    if attempt <= self.settings.request_retries:
                        time.sleep(min(2 ** attempt, 8))
                        continue
                raise DartAPIError(f"DART request failed {resp.status_code}: {resp.text[:200]}")
            except requests.RequestException as e:
                if attempt <= self.settings.request_retries:
                    time.sleep(min(2 ** attempt, 8))
                    continue
                raise DartAPIError(f"DART request error: {e}")

    def fetch_corp_codes(self) -> list[tuple[str, str]]:
        url = f"{BASE_URL}/corpCode.xml"
        resp = self._get(url, {})

        # Open DART returns a zip file for this endpoint.
        # We support both direct XML and zipped payload for robustness.
        content = resp.content
        xml_text = None

        if content[:2] == b"PK":
            import io
            import zipfile

            zf = zipfile.ZipFile(io.BytesIO(content))
            candidates = [n for n in zf.namelist() if n.lower().endswith(".xml")]
            if not candidates:
                raise DartAPIError("corpCode.xml zip payload did not contain any XML file")
            xml_text = zf.read(candidates[0]).decode("utf-8", errors="ignore")
        else:
            xml_text = content.decode("utf-8", errors="ignore")

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            raise DartAPIError(f"Failed to parse corpCode.xml: {e}")

        result: list[tuple[str, str]] = []
        for item in root.findall("list"):
            code = (item.findtext("corp_code") or "").strip()
            name = (item.findtext("corp_name") or "").strip()
            if code and name:
                result.append((code, name))
        return result

    def fetch_list_json(
        self,
        *,
        corp_code: str,
        bgn_de: str,
        end_de: str,
        page_no: int = 1,
        page_count: int = 100,
        last_reprt_at: str = "Y",
        pblntf_ty: str = "G",
    ) -> list[DartListItem]:
        url = f"{BASE_URL}/list.json"
        params = {
            "corp_code": corp_code,
            "bgn_de": bgn_de,
            "end_de": end_de,
            "page_no": page_no,
            "page_count": page_count,
            "last_reprt_at": last_reprt_at,
            "pblntf_ty": pblntf_ty,
            "sort": "date",
            "sort_mth": "desc",
        }
        resp = self._get(url, params)
        payload = resp.json()
        status = payload.get("status")
        message = payload.get("message", "")
        if status == "013":
            return []
        if status != "000":
            raise DartAPIError(f"list.json error {status}: {message}")
        items = payload.get("list") or []
        out: list[DartListItem] = []
        for row in items:
            out.append(
                DartListItem(
                    rcept_no=row["rcept_no"],
                    report_nm=row["report_nm"],
                    corp_code=row["corp_code"],
                    corp_name=row["corp_name"],
                    rcept_dt=row["rcept_dt"],
                    pblntf_ty=row.get("pblntf_ty"),
                    pblntf_detail_ty=row.get("pblntf_detail_ty"),
                    flr_nm=row.get("flr_nm"),
                )
            )
        return out

    def download_document_zip(self, rcept_no: str) -> bytes:
        url = f"{BASE_URL}/document.xml"
        resp = self._get(url, {"rcept_no": rcept_no})
        if "application/json" in resp.headers.get("content-type", ""):
            body = resp.json()
            if body.get("status") and body["status"] != "000":
                raise DartAPIError(f"document.xml error {body.get('status')}: {body.get('message')}")
        return resp.content
