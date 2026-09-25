"""Build an auditable BIS historical-rule event intake table for P3.

This script deliberately does not generate a country score.  A historical rule
may target China, named entities, an end use, or a technology class, and a
defensible mapping from that legal scope to third-country exposure requires a
separate, pre-specified coding protocol.
"""

from __future__ import annotations

import hashlib
import json

import pandas as pd
import requests

from gtri_config import PROCESSED_DIR, RAW_DIR, YEARS, append_progress, ensure_directories, utc_now


FR_API = "https://www.federalregister.gov/api/v1/documents.json"
AGENCY = "industry-and-security-bureau"
DIRECT_TERMS = ("semiconductor", "advanced computing", "supercomputer", "integrated circuit", "microelectronic")
ENTITY_TERM = "entity list"


def candidate_class(text: str) -> tuple[bool, str, str]:
    lowered = text.lower()
    direct = [term for term in DIRECT_TERMS if term in lowered]
    if direct:
        return True, "direct_semiconductor_or_advanced_computing", "; ".join(direct)
    if ENTITY_TERM in lowered:
        return True, "entity_list_requires_manual_semiconductor_coding", ENTITY_TERM
    return False, "not_candidate", ""


def main() -> int:
    ensure_directories()
    raw_dir = RAW_DIR / "bis"
    raw_dir.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict] = []
    manifest: list[dict] = []
    try:
        for year in YEARS:
            params = {
                "conditions[agencies][]": AGENCY,
                "conditions[publication_date][year]": str(year),
                "per_page": "1000",
                "order": "oldest",
            }
            response = requests.get(FR_API, params=params, headers={"User-Agent": "GTRI-academic-research/0.2"}, timeout=180)
            response.raise_for_status()
            payload = response.json()
            path = raw_dir / f"bis_federal_register_{year}.json"
            path.write_bytes(response.content)
            docs = payload.get("results", [])
            if int(payload.get("count", len(docs))) != len(docs):
                raise RuntimeError(f"Federal Register response pagination mismatch for {year}")
            manifest.append({"year": year, "records": len(docs), "url": response.url, "sha256": hashlib.sha256(response.content).hexdigest()})
            for doc in docs:
                title = doc.get("title", "")
                abstract = doc.get("abstract", "") or ""
                is_candidate, candidate_type, matched_terms = candidate_class(f"{title} {abstract}")
                all_rows.append(
                    {
                        "event_year": year,
                        "publication_date": doc.get("publication_date"),
                        "document_number": doc.get("document_number"),
                        "document_type": doc.get("type"),
                        "title": title,
                        "abstract": abstract,
                        "html_url": doc.get("html_url"),
                        "pdf_url": doc.get("pdf_url"),
                        "is_p3_candidate": is_candidate,
                        "candidate_type": candidate_type,
                        "matched_terms": matched_terms,
                        "country_target": pd.NA,
                        "country_target_coding_status": "not_coded",
                        "semiconductor_related_manual_status": "not_manually_coded",
                        "severity": pd.NA,
                        "severity_coding_status": "not_coded",
                        "source_flag": "Federal_Register_BIS_agency_archive",
                    }
                )
        universe = pd.DataFrame(all_rows).sort_values(["event_year", "publication_date", "document_number"])
        candidates = universe[universe["is_p3_candidate"]].copy()
        universe.to_csv(PROCESSED_DIR / "bis_rule_universe_2017_2022.csv", index=False, encoding="utf-8-sig")
        candidates.to_csv(PROCESSED_DIR / "bis_p3_candidate_events_2017_2022.csv", index=False, encoding="utf-8-sig")
        (raw_dir / "fetch_manifest.json").write_text(
            json.dumps({"downloaded_at_utc": utc_now(), "queries": manifest}, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        direct_count = int((candidates["candidate_type"] == "direct_semiconductor_or_advanced_computing").sum())
        entity_count = int((candidates["candidate_type"] == "entity_list_requires_manual_semiconductor_coding").sum())
        append_progress(
            "BIS historical-rule intake / P3",
            "complete as evidence table; country score intentionally not generated",
            [
                f"Downloaded the complete BIS-agency Federal Register universe for 2017 and 2022: {len(universe)} documents.",
                f"Flagged {len(candidates)} transparent keyword candidates: {direct_count} direct semiconductor/advanced-computing and {entity_count} Entity List candidates requiring manual semiconductor coding.",
                "Each candidate retains publication date, document number, title, abstract, HTML/PDF source URLs, and unfilled country/severity coding fields.",
                "P3 is not merged into master_country_year.csv: no country-target or severity score is inferred from legal text without a pre-specified mapping protocol.",
            ],
        )
        print(candidates[["event_year", "publication_date", "document_number", "candidate_type", "title"]].to_string(index=False))
        return 0
    except Exception as exc:
        append_progress("BIS historical-rule intake / P3", "FAILED", [str(exc), "No P3 score or missing value was fabricated."])
        raise


if __name__ == "__main__":
    raise SystemExit(main())
