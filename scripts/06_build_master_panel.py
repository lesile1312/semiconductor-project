"""Build a country-year panel with source-aware core and evidence layers."""

from __future__ import annotations

import pandas as pd

from gtri_config import COUNTRIES, OUTPUT_DIR, PROCESSED_DIR, RAW_DIR, YEARS, append_progress, ensure_directories


KEYS = ["country", "iso3", "year"]


def require_unique(df: pd.DataFrame, keys: list[str], label: str) -> None:
    if df.duplicated(keys).any():
        examples = df.loc[df.duplicated(keys, keep=False), keys].head(6).to_dict("records")
        raise RuntimeError(f"{label} has duplicate keys {keys}: {examples}")


def require_exact_keys(df: pd.DataFrame, base: pd.DataFrame, keys: list[str], label: str) -> None:
    observed = set(map(tuple, df[keys].itertuples(index=False, name=None)))
    expected = set(map(tuple, base[keys].itertuples(index=False, name=None)))
    if observed != expected:
        raise RuntimeError(
            f"{label} key coverage mismatch; missing={sorted(expected - observed)[:8]}, "
            f"extra={sorted(observed - expected)[:8]}"
        )


def main() -> int:
    ensure_directories()
    required_files = {
        "trade": PROCESSED_DIR / "trade_metrics_all_years.csv",
        "unga": PROCESSED_DIR / "unga_p1_country_year.csv",
        "atop": PROCESSED_DIR / "atop_p2_country_year.csv",
        "tiva": PROCESSED_DIR / "tiva_n1_country_year.csv",
        "p3": PROCESSED_DIR / "bis_p3_country_year_reviewed_summary.csv",
        "cdis": PROCESSED_DIR / "cdis_fdi_candidate_exposure_summary.csv",
        "p2_2022": RAW_DIR / "p2" / "p2_official_2022_source.csv",
    }
    missing_files = [str(path) for path in required_files.values() if not path.exists()]
    if missing_files:
        raise FileNotFoundError("Required source modules missing; run their processing scripts first: " + ", ".join(missing_files))

    base = pd.DataFrame(
        [{"country": economy["country"], "iso3": economy["iso3"], "year": year}
         for economy in COUNTRIES for year in YEARS]
    )
    require_unique(base, KEYS, "expected panel")

    trade = pd.read_csv(required_files["trade"]).rename(
        columns={
            "N2": "n2_china_hs8542_import_share",
            "N3": "n3_us_hs8542_export_share",
            "N4": "n4_dual_dependency",
            "V1": "v1_hs8542_import_hhi",
            "V2": "v2_effective_supplier_count",
            "source_flag": "trade_source_flag",
        }
    )
    unga = pd.read_csv(required_files["unga"]).rename(columns={"source_flag": "unga_source_flag"})
    atop = pd.read_csv(required_files["atop"]).rename(
        columns={
            "p2_us_formal_alliance": "p2_atop_observed",
            "p2_us_formal_alliance_structural_2018": "p2_atop_structural_2018",
            "p2_source_year": "p2_atop_source_year",
            "source_flag": "atop_source_flag",
            "notes": "atop_notes",
        }
    )
    tiva = pd.read_csv(required_files["tiva"]).rename(columns={"source_flag": "tiva_source_flag"})
    for label, module in (("trade", trade), ("UNGA", unga), ("ATOP", atop), ("TiVA", tiva)):
        require_unique(module, KEYS, label)
        require_exact_keys(module, base, KEYS, label)

    panel = base.copy()
    for label, module in (("trade", trade), ("UNGA", unga), ("ATOP", atop), ("TiVA", tiva)):
        panel = panel.merge(module, on=KEYS, how="left", validate="one_to_one", indicator=f"_{label}_merge")
        if not panel[f"_{label}_merge"].eq("both").all():
            raise RuntimeError(f"{label} did not join to every country-year row")
        panel = panel.drop(columns=f"_{label}_merge")

    # P2 uses target-year sources, never an ATOP 2018 value mislabeled as a 2022 observation.
    p2_2022 = pd.read_csv(required_files["p2_2022"])
    expected_countries = {(economy["country"], economy["iso3"]) for economy in COUNTRIES}
    if p2_2022.duplicated(["country", "iso3"]).any() or len(p2_2022) != len(COUNTRIES):
        raise RuntimeError("Official 2022 P2 coding file must contain one row per sample economy")
    if set(zip(p2_2022["country"], p2_2022["iso3"])) != expected_countries:
        raise RuntimeError("Official 2022 P2 coding file does not match the 12-economy sample")
    p2_2022["year"] = pd.to_numeric(p2_2022["year"], errors="raise").astype(int)
    p2_2022["p2_official_active_defense_tie"] = pd.to_numeric(
        p2_2022["p2_official_active_defense_tie"], errors="raise"
    )
    if not p2_2022["year"].eq(2022).all() or not p2_2022["p2_official_active_defense_tie"].isin([0, 1]).all():
        raise RuntimeError("Official P2 values must be binary and explicitly dated 2022")
    p2_2022 = p2_2022.rename(
        columns={
            "p2_official_active_defense_tie": "p2_official_2022",
            "treaty_or_basis": "p2_official_treaty_or_basis",
            "source_url": "p2_official_source_url",
            "coding_note": "p2_official_coding_note",
        }
    ).drop(columns="year")
    panel = panel.merge(p2_2022, on=["country", "iso3"], how="left", validate="many_to_one")
    panel.loc[panel["year"] != 2022, "p2_official_2022"] = pd.NA

    panel["p2_us_formal_alliance"] = pd.NA
    panel["p2_source_year"] = pd.NA
    panel["p2_measurement_source"] = ""
    panel["p2_evidence_source_url"] = ""
    panel["p2_treaty_or_basis"] = ""
    panel["p2_coding_note"] = ""
    panel["p2_oas_adjustment"] = False
    for index, row in panel.iterrows():
        if int(row["year"]) == 2017:
            if pd.isna(row["p2_atop_observed"]):
                raise RuntimeError(f"ATOP 2017 P2 missing for {row['country']}")
            value = int(row["p2_atop_observed"])
            panel.at[index, "p2_source_year"] = 2017
            panel.at[index, "p2_measurement_source"] = "ATOP_v5.1_observed"
            panel.at[index, "p2_evidence_source_url"] = "https://www.atopdata.org/"
            panel.at[index, "p2_treaty_or_basis"] = "ATOP US dyad defense-obligation field"
            panel.at[index, "p2_coding_note"] = "ATOP observed defense obligation with the United States."
            if row["iso3"] == "MEX":
                if value != 1:
                    raise RuntimeError("Expected the documented raw ATOP Mexico value 1 before the OAS status correction")
                value = 0
                panel.at[index, "p2_measurement_source"] = "ATOP_v5.1_observed_plus_OAS_treaty_status_audit"
                panel.at[index, "p2_evidence_source_url"] = "https://www.oas.org/juridico/english/sigs/b-29.html"
                panel.at[index, "p2_treaty_or_basis"] = "Rio Treaty; OAS records cessation for Mexico on 2004-09-06"
                panel.at[index, "p2_coding_note"] = "Raw ATOP is 1; audited active-treaty value is 0 because the Rio Treaty ceased for Mexico in 2004."
                panel.at[index, "p2_oas_adjustment"] = True
            panel.at[index, "p2_us_formal_alliance"] = value
        else:
            if pd.isna(row["p2_official_2022"]):
                raise RuntimeError(f"Official 2022 P2 missing for {row['country']}")
            panel.at[index, "p2_us_formal_alliance"] = int(row["p2_official_2022"])
            panel.at[index, "p2_source_year"] = 2022
            panel.at[index, "p2_measurement_source"] = "US_State_TIF_2020_plus_2021_2023_supplement_and_2022_official_coding"
            panel.at[index, "p2_evidence_source_url"] = row["p2_official_source_url"]
            panel.at[index, "p2_treaty_or_basis"] = row["p2_official_treaty_or_basis"]
            panel.at[index, "p2_coding_note"] = row["p2_official_coding_note"]

    # P3 is a selected-rule evidence overlay. Zeros are scoped to that reviewed set.
    p3 = pd.read_csv(required_files["p3"])
    p3 = p3.rename(
        columns={
            "reviewed_candidate_literal_count": "p3_reviewed_candidate_literal_count",
            "direct_semiconductor_increase_events": "p3_bis_direct_increase_events_reviewed_subset",
            "p3_direct_increase_within_reviewed_subset": "p3_bis_direct_increase_flag_reviewed_subset",
            "scope": "p3_scope",
            "scoring_status": "p3_scoring_status",
            "notes": "p3_notes",
        }
    )
    require_unique(p3, KEYS, "BIS P3 reviewed-candidate summary")
    require_exact_keys(p3, base, KEYS, "BIS P3 reviewed-candidate summary")
    panel = panel.merge(p3, on=KEYS, how="left", validate="one_to_one")
    panel["p3_coverage_note"] = (
        "Selected manually reviewed candidate rules only; zero is not evidence of no exposure outside the reviewed set."
    )

    # CDIS is aligned to the target year without disguising its source observation year.
    cdis = pd.read_csv(required_files["cdis"])
    cdis["year"] = pd.to_numeric(cdis["year"], errors="raise").astype(int)
    cdis["target_year"] = cdis["year"].map({2017: 2017, 2021: 2022})
    if cdis["target_year"].isna().any():
        raise RuntimeError("CDIS has a year outside the documented 2017/2021-to-target-year mapping")
    cdis = cdis.rename(
        columns={
            "year": "cdis_observation_year",
            "china_inward_fdi_usd_millions": "cdis_sample_country_inward_from_china_usd_millions",
            "china_outward_fdi_usd_millions": "cdis_china_outward_position_in_sample_country_usd_millions",
            "any_reported_fdi": "cdis_any_direction_reported",
            "source_coverage_note": "cdis_coverage_note",
        }
    )
    cdis["year"] = cdis["target_year"].astype(int)
    cdis["cdis_observation_lag_years"] = cdis["year"] - cdis["cdis_observation_year"]
    cdis = cdis.drop(columns="target_year")
    require_unique(cdis, KEYS, "IMF CDIS context layer")
    require_exact_keys(cdis, base, KEYS, "IMF CDIS context layer")
    panel = panel.merge(cdis, on=KEYS, how="left", validate="one_to_one")
    panel["cdis_inward_value_reported"] = panel["cdis_sample_country_inward_from_china_usd_millions"].notna()
    panel["cdis_outward_value_reported"] = panel["cdis_china_outward_position_in_sample_country_usd_millions"].notna()
    panel["cdis_score_status"] = "non_scoring_context"
    panel["cdis_direction_note"] = (
        "Separate inward positions reported by the sample economy and outward positions reported by China; "
        "immediate counterpart, not ultimate owner, not semiconductor-specific."
    )

    core_fields = [
        "p1_unga_relative_alignment", "p2_us_formal_alliance", "n1_electronics_foreign_va_share",
        "n2_china_hs8542_import_share", "n3_us_hs8542_export_share", "n4_dual_dependency",
        "v1_hs8542_import_hhi", "v2_effective_supplier_count",
    ]
    missing_flags: list[str] = []
    context_missing_flags: list[str] = []
    source_flags: list[str] = []
    notes: list[str] = []
    for _, row in panel.iterrows():
        absent_core = [field for field in core_fields if pd.isna(row[field])]
        missing_flags.append("none" if not absent_core else "missing:" + ",".join(absent_core))
        absent_context = []
        if pd.isna(row["cdis_sample_country_inward_from_china_usd_millions"]):
            absent_context.append("cdis_inward")
        if pd.isna(row["cdis_china_outward_position_in_sample_country_usd_millions"]):
            absent_context.append("cdis_outward")
        context_missing_flags.append("none" if not absent_context else "not_reported:" + ",".join(absent_context))

        sources = [
            row.get("trade_source_flag"), row.get("unga_source_flag"), row.get("atop_source_flag"),
            row.get("tiva_source_flag"), row.get("p2_measurement_source"),
            "BIS_Federal_Register_selected_manual_review_evidence",
            "IMF_CDIS_non_scoring_context",
        ]
        source_flags.append(" | ".join(dict.fromkeys(
            str(value) for value in sources if pd.notna(value) and str(value).strip()
        )))
        row_notes = []
        if str(row.get("p2_coding_note", "")).strip():
            row_notes.append(str(row["p2_coding_note"]))
        if int(row["cdis_observation_lag_years"]) == 1:
            row_notes.append("CDIS context uses nearest supplied pre-target observation year 2021; one-year lag.")
        notes.append("; ".join(row_notes))

    panel["source_flag"] = source_flags
    panel["missing_flag"] = missing_flags
    panel["context_missing_flag"] = context_missing_flags
    panel["notes"] = notes
    ordered = [
        "country", "iso3", "year", "p1_unga_relative_alignment",
        "p2_us_formal_alliance", "p2_source_year", "p2_measurement_source", "p2_evidence_source_url",
        "p2_treaty_or_basis", "p2_coding_note", "p2_oas_adjustment", "p2_atop_observed",
        "p2_atop_source_year", "p2_atop_structural_2018", "p2_official_2022",
        "n1_electronics_foreign_va_share", "n2_china_hs8542_import_share", "n3_us_hs8542_export_share",
        "n4_dual_dependency", "v1_hs8542_import_hhi", "v2_effective_supplier_count",
        "avg_distance_to_china", "avg_distance_to_us", "window_start", "window_end",
        "p3_reviewed_candidate_literal_count", "p3_bis_direct_increase_events_reviewed_subset",
        "p3_bis_direct_increase_flag_reviewed_subset", "p3_scope", "p3_scoring_status", "p3_notes",
        "p3_coverage_note", "cdis_observation_year", "cdis_observation_lag_years",
        "cdis_sample_country_inward_from_china_usd_millions",
        "cdis_china_outward_position_in_sample_country_usd_millions", "cdis_inward_value_reported",
        "cdis_outward_value_reported", "cdis_any_direction_reported", "cdis_coverage_note",
        "cdis_direction_note", "cdis_score_status", "source_flag", "missing_flag",
        "context_missing_flag", "notes",
    ]
    output_path = OUTPUT_DIR / "master_country_year.csv"
    panel[ordered].to_csv(output_path, index=False, encoding="utf-8-sig")
    context_path = OUTPUT_DIR / "master_country_year_context.csv"
    panel[ordered].to_csv(context_path, index=False, encoding="utf-8-sig")

    append_progress(
        "Source-aware integrated country-year panel",
        "complete; core metrics separated from supplementary evidence",
        [
            f"Merged {len(panel)} rows (12 economies x 2 target years) with unique one-to-one country/ISO/year keys.",
            "P2 now uses ATOP 2017 values (Mexico separately corrected from raw 1 to active-treaty 0 using OAS withdrawal status) and official target-year treaty/NATO evidence for 2022; ATOP 2018 remains an explicitly historical cross-reference.",
            "Joined the reviewed BIS candidate-event layer as non-exhaustive, non-scoring evidence; a zero hit means no positive result in the selected reviewed set only.",
            "Joined IMF CDIS inward and outward positions separately: 2017 exact-year and 2021-to-2022 one-year-lag context; no value was imputed, and the layer is not semiconductor-specific or scored.",
            f"Core missingness distribution: {panel.assign(_missing=missing_flags)['_missing'].value_counts().to_dict()}; context reporting gaps are isolated in context_missing_flag.",
        ],
    )
    print(f"Wrote {output_path} and {context_path}; rows={len(panel)}; primary_key_unique={not panel.duplicated(['country','iso3','year']).any()}")
    print(f"P2 observed by year: {panel.groupby('year')['p2_us_formal_alliance'].count().to_dict()}; missing={int(panel['p2_us_formal_alliance'].isna().sum())}")
    print(f"CDIS context rows with at least one reporting direction: {int(panel['cdis_any_direction_reported'].sum())}/{len(panel)}; missing entries remain null")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
