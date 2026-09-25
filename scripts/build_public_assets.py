"""Build browser data assets from the audited public CSV files."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def value(raw: str | None):
    if raw is None or raw == "":
        return None
    lowered = raw.strip().lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        number = float(raw)
    except (ValueError, TypeError):
        return raw
    if not math.isfinite(number):
        return None
    return int(number) if number.is_integer() else number


def read_records(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return [{key: value(item) for key, item in row.items()} for row in csv.DictReader(stream)]


def emit(path: Path, variable: str, records: list[dict], append: bool = False) -> None:
    payload = json.dumps(records, ensure_ascii=False, separators=(",", ":"))
    mode = "a" if append else "w"
    with path.open(mode, encoding="utf-8", newline="\n") as stream:
        stream.write(f"window.{variable}={payload};\n")


def preferred_path(primary: Path, archived: Path) -> Path:
    return primary if primary.is_file() else archived


def main() -> int:
    panel = read_records(preferred_path(ROOT / "output" / "master_country_year.csv", ROOT / "data" / "芯链哨兵_核心面板.csv"))
    index = read_records(preferred_path(ROOT / "output" / "pilot_gtri_v0_index.csv", ROOT / "data" / "芯链哨兵_试点指数.csv"))
    coverage = read_records(preferred_path(ROOT / "data" / "processed" / "source_coverage_by_year.csv", ROOT / "data" / "各年份数据源覆盖.csv"))
    website_coverage_years = {
        "comtrade_hs8542": {2017, 2022},
        "unga_ideal_points": {2017, 2022},
        "atop_v5_1": {2017},
        "p2_us_state_nato_2022": {2022},
        "oecd_tiva_2025": {2017, 2022},
    }
    website_coverage = [
        row for row in coverage
        if row.get("source_id") in website_coverage_years
        and int(row.get("target_year")) in website_coverage_years[row["source_id"]]
    ]
    lineage = read_records(preferred_path(ROOT / "data" / "processed" / "field_lineage.csv", ROOT / "data" / "字段级来源血缘.csv"))
    if len(panel) != 24 or len(index) != 24 or len(coverage) != 22:
        raise SystemExit(
            f"Expected 24-row panels and 22 source/year coverage rows; "
            f"got panel={len(panel)}, index={len(index)}, coverage={len(coverage)}"
        )
    keys = [(r["iso3"], r["year"]) for r in panel]
    if len(keys) != len(set(keys)):
        raise SystemExit("Duplicate economy-year keys in the public panel")
    if any(r.get("p2_us_formal_alliance") is None for r in panel):
        raise SystemExit("A core P2 value is missing; refusing to build the browser panel")
    panel_fields = set(panel[0])
    lineage_fields = [r.get("target_field") for r in lineage]
    if len(lineage_fields) != len(panel_fields) or set(lineage_fields) != panel_fields:
        raise SystemExit("Field-level source lineage does not cover the public panel exactly")
    asset = ROOT / "assets" / "panel-data.js"
    emit(asset, "PANEL", panel)
    emit(asset, "PILOT_INDEX", index, append=True)
    if len(website_coverage) != 8:
        raise SystemExit(f"Expected 8 core-source coverage rows for the overview; got {len(website_coverage)}")
    emit(ROOT / "assets" / "source-coverage-data.js", "SOURCE_COVERAGE", website_coverage)
    print(
        f"Built panel-data.js ({len(panel)} country-year rows), "
        f"source-coverage-data.js ({len(website_coverage)} core source/year rows; "
        f"full audit retains {len(coverage)} rows), "
        f"and validated lineage for {len(lineage_fields)} fields; keys unique; P2 complete."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
