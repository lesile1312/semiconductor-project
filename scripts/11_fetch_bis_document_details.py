"""Fetch official Federal Register details and full text for BIS P3 candidates."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import pandas as pd
import requests

from gtri_config import PROCESSED_DIR, RAW_DIR, append_progress, ensure_directories, utc_now


INPUT = PROCESSED_DIR / "bis_p3_candidate_events_2017_2022.csv"
DETAIL_DIR = RAW_DIR / "bis" / "documents"
MANIFEST = RAW_DIR / "bis" / "document_detail_manifest.csv"
API_TEMPLATE = "https://www.federalregister.gov/api/v1/documents/{document_number}.json"
USER_AGENT = "GTRI-research-pipeline/1.0 (academic reproducibility)"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def fetch(session: requests.Session, url: str) -> requests.Response:
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            response = session.get(url, timeout=60)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(attempt * 2)
    raise RuntimeError(f"Failed after 3 attempts: {url}: {last_error}")


def main() -> int:
    ensure_directories()
    DETAIL_DIR.mkdir(parents=True, exist_ok=True)
    source = pd.read_csv(INPUT, dtype={"document_number": "string"})
    if source["document_number"].isna().any() or source["document_number"].duplicated().any():
        raise ValueError("Candidate document_number must be complete and unique.")

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json,text/plain"})
    records: list[dict] = []
    failures: list[str] = []

    for document_number in source["document_number"].tolist():
        api_url = API_TEMPLATE.format(document_number=document_number)
        try:
            detail_response = fetch(session, api_url)
            detail = detail_response.json()
            if str(detail.get("document_number")) != document_number:
                raise ValueError("API document_number mismatch")
            detail_bytes = json.dumps(detail, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
            detail_path = DETAIL_DIR / f"{document_number}.json"
            detail_path.write_bytes(detail_bytes)

            raw_text_url = detail.get("raw_text_url")
            text_status = "not_available"
            text_path: Path | None = None
            text_sha: str | None = None
            text_bytes = b""
            if raw_text_url:
                text_response = fetch(session, raw_text_url)
                text_bytes = text_response.content
                text_path = DETAIL_DIR / f"{document_number}.txt"
                text_path.write_bytes(text_bytes)
                text_sha = sha256_bytes(text_bytes)
                text_status = "downloaded"

            records.append(
                {
                    "fetched_at_utc": utc_now(),
                    "document_number": document_number,
                    "api_url": api_url,
                    "detail_status": "downloaded",
                    "detail_path": detail_path.relative_to(RAW_DIR.parent.parent).as_posix(),
                    "detail_sha256": sha256_bytes(detail_bytes),
                    "raw_text_url": raw_text_url,
                    "raw_text_status": text_status,
                    "raw_text_path": text_path.relative_to(RAW_DIR.parent.parent).as_posix() if text_path else None,
                    "raw_text_sha256": text_sha,
                    "raw_text_bytes": len(text_bytes),
                    "source_flag": "Federal_Register_official_API_and_full_text",
                    "error": None,
                }
            )
        except Exception as exc:  # preserve per-document failures in the manifest
            failures.append(document_number)
            records.append(
                {
                    "fetched_at_utc": utc_now(),
                    "document_number": document_number,
                    "api_url": api_url,
                    "detail_status": "failed",
                    "detail_path": None,
                    "detail_sha256": None,
                    "raw_text_url": None,
                    "raw_text_status": "failed",
                    "raw_text_path": None,
                    "raw_text_sha256": None,
                    "raw_text_bytes": 0,
                    "source_flag": "Federal_Register_official_API_and_full_text",
                    "error": repr(exc),
                }
            )

    manifest = pd.DataFrame(records)
    manifest.to_csv(MANIFEST, index=False, encoding="utf-8-sig")
    append_progress(
        "BIS P3 Federal Register full-text archive",
        "complete" if not failures else "partial with recorded failures",
        [
            f"Requested {len(source)} candidate documents from the official Federal Register API.",
            f"Downloaded details for {(manifest['detail_status'] == 'downloaded').sum()} documents and full text for {(manifest['raw_text_status'] == 'downloaded').sum()} documents.",
            f"Per-file SHA-256 hashes and request URLs are recorded in {MANIFEST.as_posix()}.",
            f"Failed document numbers: {failures if failures else 'none'}.",
            "This archive supplies review evidence only and does not generate P3 scores.",
        ],
    )
    print(manifest[["document_number", "detail_status", "raw_text_status", "raw_text_bytes"]].to_string(index=False))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
