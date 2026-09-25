"""Fetch OECD TiVA electronic-industry foreign-value-added share (N1)."""

from __future__ import annotations

import hashlib
import json
from io import StringIO

import pandas as pd
import requests

from gtri_config import COUNTRIES, PROCESSED_DIR, RAW_DIR, YEARS, append_progress, ensure_directories, utc_now


DATAFLOW = "OECD.STI.PIE,DSD_TIVA_MAINSH@DF_MAINSH,1.1"
API_BASE = "https://sdmx.oecd.org/sti-public/rest/v1/data/"
CURRENT_MEASURE = "EXGR_FVA"
LEGACY_MEASURE = "EXGR_FVASH"
ACTIVITY = "C26_27"
COUNTERPART = "W"
UNIT = "PT_EXGR"
FREQUENCY = "A"


def main() -> int:
    ensure_directories()
    raw_dir = RAW_DIR / "tiva"
    iso3s = "+".join(country["iso3"] for country in COUNTRIES)
    key = f"{CURRENT_MEASURE}.{iso3s}.{ACTIVITY}.{COUNTERPART}.{UNIT}.{FREQUENCY}"
    url = f"{API_BASE}{DATAFLOW}/{key}"
    params = {"startPeriod": min(YEARS), "endPeriod": max(YEARS), "dimensionAtObservation": "AllDimensions"}
    raw_path = raw_dir / "oecd_tiva_exgr_fva_c26_27.csv"
    try:
        response = requests.get(
            url,
            params=params,
            headers={"Accept": "text/csv", "User-Agent": "GTRI-academic-research/0.2"},
            timeout=180,
        )
        response.raise_for_status()
        raw_path.write_bytes(response.content)
        raw = pd.read_csv(StringIO(response.text))
        required = {"MEASURE", "REF_AREA", "ACTIVITY", "COUNTERPART_AREA", "UNIT_MEASURE", "FREQ", "TIME_PERIOD", "OBS_VALUE"}
        if not required.issubset(raw.columns):
            raise RuntimeError(f"Unexpected TiVA response columns: missing {sorted(required - set(raw.columns))}")
        raw["TIME_PERIOD"] = pd.to_numeric(raw["TIME_PERIOD"], errors="raise").astype(int)
        raw["OBS_VALUE"] = pd.to_numeric(raw["OBS_VALUE"], errors="raise")
        filtered = raw[raw["TIME_PERIOD"].isin(YEARS)].copy()
        expected_keys = {(country["iso3"], year) for country in COUNTRIES for year in YEARS}
        observed_keys = set(zip(filtered["REF_AREA"], filtered["TIME_PERIOD"]))
        if observed_keys != expected_keys:
            missing = sorted(expected_keys - observed_keys)
            extra = sorted(observed_keys - expected_keys)
            raise RuntimeError(f"TiVA coverage mismatch; missing={missing}, extra={extra}")
        if filtered.duplicated(["REF_AREA", "TIME_PERIOD"]).any():
            raise RuntimeError("Duplicate TiVA country-year observations")
        if not (
            (filtered["MEASURE"] == CURRENT_MEASURE)
            & (filtered["ACTIVITY"] == ACTIVITY)
            & (filtered["COUNTERPART_AREA"] == COUNTERPART)
            & (filtered["UNIT_MEASURE"] == UNIT)
            & (filtered["FREQ"] == FREQUENCY)
        ).all():
            raise RuntimeError("TiVA response does not match requested indicator dimensions")

        country_names = {country["iso3"]: country["country"] for country in COUNTRIES}
        output = filtered.rename(columns={"REF_AREA": "iso3", "TIME_PERIOD": "year", "OBS_VALUE": "n1_electronics_foreign_va_share"})[
            ["iso3", "year", "n1_electronics_foreign_va_share"]
        ].copy()
        output.insert(0, "country", output["iso3"].map(country_names))
        output["source_measure"] = CURRENT_MEASURE
        output["legacy_measure_name"] = LEGACY_MEASURE
        output["activity"] = ACTIVITY
        output["counterpart_area"] = COUNTERPART
        output["unit_measure"] = UNIT
        output["source_flag"] = "OECD_TiVA_2025_SDMX"
        output = output.sort_values(["country", "year"])
        output.to_csv(PROCESSED_DIR / "tiva_n1_country_year.csv", index=False, encoding="utf-8-sig")
        metadata = {
            "downloaded_at_utc": utc_now(),
            "source_url": response.url,
            "dataflow": DATAFLOW,
            "api_measure": CURRENT_MEASURE,
            "legacy_measure_name": LEGACY_MEASURE,
            "definition": "Foreign value added in gross exports as a percentage of gross exports",
            "activity": "C26_27: computer, electronic and electrical equipment",
            "counterpart_area": "W: World",
            "unit": "PT_EXGR: percent of gross exports",
            "sha256": hashlib.sha256(response.content).hexdigest(),
        }
        (raw_dir / "source_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        append_progress(
            "OECD TiVA / N1",
            "complete",
            [
                "Downloaded the official OECD TiVA 2025 SDMX response for all 12 economies; raw CSV, exact API URL, and SHA-256 are retained.",
                "N1 is EXGR_FVA with unit PT_EXGR, the current SDMX representation of the legacy EXGR_FVASH concept: foreign value added in gross exports as a share of gross exports.",
                "Industry C26_27 is computer, electronic and electrical equipment; counterpart W is World.",
                f"Validated complete, unique coverage for {len(output)} country-year observations with no imputation.",
            ],
        )
        print(output.to_string(index=False))
        return 0
    except Exception as exc:
        append_progress("OECD TiVA / N1", "FAILED", [str(exc), "No missing values were fabricated."])
        raise


if __name__ == "__main__":
    raise SystemExit(main())
