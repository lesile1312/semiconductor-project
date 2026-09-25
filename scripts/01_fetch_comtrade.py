"""Fetch reporter-reported HS8542 trade by partner from UN Comtrade."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from pathlib import Path

import requests

from gtri_config import COUNTRIES, RAW_DIR, YEARS, append_progress, ensure_directories, utc_now


API_URL = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"
REPORTERS_URL = "https://comtradeapi.un.org/files/v1/app/reference/Reporters.json"
PARTNERS_URL = "https://comtradeapi.un.org/files/v1/app/reference/partnerAreas.json"
MAX_RECORDS = 500
USER_AGENT = "GTRI-academic-research/0.1 (reproducible pipeline)"


def request_json(session: requests.Session, url: str, params: dict | None = None) -> dict:
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            response = session.get(url, params=params, timeout=120)
            if response.status_code == 429:
                time.sleep(2 ** (attempt + 1))
                continue
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Official API request failed after retries: {url}: {last_error}")


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Redownload existing raw responses")
    parser.add_argument("--delay", type=float, default=1.1, help="Seconds between API calls")
    args = parser.parse_args()
    ensure_directories()
    raw_dir = RAW_DIR / "comtrade"

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})

    try:
        reference_specs = (("reporters.json", REPORTERS_URL), ("partner_areas.json", PARTNERS_URL))
        for filename, url in reference_specs:
            path = raw_dir / filename
            if args.force or not path.exists():
                write_json(path, request_json(session, url))

        reporter_ref = json.loads((raw_dir / "reporters.json").read_text(encoding="utf-8"))["results"]
        partner_ref = json.loads((raw_dir / "partner_areas.json").read_text(encoding="utf-8"))["results"]
        reporters = {int(x["reporterCode"]): x for x in reporter_ref}
        partners = {int(x["PartnerCode"]): x for x in partner_ref}

        rows: list[dict] = []
        manifest: list[dict] = []
        for country in COUNTRIES:
            for year in YEARS:
                filename = f"{country['iso3']}_{year}_HS8542_MX.json"
                path = raw_dir / filename
                params = {
                    "period": year,
                    "reporterCode": country["comtrade"],
                    "cmdCode": "8542",
                    "flowCode": "M,X",
                    "partner2Code": 0,
                    "customsCode": "C00",
                    "motCode": 0,
                    "maxRecords": MAX_RECORDS,
                }
                if args.force or not path.exists():
                    payload = request_json(session, API_URL, params)
                    write_json(path, payload)
                    time.sleep(max(0.0, args.delay))
                else:
                    payload = json.loads(path.read_text(encoding="utf-8"))

                data = payload.get("data") or []
                count = int(payload.get("count", len(data)))
                if count != len(data):
                    raise RuntimeError(f"Record-count mismatch for {country['country']} {year}: {count} != {len(data)}")
                if count >= MAX_RECORDS:
                    raise RuntimeError(
                        f"Public endpoint may be truncated for {country['country']} {year} "
                        f"({count} records). Provide a UN Comtrade subscription key and replace "
                        "the endpoint with the authenticated full-data API before continuing."
                    )
                if not data:
                    raise RuntimeError(f"No Comtrade records for {country['country']} {year}")

                flows = {item.get("flowCode") for item in data}
                if flows != {"M", "X"}:
                    raise RuntimeError(f"Incomplete flows for {country['country']} {year}: {sorted(flows)}")

                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                manifest.append(
                    {
                        "country": country["country"], "iso3": country["iso3"], "year": year,
                        "records": count, "sha256": digest, "source_url": API_URL,
                        "query": params,
                    }
                )
                reporter_meta = reporters.get(country["comtrade"], {})
                for item in data:
                    partner_code = int(item["partnerCode"])
                    partner_meta = partners.get(partner_code, {})
                    rows.append(
                        {
                            "classification": item.get("classificationCode"),
                            "reporter_code": country["comtrade"],
                            "reporter_iso3": reporter_meta.get("reporterCodeIsoAlpha3") or country["iso3"],
                            "reporter": reporter_meta.get("reporterDesc") or country["country"],
                            "partner_code": partner_code,
                            "partner_iso3": partner_meta.get("PartnerCodeIsoAlpha3", ""),
                            "partner": partner_meta.get("PartnerDesc", f"code_{partner_code}"),
                            "partner_is_group": bool(partner_meta.get("isGroup", False)),
                            "flow": item.get("flowCode"),
                            "year": int(item.get("refYear", year)),
                            "cmd_code": str(item.get("cmdCode", "")),
                            "trade_value": item.get("primaryValue"),
                            "is_reported_api_field": item.get("isReported"),
                            "is_aggregate_api_field": item.get("isAggregate"),
                            "source_flag": "UN_Comtrade_official_public_preview_reporter_query",
                            "fetched_at_utc": utc_now(),
                        }
                    )

        csv_path = raw_dir / "comtrade_hs8542_raw.csv"
        with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        write_json(raw_dir / "fetch_manifest.json", {"generated_at_utc": utc_now(), "queries": manifest})
        append_progress(
            "UN Comtrade fetch",
            "complete",
            [
                f"Downloaded/validated {len(manifest)} reporter-year queries and {len(rows)} rows.",
                "Official public endpoint; reporter codes are the 12 study economies. Mirror reporters were not queried.",
                "Each query requested Imports+Exports and all partner areas; all were below the 500-record limit.",
                "Raw JSON, reference tables, normalized CSV, query parameters, timestamps, and SHA-256 hashes retained.",
                "The API isReported field can be false for an API-aggregated four-digit row; this does not indicate mirror trade. Reporter identity is fixed by reporterCode in every query.",
            ],
        )
        print(f"Wrote {len(rows)} rows to {csv_path}")
        return 0
    except Exception as exc:
        append_progress("UN Comtrade fetch", "FAILED", [str(exc), "No missing values were fabricated."])
        raise


if __name__ == "__main__":
    raise SystemExit(main())
