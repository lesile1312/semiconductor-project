"""Validate and clean UN Comtrade HS8542 partner data."""

from __future__ import annotations

import json

import pandas as pd

from gtri_config import COUNTRIES, PROCESSED_DIR, RAW_DIR, YEARS, append_progress, ensure_directories


def main() -> int:
    ensure_directories()
    source = RAW_DIR / "comtrade" / "comtrade_hs8542_raw.csv"
    if not source.exists():
        raise FileNotFoundError("Run scripts/01_fetch_comtrade.py first")

    df = pd.read_csv(source, dtype={"partner_iso3": "string", "cmd_code": "string"})
    expected_reporters = {int(c["comtrade"]): c for c in COUNTRIES}
    anomalies: list[str] = []

    if set(df["reporter_code"].astype(int)) != set(expected_reporters):
        anomalies.append("reporter code set differs from configured 12 economies")
    if set(df["year"].astype(int)) != set(YEARS):
        anomalies.append("year set differs from 2017 and 2022")
    if set(df["flow"]) != {"M", "X"}:
        anomalies.append("flow set is not exactly Imports and Exports")
    if set(df["cmd_code"].astype(str)) != {"8542"}:
        anomalies.append("commodity code is not uniformly the four-digit HS heading 8542")
    if df["trade_value"].isna().any() or (df["trade_value"] < 0).any():
        anomalies.append("missing or negative trade values present")

    duplicate_key = ["reporter_code", "year", "flow", "partner_code"]
    duplicates = int(df.duplicated(duplicate_key).sum())
    if duplicates:
        anomalies.append(f"{duplicates} duplicate reporter-year-flow-partner rows")

    classifications = (
        df.groupby("year")["classification"].agg(lambda x: ",".join(sorted(set(x.dropna().astype(str))))).to_dict()
    )
    classification_detail = (
        df.groupby(["reporter_code", "reporter_iso3", "reporter", "year"], as_index=False)["classification"]
        .agg(lambda x: ",".join(sorted(set(x.dropna().astype(str)))))
        .sort_values(["reporter_iso3", "year"])
    )
    world = df[df["partner_code"] == 0].copy()
    world_counts = world.groupby(["reporter_code", "year", "flow"]).size()
    expected_cells = len(COUNTRIES) * len(YEARS) * 2
    if len(world_counts) != expected_cells or not (world_counts == 1).all():
        anomalies.append("World totals are not unique and complete for all reporter-year-flow cells")

    real = df[(df["partner_code"] != 0) & (~df["partner_is_group"].astype(bool))].copy()
    aggregates_removed = len(df) - len(real)
    real["trade_value"] = pd.to_numeric(real["trade_value"], errors="coerce")
    world["trade_value"] = pd.to_numeric(world["trade_value"], errors="coerce")

    partner_sums = real.groupby(["reporter_code", "year", "flow"], as_index=False)["trade_value"].sum()
    check = world.merge(partner_sums, on=["reporter_code", "year", "flow"], suffixes=("_world", "_partners"))
    check["partner_sum_over_world"] = check["trade_value_partners"] / check["trade_value_world"]
    check["absolute_gap"] = (check["trade_value_partners"] - check["trade_value_world"]).abs()
    bad_reconciliation = check[(check["partner_sum_over_world"] - 1).abs() > 1e-6]
    if len(bad_reconciliation):
        anomalies.append(f"{len(bad_reconciliation)} cells do not reconcile partner sums to World within 1e-6")

    real.to_csv(PROCESSED_DIR / "comtrade_hs8542_clean.csv", index=False, encoding="utf-8-sig")
    world.to_csv(PROCESSED_DIR / "comtrade_hs8542_world_totals.csv", index=False, encoding="utf-8-sig")
    check.to_csv(PROCESSED_DIR / "comtrade_reconciliation.csv", index=False, encoding="utf-8-sig")
    classification_detail.to_csv(
        PROCESSED_DIR / "comtrade_classification_by_reporter_year.csv", index=False, encoding="utf-8-sig"
    )
    audit = {
        "input_rows": len(df),
        "clean_partner_rows": len(real),
        "aggregate_rows_removed": aggregates_removed,
        "classifications_by_year": {str(k): v for k, v in classifications.items()},
        "anomalies": anomalies,
    }
    (PROCESSED_DIR / "comtrade_clean_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    status = "complete" if not anomalies else "FAILED"
    append_progress(
        "UN Comtrade clean",
        status,
        [
            f"Input {len(df)} rows; retained {len(real)} non-group partner-area rows; removed {aggregates_removed} World/group aggregate rows.",
            f"Reported classifications by year: {classifications}. HS code is exactly 8542 in every retained row.",
            "Classification revision is retained at reporter-year level in comtrade_classification_by_reporter_year.csv; no revision-specific six-digit subheading is mixed into the four-digit heading.",
            f"Partner-sum reconciliation range: {check['partner_sum_over_world'].min():.12f} to {check['partner_sum_over_world'].max():.12f}.",
            "Non-group statistical partner areas such as Other Asia, nes are retained; removing them would discard reported trade (including the Taiwan reporting area).",
            *(anomalies or ["No missing, duplicate, negative-value, flow, reporter, or denominator anomalies detected."]),
        ],
    )
    if anomalies:
        raise RuntimeError("Comtrade cleaning validation failed: " + "; ".join(anomalies))
    print(f"Wrote {len(real)} cleaned partner rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
