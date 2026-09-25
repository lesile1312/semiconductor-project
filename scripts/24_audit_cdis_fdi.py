"""Audit and summarize the supplied IMF CDIS context layer without scoring it."""

from __future__ import annotations

import shutil

import numpy as np
import pandas as pd

from gtri_config import COUNTRIES, OUTPUT_DIR, PROCESSED_DIR, PROJECT_ROOT, append_progress, ensure_directories


INPUT = PROCESSED_DIR / "cdis_china_fdi_key_years.csv"
AUDIT = PROCESSED_DIR / "cdis_fdi_quality_audit.csv"
SUMMARY = PROCESSED_DIR / "cdis_fdi_candidate_exposure_summary.csv"


def main() -> int:
    ensure_directories()
    if not INPUT.is_file():
        raise FileNotFoundError("Run scripts/23_process_cdis_key_years.py first")
    panel = pd.read_csv(INPUT)
    required = {"year", "country", "iso3", "flow", "value_usd_millions", "source_artifact", "source_sha256"}
    if not required.issubset(panel.columns):
        raise RuntimeError(f"Unexpected CDIS source schema; missing {sorted(required - set(panel.columns))}")
    if panel.duplicated(["year", "iso3", "flow"]).any():
        raise RuntimeError("Duplicate CDIS observation at year/ISO/flow grain")

    expected = {
        (year, economy["country"], economy["iso3"], flow)
        for year in (2017, 2021)
        for economy in COUNTRIES
        for flow in ("china_inward_fdi_usd_millions", "china_outward_fdi_usd_millions")
    }
    observed = set(map(tuple, panel[["year", "country", "iso3", "flow"]].itertuples(index=False, name=None)))
    if observed != expected:
        raise RuntimeError(f"CDIS key coverage mismatch; missing={len(expected - observed)} extra={len(observed - expected)}")

    panel["missing_or_nonreported"] = panel["value_usd_millions"].isna()
    panel["negative_value"] = panel["value_usd_millions"].lt(0)
    panel["extreme_over_10000_usd_millions"] = panel["value_usd_millions"].gt(10000)
    panel["log1p_value_if_reported"] = np.log1p(panel["value_usd_millions"].clip(lower=0))
    panel.to_csv(AUDIT, index=False, encoding="utf-8-sig")

    id_fields = panel[["year", "country", "iso3"]].drop_duplicates()
    values = panel.pivot(
        index=["year", "country", "iso3"], columns="flow", values="value_usd_millions"
    ).reset_index()
    values.columns.name = None
    summary = id_fields.merge(values, on=["year", "country", "iso3"], validate="one_to_one")
    summary = summary.rename(
        columns={
            "china_inward_fdi_usd_millions": "china_inward_fdi_usd_millions",
            "china_outward_fdi_usd_millions": "china_outward_fdi_usd_millions",
        }
    )
    artifact_notes = (
        panel.groupby(["year", "country"], as_index=False)
        .agg(source_artifacts=("source_artifact", lambda values: " | ".join(sorted(set(values)))),
             source_hashes=("source_sha256", lambda values: " | ".join(sorted(set(values)))))
    )
    summary = summary.merge(artifact_notes, on=["year", "country"], validate="one_to_one")
    summary["any_reported_fdi"] = summary[
        ["china_inward_fdi_usd_millions", "china_outward_fdi_usd_millions"]
    ].notna().any(axis=1)
    summary["source_flag"] = "IMF_CDIS_reporter_positions_by_immediate_counterpart"
    summary["source_coverage_note"] = (
        "IMF CDIS supplied workbooks; end-year positions by immediate counterpart; 2017 and 2021 only; "
        "not semiconductor-specific; inward and outward reporting sides remain separate."
    )
    summary = summary.sort_values(["year", "country"])
    summary.to_csv(SUMMARY, index=False, encoding="utf-8-sig")

    public = PROJECT_ROOT / "outputs"
    public.mkdir(exist_ok=True)
    shutil.copy2(AUDIT, public / AUDIT.name)
    shutil.copy2(SUMMARY, public / SUMMARY.name)
    missing = int(panel["missing_or_nonreported"].sum())
    negative = int(panel["negative_value"].sum())
    extreme = int(panel["extreme_over_10000_usd_millions"].sum())
    append_progress(
        "CDIS FDI quality audit",
        "complete as optional non-scoring context",
        [
            f"Audited {len(panel)} unique economy-year-flow records and produced {len(summary)} country-year summaries with ISO3 keys.",
            f"Missing/nonreported cells: {missing}; negative positions: {negative}; positions above USD 10,000 million: {extreme}.",
            "Values are position stocks reported by immediate counterpart, not flows or ultimate-owner measures; financial-center effects and reporting asymmetry remain relevant.",
            "Input provenance uses project-relative artifact paths and SHA-256 hashes; no source-machine attachment path is retained.",
            "This module is context only: no FDI score is merged into GTRI, and 2022 uses 2021 only as a labelled lagged observation.",
        ],
    )
    print(f"CDIS audited_rows={len(panel)}; summaries={len(summary)}; missing={missing}; negative={negative}; extreme={extreme}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
