"""Validate cross-source joins and publish a field-level source registry."""

from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import urlsplit

import numpy as np
import pandas as pd

from gtri_config import COUNTRIES, DOCS_DIR, OUTPUT_DIR, PROJECT_ROOT, RAW_DIR, YEARS, append_progress, ensure_directories


MASTER = OUTPUT_DIR / "master_country_year.csv"
REGISTRY = PROJECT_ROOT / "data" / "processed" / "source_registry.csv"
CHECKS = OUTPUT_DIR / "multisource_integration_checks.csv"
REPORT = DOCS_DIR / "multisource_integration_report.md"
LINEAGE = PROJECT_ROOT / "data" / "processed" / "field_lineage.csv"
COVERAGE = PROJECT_ROOT / "data" / "processed" / "source_coverage_by_year.csv"


# One row per public master-panel field: dataset-level registration alone is not
# enough to reproduce a multi-source join. This map documents the exact field,
# transformation, time mapping, and missingness boundary used in the panel.
FIELD_LINEAGE = {
    "country": ("sample_design", "country", "12-economy research sample; no external join", "fixed sample; 2017/2022", "country name", "identity", "not applicable", "Not a population sample."),
    "iso3": ("sample_design", "ISO3", "standardized sample key", "fixed sample; 2017/2022", "ISO3", "identity", "not applicable", "Used as the cross-source country key after source-specific mapping."),
    "year": ("sample_design", "target_year", "fixed target years 2017 and 2022", "target year", "ISO3 + target year", "identity", "not applicable", "For CDIS, source year may differ and is retained separately."),
    "p1_unga_relative_alignment": ("unga_ideal_points", "idealpointall for sample economy, China and United States", "mean absolute distances over the three-year window; China distance / (China + US distance)", "2017→2016–2018; 2022→2021–2023", "ISO3 + UNGA year window", "core_score", "No imputation; missing window would remain missing", "Centered windows are descriptive; 2022 includes 2023 and is not a no-look-ahead forecast."),
    "p2_us_formal_alliance": ("atop_v5_1; p2_us_state_nato_2022; oas_mexico_treaty_status", "ATOP defense obligation (2017); official 2022 source table; OAS Mexico status exception", "2017 ATOP observed value, except Mexico active-treaty audit; 2022 target-year treaty/NATO evidence", "2017→2017; 2022→2022", "country + ISO3 + target year", "core_score_with_source_break", "Not inferred from absent ATOP 2022; source-specific coding retained", "Source construction differs by year; zeros mean no qualifying tie found in selected evidence."),
    "p2_source_year": ("p2_source_logic", "source observation year", "recorded separately from target year", "2017 or 2022", "country + ISO3 + target year", "provenance", "Never forward-filled", "ATOP 2018 is only a separate reference, not a target-year observation."),
    "p2_measurement_source": ("p2_source_logic", "source_id / coding pathway", "labels ATOP, OAS exception, or State/NATO pathway", "2017 vs 2022", "country + ISO3 + target year", "provenance", "Not applicable", "Explicitly exposes the cross-year source break."),
    "p2_evidence_source_url": ("p2_source_logic", "source_url", "per-row official evidence links; semicolon-separated where multiple", "target-year evidence", "country + ISO3 + target year", "provenance", "Blank is a failure for coded P2 rows", "URLs identify source evidence; an audit note states the scope of negative findings."),
    "p2_treaty_or_basis": ("p2_source_logic", "treaty_or_basis", "short legal/institutional basis label", "target-year evidence", "country + ISO3 + target year", "provenance", "Blank is not allowed for coded rows", "Descriptive label, not a legal opinion."),
    "p2_coding_note": ("p2_source_logic", "coding_note", "human-readable coding scope and exception", "target-year evidence", "country + ISO3 + target year", "provenance", "Blank is not allowed for coded rows", "A zero is limited to selected formal defense-tie sources."),
    "p2_oas_adjustment": ("oas_mexico_treaty_status", "Rio Treaty effective status", "true only for Mexico 2017 raw ATOP conflict correction", "effective date 2004-09-06 applied to 2017", "Mexico + treaty status", "audit flag", "False otherwise; not a missing-value substitute", "Raw ATOP value is retained alongside the adjustment."),
    "p2_atop_observed": ("atop_v5_1", "US dyad defense-obligation field", "preserved as source observation before OAS audit", "2017 target; 2018 separate reference", "COW code + year → ISO3", "raw/reference", "Source NA retained", "ATOP coverage ends in 2018."),
    "p2_atop_source_year": ("atop_v5_1", "ATOP observation year", "preserved separately", "2017 observed; 2018 structural", "country + source year", "provenance", "Source NA retained", "Never relabel 2018 as 2022."),
    "p2_atop_structural_2018": ("atop_v5_1", "2018 US dyad structural value", "displayed only as historical cross-reference", "2018", "COW code + 2018 → ISO3", "reference_only", "Source NA retained", "Not a dynamic 2022 alliance measure."),
    "p2_official_2022": ("p2_us_state_nato_2022", "p2_official_active_defense_tie", "line-level target-year source coding", "2022", "country + ISO3", "core_score_2022", "Must have exactly one row per sample economy", "Official-source reconstruction; source break versus ATOP 2017 is disclosed."),
    "n1_electronics_foreign_va_share": ("oecd_tiva_2025", "EXGR_FVA; activity C26_27; counterpart World", "retain percent-of-gross-exports value", "2017 and 2022", "REF_AREA ISO3 + TIME_PERIOD", "core_score", "Missing stays null", "Broad electronics/electrical activity, not HS8542-only."),
    "n2_china_hs8542_import_share": ("comtrade_hs8542", "reporter self-reported imports from China / World imports", "HS8542 four-digit reporter import share", "2017 and 2022", "UN M49 reporter → ISO3 + year", "core_score", "No mirror-flow substitution; missing source data remain missing", "Reporter-year classification is retained; partner aggregates excluded."),
    "n3_us_hs8542_export_share": ("comtrade_hs8542", "reporter self-reported exports to United States / World exports", "HS8542 four-digit reporter export share", "2017 and 2022", "UN M49 reporter → ISO3 + year", "core_score", "No mirror-flow substitution; missing source data remain missing", "Trade destination is not a claim about re-export origin."),
    "n4_dual_dependency": ("derived_from_comtrade_hs8542", "N2 × N3", "product of two same-row country-year shares", "2017 and 2022", "country + ISO3 + year", "core_score_derived", "Null if either component is null", "Interaction indicator; overlaps conceptually with N2 and N3."),
    "v1_hs8542_import_hhi": ("comtrade_hs8542", "real partner import values / world import denominator", "sum of squared partner shares after removing World/aggregate partners", "2017 and 2022", "reporter + year + genuine partner", "core_score", "No synthetic partners; source coverage preserved", "Partner aggregation and reporter classification affect comparability."),
    "v2_effective_supplier_count": ("comtrade_hs8542", "genuine partner import shares", "count partners with import share ≥1%", "2017 and 2022", "reporter + year + genuine partner", "core_score", "No synthetic partners; missing remains missing", "Threshold measure; not a count of firm-level qualified suppliers."),
    "avg_distance_to_china": ("unga_ideal_points", "idealpointall", "mean absolute distance over target window", "2017→2016–2018; 2022→2021–2023", "ISO3 + UNGA year window", "intermediate", "No imputation", "Source-window years are also stored."),
    "avg_distance_to_us": ("unga_ideal_points", "idealpointall", "mean absolute distance over target window", "2017→2016–2018; 2022→2021–2023", "ISO3 + UNGA year window", "intermediate", "No imputation", "Source-window years are also stored."),
    "window_start": ("unga_ideal_points", "UNGA year window", "target year minus one", "2017→2016; 2022→2021", "target year", "provenance", "not applicable", "Centered window includes a future year for each target."),
    "window_end": ("unga_ideal_points", "UNGA year window", "target year plus one", "2017→2018; 2022→2023", "target year", "provenance", "not applicable", "2022 window includes 2023."),
    "p3_reviewed_candidate_literal_count": ("bis_federal_register_reviewed_subset", "literal mention count in reviewed candidate records", "reported only for the selected reviewed subset", "rule/event years 2017 and 2022", "reviewed rule + sample economy + year", "evidence_only", "Not a full-rule-universe denominator", "Mention count is not legal applicability."),
    "p3_bis_direct_increase_events_reviewed_subset": ("bis_federal_register_reviewed_subset", "manually confirmed direct semiconductor-increase finding", "count direct findings in reviewed subset", "rule/event years 2017 and 2022", "reviewed rule + sample economy + year", "evidence_only", "Zero is subset-bounded", "Not an exhaustive BIS exposure count."),
    "p3_bis_direct_increase_flag_reviewed_subset": ("bis_federal_register_reviewed_subset", "direct event count > 0", "binary summary of reviewed subset only", "2017 and 2022", "country + year", "evidence_only_not_scored", "Zero does not mean no wider exposure", "P3 remains outside the score pending complete legal review."),
    "p3_scope": ("bis_federal_register_reviewed_subset", "review scope label", "copied from reviewed-subset summary", "2017 and 2022", "country + year", "provenance", "Must identify non-exhaustive scope", "Selected candidate rules only."),
    "p3_scoring_status": ("bis_federal_register_reviewed_subset", "scoring boundary", "explicit evidence-only label", "2017 and 2022", "country + year", "provenance", "Must remain not scored", "Not an index input."),
    "p3_notes": ("bis_federal_register_reviewed_subset", "manual review notes", "copied from selected-rule table", "reviewed rule/event year", "country + year", "evidence", "Blank permitted if no note", "Human-reviewed sample only."),
    "p3_coverage_note": ("bis_federal_register_reviewed_subset", "coverage limitation", "fixed scope note attached to all rows", "2017 and 2022", "country + year", "provenance", "Must state selected subset", "Zero hit is not proof of no exposure."),
    "cdis_observation_year": ("imf_cdis_positions", "reported observation year", "retained separately from target year", "2017→2017; 2022→2021", "economy + observed year", "provenance", "No year interpolation", "2022 target uses nearest supplied prior year."),
    "cdis_observation_lag_years": ("imf_cdis_positions", "target year - observation year", "derived lag in years", "2017→0; 2022→1", "target year + observation year", "provenance", "Not applicable", "Lag is visible, never concealed."),
    "cdis_sample_country_inward_from_china_usd_millions": ("imf_cdis_positions", "sample reporter inward position; China immediate counterpart", "retain USD millions as reported", "2017 and 2021→2022", "reporter ISO3 + year + direction + counterpart", "context_only", "Reported null remains null; no zero-fill", "Not semiconductor-specific; immediate counterpart, not ultimate owner."),
    "cdis_china_outward_position_in_sample_country_usd_millions": ("imf_cdis_positions", "China reporter outward position; sample economy immediate counterpart", "retain USD millions as reported", "2017 and 2021→2022", "China reporter + counterpart ISO3 + year + direction", "context_only", "Reported null remains null; no zero-fill", "Different reporting perspective; do not add/average with inward series."),
    "cdis_inward_value_reported": ("imf_cdis_positions", "inward position non-null flag", "derived from reported value presence", "2017 and 2021→2022", "same CDIS observation key", "coverage_flag", "False means not reported, not zero", "Missingness explicitly exposed."),
    "cdis_outward_value_reported": ("imf_cdis_positions", "outward position non-null flag", "derived from reported value presence", "2017 and 2021→2022", "same CDIS observation key", "coverage_flag", "False means not reported, not zero", "Missingness explicitly exposed."),
    "cdis_any_direction_reported": ("imf_cdis_positions", "either direction has reported value", "OR of direction-specific value presence", "2017 and 2021→2022", "country + target year", "coverage_flag", "False means neither direction reported", "Does not imply two-sided coverage."),
    "cdis_coverage_note": ("imf_cdis_positions", "source coverage note", "retained from CDIS processor", "2017 and 2021→2022", "country + target year", "provenance", "Missing remains null", "No 2022 CDIS file supplied."),
    "cdis_direction_note": ("imf_cdis_positions", "direction/ownership note", "fixed reporting-asymmetry explanation", "2017 and 2021→2022", "country + target year", "provenance", "not applicable", "Immediate counterpart only."),
    "cdis_score_status": ("imf_cdis_positions", "score status", "fixed non-scoring context label", "2017 and 2022 target rows", "country + target year", "provenance", "Must remain non_scoring_context", "Never enters GTRI calculation."),
    "source_flag": ("derived_source_ledger", "module source flags", "deduplicated provenance labels joined with delimiter", "per target row", "country + year", "provenance", "Must contain scored-source identities", "Not a substitute for the field-level map."),
    "missing_flag": ("derived_missingness_audit", "eight core index fields", "lists missing core fields or `none`", "per target row", "country + year", "quality_flag", "Never overwrite nulls", "Core completeness only."),
    "context_missing_flag": ("derived_missingness_audit", "CDIS inward/outward positions", "lists not-reported directions", "per target row", "country + year", "quality_flag", "No missing context is imputed", "Context gaps do not affect core score."),
    "notes": ("derived_source_ledger", "P2 coding note + CDIS lag note", "concatenate relevant row-level caveats", "per target row", "country + year", "provenance", "Blank permitted when no special note", "Retains material exceptions and lag."),
}


SOURCE_ROWS = [
    {
        "source_id": "comtrade_hs8542",
        "dataset_name": "UN Comtrade HS8542 Reporter self-reported trade",
        "provider": "United Nations Statistics Division",
        "source_tier": "official_external_trade_source",
        "role": "Core scored trade and concentration indicators N2-N4/V1-V2",
        "raw_artifact": "data/raw/comtrade/*_HS8542_*.json",
        "grain": "reporter x year x flow x partner x HS heading",
        "join_key_or_mapping": "UN M49 reporter/partner -> ISO3; reporter x target year",
        "coverage": "12 economies; 2017 and 2022; HS8542; imports and exports",
        "transformation": "Reporter self-reports only; real partner rows for shares/HHI; world total used as denominator; no mirror flows",
        "score_status": "core_score",
        "known_boundary": "Classification revision differs by reporter-year at the four-digit heading; six-digit subheadings are not mixed.",
        "source_url": "https://comtradeapi.un.org/",
    },
    {
        "source_id": "unga_ideal_points",
        "dataset_name": "UNGA Voting Ideal Points / Voeten",
        "provider": "Harvard Dataverse",
        "source_tier": "contest_host_base_dataset",
        "role": "P1 relative alignment",
        "raw_artifact": "data/raw/unga/IdealpointsJuly2025.tab",
        "grain": "economy x General Assembly year",
        "join_key_or_mapping": "ISO3 x window year; three observations summarized per target year",
        "coverage": "2017 target uses 2016-2018; 2022 target uses 2021-2023",
        "transformation": "Mean absolute distance to China divided by summed mean distances to China and the United States",
        "score_status": "core_score",
        "known_boundary": "Centered windows are descriptive alignment measures; the 2022 value includes 2023 voting data and is not a no-look-ahead forecast.",
        "source_url": "https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/LEJUQZ",
    },
    {
        "source_id": "atop_v5_1",
        "dataset_name": "ATOP v5.1",
        "provider": "Alliance Treaty Obligations and Provisions project",
        "source_tier": "contest_host_base_dataset",
        "role": "P2 observed defense obligation in 2017; 2018 structural cross-reference",
        "raw_artifact": "data/raw/atop/atop_5.1_csv.zip",
        "grain": "alliance dyad x year",
        "join_key_or_mapping": "COW state codes; US dyad x target year",
        "coverage": "Published dyad-year coverage ends 2018",
        "transformation": "Use the defense-obligation component; preserve broader alliance and clause fields for audit",
        "score_status": "core_score_2017_only; 2018_separate_reference",
        "known_boundary": "No ATOP 2022 observation; structural 2018 is not relabelled as 2022.",
        "source_url": "https://www.atopdata.org/",
    },
    {
        "source_id": "p2_us_state_nato_2022",
        "dataset_name": "US formal defense treaties and NATO membership (2022 target-year reconstruction)",
        "provider": "US Department of State; NATO",
        "source_tier": "official_external_policy_source",
        "role": "P2 target-year active formal defense tie for 2022",
        "raw_artifact": "data/raw/p2/p2_official_2022_source.csv; data/raw/p2/state_treaties_in_force_2020.pdf; data/raw/p2/state_tif_supplement_2021_2023.pdf",
        "grain": "sample economy x target year",
        "join_key_or_mapping": "country + ISO3; one 2022 row per sample economy",
        "coverage": "12 economies; target year 2022; US State Treaties in Force 2020 plus 2021-2023 supplement; NATO accession chronology",
        "transformation": "Screen State treaty records and dated 2022 country documents for formal mutual/collective defense commitments; filter NATO membership by accession date; each row retains its evidence URLs and scope note",
        "score_status": "core_score_2022_with_source_break_disclosed",
        "known_boundary": "Source construction differs from ATOP 2017. The archived State collective-defense inventory is not treated as a 2022 snapshot by itself; the 2020 TIF and 2021-2023 supplement plus target-year country evidence are retained. Zero means no qualifying tie found in the selected evidence, not absence of security cooperation.",
        "source_url": "https://www.state.gov/wp-content/uploads/2020/08/TIF-2020-Full-website-view.pdf; https://www.state.gov/wp-content/uploads/2023/06/TIF-Supplement-Report-2023.pdf; https://2009-2017.state.gov/s/l/treaty/collectivedefense/; https://www.nato.int/cps/en/natohq/opinions_212795.htm",
    },
    {
        "source_id": "oas_mexico_treaty_status",
        "dataset_name": "Rio Treaty status for Mexico",
        "provider": "Organization of American States",
        "source_tier": "official_external_treaty_status_crosscheck",
        "role": "Resolve the ATOP/Mexico 2017 status disagreement",
        "raw_artifact": "data/raw/p2/p2_official_2022_source.csv",
        "grain": "treaty party status x effective date",
        "join_key_or_mapping": "Mexico; Rio Treaty cessation date 2004-09-06",
        "coverage": "Mexico P2 audit note; applies to 2017 active-status coding",
        "transformation": "Keep ATOP raw dyad value=1 but audited active-defense-tie P2=0",
        "score_status": "single_country_core_score_adjustment_2017",
        "known_boundary": "Raw ATOP evidence is retained next to the audited value so the exception is reversible and inspectable.",
        "source_url": "https://www.oas.org/juridico/english/sigs/b-29.html",
    },
    {
        "source_id": "oecd_tiva_2025",
        "dataset_name": "OECD TiVA 2025",
        "provider": "Organisation for Economic Co-operation and Development",
        "source_tier": "contest_host_base_dataset",
        "role": "N1 foreign value-added share in electronics exports",
        "raw_artifact": "data/raw/tiva/oecd_tiva_exgr_fva_c26_27.csv",
        "grain": "economy x year x activity x counterpart x unit",
        "join_key_or_mapping": "REF_AREA ISO3 x TIME_PERIOD",
        "coverage": "12 economies; annual values for 2017 and 2022",
        "transformation": "EXGR_FVA, C26_27 computer/electronic/electrical equipment, counterpart World, percent of gross exports",
        "score_status": "core_score",
        "known_boundary": "C26_27 is broader than HS8542 and is not a semiconductor-only industry measure.",
        "source_url": "https://sdmx.oecd.org/",
    },
    {
        "source_id": "bis_federal_register_reviewed_subset",
        "dataset_name": "BIS Federal Register rules, selected manually reviewed candidates",
        "provider": "US Department of Commerce / Federal Register",
        "source_tier": "official_external_policy_evidence",
        "role": "P3 event evidence overlay, not country-level legal risk score",
        "raw_artifact": "data/raw/bis/documents/*; data/raw/bis/bis_p3_manual_review_completed_2017_2022.csv",
        "grain": "rule document x event year; summarized to economy-year within reviewed candidate subset",
        "join_key_or_mapping": "Manual scope finding + sample economy + publication year",
        "coverage": "10 selected reviewed rules across 2017/2022; 24-row summary grid",
        "transformation": "Join only reviewed direct semiconductor-increase findings as scoped evidence; mention alone is not a target finding",
        "score_status": "evidence_only_non_exhaustive_not_scored",
        "known_boundary": "A zero is limited to the reviewed candidate subset and does not mean no BIS exposure in the full rule universe.",
        "source_url": "https://www.federalregister.gov/",
    },
    {
        "source_id": "imf_cdis_positions",
        "dataset_name": "IMF Coordinated Direct Investment Survey (now Direct Investment Positions by Counterpart Economy)",
        "provider": "International Monetary Fund; user-supplied official workbooks",
        "source_tier": "official_external_capital_context",
        "role": "Separate China-related inward and outward capital-position context",
        "raw_artifact": "data/raw/fdi/2017_inward.xlsx; data/raw/fdi/2017_outward.xlsx; data/raw/fdi/2021_inward.xlsx; data/raw/fdi/2021_outward.xlsx",
        "grain": "reporting economy x year x direction x immediate counterpart",
        "join_key_or_mapping": "ISO3/economy x observation year; 2017 -> target 2017 (lag 0), 2021 -> target 2022 (lag 1)",
        "coverage": "12 economies; 2017 and 2021 only; no supplied 2022 file",
        "transformation": "Keep reporting-economy inward and China-reported outward positions separate; values remain USD millions",
        "score_status": "non_scoring_context",
        "known_boundary": "Not semiconductor-specific; immediate counterpart is not ultimate owner; reporting asymmetry, missing cells, and financial-center effects remain.",
        "source_url": "https://data.imf.org/Datasets/DIP",
    },
    {
        "source_id": "gdelt_us_china",
        "dataset_name": "GDELT US-China Bilateral Events Database",
        "provider": "Risk Analysis Lab original database / GDELT",
        "source_tier": "contest_host_original_database_screened",
        "role": "Macro event-background reference only",
        "raw_artifact": "not downloaded; no event-level export in current project inputs",
        "grain": "bilateral event; not the country-year observation unit used by the core panel",
        "join_key_or_mapping": "No country-year join performed",
        "coverage": "Described by the lab as covering 1979 onward",
        "transformation": "No values inferred from charts; no country-year value is created",
        "score_status": "context_only_not_joined",
        "known_boundary": "Current project has no downloadable event-level file to reproduce country-year values.",
        "source_url": "https://riskalab-databank.vercel.app/gdelt",
    },
    {
        "source_id": "gta_csl_candidates",
        "dataset_name": "Global Trade Alert and US Consolidated Screening List",
        "provider": "Global Trade Alert; US trade agencies",
        "source_tier": "contest_host_library_candidates_screened",
        "role": "Future enterprise/product compliance linkage candidates",
        "raw_artifact": "not downloaded; no enterprise/product historical matches in current project inputs",
        "grain": "policy intervention / listed entity or product record",
        "join_key_or_mapping": "Would require real supplier/customer/product identifiers and historical snapshot mapping",
        "coverage": "Not integrated into current country-year panel",
        "transformation": "No hit counts or historical scores generated",
        "score_status": "candidate_not_integrated",
        "known_boundary": "A country-level join would not establish company exposure without BOM, entity, or product linkage.",
        "source_url": "https://www.globaltradealert.org/; https://www.trade.gov/consolidated-screening-list",
    },
]


def digest_artifacts(spec: str) -> str:
    entries: list[str] = []
    for item in spec.split("; "):
        if "*" not in item:
            candidates = [PROJECT_ROOT / item]
        else:
            parent, pattern = item.rsplit("/", 1)
            candidates = sorted((PROJECT_ROOT / parent).glob(pattern))
        files: list[Path] = []
        for path in candidates:
            if path.is_dir():
                files.extend(child for child in path.rglob("*") if child.is_file())
            elif path.is_file():
                files.append(path)
        for path in sorted(set(files)):
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            entries.append(f"{path.relative_to(PROJECT_ROOT).as_posix()}:{digest}")
    if not entries:
        return ""
    return hashlib.sha256("\n".join(sorted(entries)).encode("utf-8")).hexdigest()


def add_check(rows: list[dict], check_id: str, observed: object, expected: object, passed: bool, detail: str) -> None:
    rows.append(
        {
            "check_id": check_id,
            "observed": observed,
            "expected": expected,
            "status": "PASS" if passed else "FAIL",
            "detail": detail,
        }
    )


def build_field_lineage(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for field in panel.columns:
        spec = FIELD_LINEAGE.get(field)
        if spec is None:
            raise RuntimeError(f"Panel field has no lineage specification: {field}")
        source_id, source_field, transformation, source_year, join_key, status, missing_rule, caveat = spec
        rows.append({
            "target_field": field,
            "source_id": source_id,
            "source_field_or_record": source_field,
            "source_year_mapping": source_year,
            "join_key": join_key,
            "transformation": transformation,
            "score_or_evidence_status": status,
            "missing_value_rule": missing_rule,
            "comparability_or_scope_limit": caveat,
        })
    return pd.DataFrame(rows)


def build_source_coverage(panel: pd.DataFrame) -> pd.DataFrame:
    expected = panel["country"].nunique()
    rows: list[dict] = []

    def add(source_id: str, year: int, observation_year: str, present: int, observed: int,
            score_status: str, note: str, inward: int | None = None, outward: int | None = None,
            hits: int | None = None) -> None:
        rows.append({
            "source_id": source_id,
            "target_year": year,
            "source_observation_year": observation_year,
            "expected_country_rows": expected,
            "panel_rows_with_source_record": present,
            "rows_with_observed_values": observed,
            "rows_missing_source_values": expected - observed,
            "cdis_inward_values_reported": inward,
            "cdis_outward_values_reported": outward,
            "reviewed_subset_positive_hits": hits,
            "score_or_evidence_status": score_status,
            "coverage_note": note,
        })

    for year, group in panel.groupby("year", sort=True):
        year = int(year)
        trade_fields = ["n2_china_hs8542_import_share", "n3_us_hs8542_export_share", "n4_dual_dependency",
                        "v1_hs8542_import_hhi", "v2_effective_supplier_count"]
        add("comtrade_hs8542", year, str(year), len(group), int(group[trade_fields].notna().all(axis=1).sum()),
            "core_score", "Reporter-self-reported HS8542 fields; not mirror trade.")
        add("unga_ideal_points", year, str(group["window_start"].iloc[0]) + "-" + str(group["window_end"].iloc[0]),
            len(group), int(group["p1_unga_relative_alignment"].notna().sum()), "core_score",
            "Three-year centered voting window; 2022 includes 2023.")
        add("atop_v5_1", year, str(year), len(group), int(group["p2_atop_observed"].notna().sum()),
            "core_score_2017_only", "Target-year ATOP observation; absence in 2022 is not filled from 2018.")
        add("atop_v5_1_structural_reference", year, "2018", len(group), int(group["p2_atop_structural_2018"].notna().sum()),
            "reference_only", "2018 structural cross-reference; never labelled a 2022 observation.")
        add("p2_us_state_nato_2022", year, "2022", len(group), int(group["p2_official_2022"].notna().sum()),
            "core_score_2022_with_source_break", "Target-year official-source reconstruction; not method-identical to ATOP 2017.")
        add("oas_mexico_treaty_status", year, "2004 status applied to 2017 audit", len(group),
            int(group["p2_oas_adjustment"].sum()), "single_country_audit", "Applies only to the Mexico 2017 ATOP conflict.")
        add("oecd_tiva_2025", year, str(year), len(group), int(group["n1_electronics_foreign_va_share"].notna().sum()),
            "core_score", "C26_27 broad electronics/electrical industry; not semiconductor-only.")
        p3_present = int(group[["p3_scope", "p3_scoring_status", "p3_bis_direct_increase_flag_reviewed_subset"]].notna().all(axis=1).sum())
        add("bis_federal_register_reviewed_subset", year, str(year), p3_present, p3_present,
            "evidence_only_non_exhaustive_not_scored", "Complete 12-row summary grid is not full BIS rule-universe coverage.",
            hits=int(group["p3_bis_direct_increase_flag_reviewed_subset"].fillna(0).sum()))
        cdis_source_year = int(group["cdis_observation_year"].dropna().iloc[0]) if group["cdis_observation_year"].notna().any() else "not supplied"
        cdis_in = int(group["cdis_inward_value_reported"].sum())
        cdis_out = int(group["cdis_outward_value_reported"].sum())
        cdis_any = int(group["cdis_any_direction_reported"].sum())
        add("imf_cdis_positions", year, str(cdis_source_year), len(group), cdis_any, "context_only_not_scored",
            "Immediate-counterpart investment position; observed year kept separate; missing cells are not zero-filled.",
            inward=cdis_in, outward=cdis_out)
        add("gdelt_us_china", year, "not joined", 0, 0, "context_only_not_joined",
            "No event-level export was available for reproducible country-year linkage.")
        add("gta_csl_candidates", year, "not joined", 0, 0, "candidate_not_integrated",
            "No enterprise/product identifiers and historical snapshots available for a defensible match.")
    return pd.DataFrame(rows)


def main() -> int:
    ensure_directories()
    if not MASTER.is_file():
        raise FileNotFoundError("Run scripts/06_build_master_panel.py first")
    panel = pd.read_csv(MASTER)
    lineage_df = build_field_lineage(panel)
    coverage_df = build_source_coverage(panel)
    expected = {(economy["country"], economy["iso3"], year) for economy in COUNTRIES for year in YEARS}
    observed = set(map(tuple, panel[["country", "iso3", "year"]].itertuples(index=False, name=None)))
    checks: list[dict] = []
    add_check(checks, "panel_country_year_coverage", len(panel), 24, len(panel) == 24 and observed == expected,
              "Expected the exact 12-economy x 2-year key grid.")
    add_check(checks, "panel_primary_key_unique", int(panel.duplicated(["country", "iso3", "year"]).sum()), 0,
              not panel.duplicated(["country", "iso3", "year"]).any(), "No duplicate country/ISO/year rows.")

    core = [
        "p1_unga_relative_alignment", "p2_us_formal_alliance", "n1_electronics_foreign_va_share",
        "n2_china_hs8542_import_share", "n3_us_hs8542_export_share", "n4_dual_dependency",
        "v1_hs8542_import_hhi", "v2_effective_supplier_count",
    ]
    core_missing = int(panel[core].isna().sum().sum())
    add_check(checks, "core_scoring_field_completeness", core_missing, 0, core_missing == 0,
              "Core score inputs must be populated; only explicit source exceptions may be retained in separate raw/reference fields.")

    n4_error = float((panel["n4_dual_dependency"] - panel["n2_china_hs8542_import_share"] * panel["n3_us_hs8542_export_share"]).abs().max())
    add_check(checks, "N4_formula_max_abs_error", n4_error, "<= 1e-12", n4_error <= 1e-12,
              "N4 must equal N2 multiplied by N3 for every row.")

    p2_year_ok = (
        panel.loc[panel["year"] == 2017, "p2_source_year"].eq(2017).all()
        and panel.loc[panel["year"] == 2022, "p2_source_year"].eq(2022).all()
        and panel["p2_us_formal_alliance"].isin([0, 1]).all()
    )
    add_check(checks, "P2_target_year_source_alignment", int(p2_year_ok), 1, bool(p2_year_ok),
              "2017 rows use 2017 evidence; 2022 rows use 2022 evidence; ATOP 2018 remains separately labelled.")

    mexico = panel[(panel["iso3"] == "MEX") & (panel["year"] == 2017)]
    mexico_ok = len(mexico) == 1 and int(mexico.iloc[0]["p2_atop_observed"]) == 1 \
        and int(mexico.iloc[0]["p2_us_formal_alliance"]) == 0 and bool(mexico.iloc[0]["p2_oas_adjustment"])
    add_check(checks, "Mexico_ATOP_OAS_conflict_explicit", int(mexico_ok), 1, mexico_ok,
              "Raw ATOP=1 is preserved; audited P2=0 follows OAS's 2004 treaty-cessation record.")

    p2_source = pd.read_csv(RAW_DIR / "p2" / "p2_official_2022_source.csv")
    p2_2022 = panel[panel["year"] == 2022].merge(
        p2_source[["country", "iso3", "p2_official_active_defense_tie"]],
        on=["country", "iso3"], how="left", validate="one_to_one",
    )
    p2_match = len(p2_2022) == 12 and p2_2022["p2_us_formal_alliance"].eq(p2_2022["p2_official_active_defense_tie"]).all()
    add_check(checks, "P2_2022_official_overlay_matches_source", int(p2_match), 1, bool(p2_match),
              "Merged P2 values reproduce the line-level manually coded official-source input file.")

    required_specific_evidence = {
        "THA": "u-s-security-cooperation-with-thailand",
        "PHL": "u-s-security-cooperation-with-the-philippines",
        "JPN": "u-s-japan-security-consultative-committee-22",
        "KOR": "ICS_EAP_ROK",
        "DEU": "nato-member-countries",
        "NLD": "nato-member-countries",
    }
    row_quality = (
        len(p2_source) == 12
        and not p2_source.duplicated(["country", "iso3", "year"]).any()
        and p2_source["treaty_or_basis"].notna().all()
        and p2_source["coding_note"].notna().all()
        and p2_source["source_url"].map(lambda value: all(
            urlsplit(url.strip()).scheme in {"http", "https"} and bool(urlsplit(url.strip()).netloc)
            for url in str(value).split(";") if url.strip()
        )).all()
        and all(
            required_specific_evidence[iso3] in str(p2_source.loc[p2_source["iso3"] == iso3, "source_url"].iloc[0])
            for iso3 in required_specific_evidence
        )
    )
    add_check(checks, "P2_2022_row_level_basis_and_link_quality", int(row_quality), 1, bool(row_quality),
              "All 12 country rows have a coding note and parseable URLs; each positive row links to country-specific or NATO membership evidence, not only a general inventory.")

    tif_paths = [
        RAW_DIR / "p2" / "state_treaties_in_force_2020.pdf",
        RAW_DIR / "p2" / "state_tif_supplement_2021_2023.pdf",
    ]
    tif_urls = [
        "https://www.state.gov/wp-content/uploads/2020/08/TIF-2020-Full-website-view.pdf",
        "https://www.state.gov/wp-content/uploads/2023/06/TIF-Supplement-Report-2023.pdf",
    ]
    tif_files_ok = all(path.is_file() and path.stat().st_size > 100_000 for path in tif_paths)
    tif_row_coverage_ok = len(p2_source) == 12 and p2_source["source_url"].map(
        lambda value: all(url in str(value) for url in tif_urls)
    ).all()
    p2_docs_ok = tif_files_ok and tif_row_coverage_ok
    add_check(checks, "P2_official_treaty_reference_files_and_row_links", int(p2_docs_ok), 1, p2_docs_ok,
              "Official State TIF 2020 and 2021-2023 supplement are retained, hashed in the registry, and linked from all 12 target-year coding rows.")

    cdis_ok = panel["cdis_observation_year"].eq(panel["year"].map({2017: 2017, 2022: 2021})).all() \
        and panel["cdis_observation_lag_years"].eq(panel["year"] - panel["cdis_observation_year"]).all() \
        and panel["cdis_score_status"].eq("non_scoring_context").all()
    add_check(checks, "CDIS_target_year_lag_and_score_boundary", int(cdis_ok), 1, bool(cdis_ok),
              "2017 maps to 2017 and 2022 maps to 2021 with one-year lag; CDIS stays outside the score.")

    cdis_missingness_ok = (
        panel["cdis_inward_value_reported"].eq(panel["cdis_sample_country_inward_from_china_usd_millions"].notna()).all()
        and panel["cdis_outward_value_reported"].eq(panel["cdis_china_outward_position_in_sample_country_usd_millions"].notna()).all()
        and panel["cdis_any_direction_reported"].eq(
            panel["cdis_inward_value_reported"] | panel["cdis_outward_value_reported"]
        ).all()
    )
    add_check(checks, "CDIS_reported_flags_match_unfilled_values", int(cdis_missingness_ok), 1,
              bool(cdis_missingness_ok),
              "Direction flags are derived from actual reported cells; absent CDIS values remain null rather than being converted to zero.")

    p3_ok = panel["p3_scoring_status"].eq("evidence_only_not_scored").all() \
        and panel["p3_scope"].eq("selected_reviewed_candidate_events_only_not_exhaustive").all()
    add_check(checks, "P3_scope_and_non_scoring_boundary", int(p3_ok), 1, bool(p3_ok),
              "The selected candidate set is explicitly non-exhaustive; no zero is interpreted as no overall exposure.")

    path_text = " ".join(panel.astype(str).fillna("").to_numpy().flatten())
    has_machine_path = any(token in path_text for token in ("D:\\", "C:\\Users\\", "/Users/"))
    add_check(checks, "no_machine_local_paths_in_panel", int(not has_machine_path), 1, not has_machine_path,
              "Public-facing panel stores source URLs or project-relative artifacts, not private workstation paths.")

    lineage_ok = set(lineage_df["target_field"]) == set(panel.columns) and not lineage_df["target_field"].duplicated().any()
    add_check(checks, "field_level_lineage_covers_entire_panel", len(lineage_df), len(panel.columns), lineage_ok,
              "Every core, context, provenance, and missingness field has a declared source, transformation, join key, and boundary.")

    expected_coverage_ids = {
        "comtrade_hs8542", "unga_ideal_points", "atop_v5_1", "atop_v5_1_structural_reference",
        "p2_us_state_nato_2022", "oas_mexico_treaty_status", "oecd_tiva_2025",
        "bis_federal_register_reviewed_subset", "imf_cdis_positions", "gdelt_us_china", "gta_csl_candidates",
    }
    coverage_ok = (
        len(coverage_df) == len(expected_coverage_ids) * len(YEARS)
        and set(coverage_df["source_id"]) == expected_coverage_ids
        and set(coverage_df["target_year"].astype(int)) == set(YEARS)
        and (coverage_df["rows_with_observed_values"] <= coverage_df["expected_country_rows"]).all()
        and (coverage_df["rows_missing_source_values"] >= 0).all()
    )
    add_check(checks, "source_coverage_by_target_year_artifact", len(coverage_df),
              len(expected_coverage_ids) * len(YEARS), bool(coverage_ok),
              "Coverage distinguishes source records from observed values, reports CDIS directions separately, and marks unjoined candidates as unavailable rather than zero risk.")

    registry = pd.DataFrame(SOURCE_ROWS)
    registry["artifact_sha256_manifest"] = registry["raw_artifact"].map(digest_artifacts)
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    registry.to_csv(REGISTRY, index=False, encoding="utf-8-sig")
    LINEAGE.parent.mkdir(parents=True, exist_ok=True)
    lineage_df.to_csv(LINEAGE, index=False, encoding="utf-8-sig")
    coverage_df.to_csv(COVERAGE, index=False, encoding="utf-8-sig")
    checks_df = pd.DataFrame(checks)
    CHECKS.parent.mkdir(parents=True, exist_ok=True)
    checks_df.to_csv(CHECKS, index=False, encoding="utf-8-sig")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    registry.to_csv(OUTPUT_DIR / REGISTRY.name, index=False, encoding="utf-8-sig")

    missing_cdis_in = int(panel["cdis_sample_country_inward_from_china_usd_millions"].isna().sum())
    missing_cdis_out = int(panel["cdis_china_outward_position_in_sample_country_usd_millions"].isna().sum())
    p3_hits = panel.loc[panel["p3_bis_direct_increase_flag_reviewed_subset"].eq(1), ["country", "year"]]
    lines = [
        "# 多源数据整合与连接审计",
        "",
        "本报告说明各来源怎样连接到国家—年份面板，以及哪些字段参与计分。所有补充来源保留自己的观测年份、口径和用途；不能对齐的来源不会为了凑齐而被强行转成分数。",
        "",
        "## 数据层级",
        "",
        "| 层级 | 数据 | 连接方式 | 进入指数 |",
        "| --- | --- | --- | --- |",
        "| 核心指标 | UN Comtrade、UNGA、ATOP/官方条约资料、OECD TiVA | ISO3 + 目标年份；贸易细项先按Reporter、年份、Flow、Partner计算 | 是；P2每年来源不同，见字段说明 |",
        "| 政策证据 | BIS Federal Register人工复核候选规则 | 规则生效/发布年份 + 样本经济体；只反映选中复核集合 | 否；非穷尽 |",
        "| 资本联系背景 | IMF CDIS | 国家 + 观测年；2017→2017，2021→2022（滞后1年） | 否；非半导体专项 |",
        "| 宏观背景/候选 | GDELT、GTA、CSL | 当前无国家—年份或企业商品级可复现明细匹配 | 否 |",
        "",
        "## 连接检查",
        "",
        f"- 核心面板：{len(panel)} 行；预期 12 国 × 2 年；主键重复数 {int(panel.duplicated(['country','iso3','year']).sum())}。",
        f"- 核心计分字段缺失数：{int(panel[core].isna().sum().sum())}。",
        f"- P2：2017 为 ATOP 观察值（墨西哥单独按 OAS 退约记录复核）；2022 逐国核对美国国务院《Treaties in Force 2020》、覆盖至2023年的补编、目标年双边材料及NATO成员加入年份。旧版国务院安排清单标为历史索引，不单独充当2022状态快照；ATOP 2018只作历史参照。",
        f"- BIS：候选集复核正向事件命中 {len(p3_hits)} 个国家—年份格；当前命中：{', '.join(f'{r.country} {int(r.year)}' for r in p3_hits.itertuples(index=False)) or '无'}。零值仅指本次选定复核集合。",
        f"- CDIS：2022目标行使用2021数据，标注滞后1年；对华流入位置未报告 {missing_cdis_in}/24，对华流出位置未报告 {missing_cdis_out}/24；未填补。",
        "- CDIS的流入与流出来自不同报告方，分别保留，不求平均、不相加；它描述直接对手方投资头寸，不代表最终所有者或半导体投资。",
        "",
        "## 可复核文件",
        "",
        "- `data/processed/source_registry.csv`：逐来源说明发布方、粒度、连接键、覆盖、转换、计分状态、局限与来源文件哈希清单。",
        "- `data/processed/field_lineage.csv`：逐字段记录面板变量的原始字段、来源年份映射、连接键、转换、缺失值处理和可比性边界。",
        "- `data/processed/source_coverage_by_year.csv`：逐数据源与目标年份列出实际连接数、观测值覆盖、缺报和未接入候选；CDIS的流入、流出单独列示。",
        "- `output/master_country_year.csv`：核心指标与非计分证据并列的24行面板。",
        "- `output/multisource_integration_checks.csv`：本轮主键、来源年份、P2冲突、P3边界、CDIS滞后与本机路径检查。",
        "- `data/raw/fdi/key_year_manifest.csv`：四份CDIS工作簿的相对路径、文件字节数与SHA-256。",
        "- `data/raw/p2/state_treaties_in_force_2020.pdf` 与 `data/raw/p2/state_tif_supplement_2021_2023.pdf`：美国国务院正式条约记录；SHA-256见来源登记表。",
        "",
        "",
    ]
    coverage_lookup = {(str(row.source_id), int(row.target_year)): row
                       for row in coverage_df.itertuples(index=False)}
    lines.extend([
        "## 年度覆盖摘要",
        "",
        "| 来源层 | 2017目标年 | 2022目标年 | 解释 |",
        "| --- | ---: | ---: | --- |",
    ])
    summary_rows = [
        ("UN Comtrade HS8542", "comtrade_hs8542", "Reporter自报贸易与真实伙伴分布"),
        ("UNGA理想点", "unga_ideal_points", "2017用2016–2018窗口；2022用2021–2023窗口"),
        ("ATOP目标年观察", "atop_v5_1", "ATOP无2022目标年观测；2018只单列为结构参照"),
        ("美国国务院/NATO P2", "p2_us_state_nato_2022", "仅用于2022；与2017 ATOP存在来源断点"),
        ("OECD TiVA C26_27", "oecd_tiva_2025", "电子/电气宽口径，不是半导体专属"),
    ]
    for label, source_id, explanation in summary_rows:
        cells = []
        for target_year in (2017, 2022):
            row = coverage_lookup[(source_id, target_year)]
            if source_id == "p2_us_state_nato_2022" and target_year == 2017:
                cells.append("不适用")
            elif source_id == "atop_v5_1" and target_year == 2022:
                cells.append("无目标年观测")
            else:
                cells.append(f"{int(row.rows_with_observed_values)}/12")
        lines.append(f"| {label} | {cells[0]} | {cells[1]} | {explanation} |")
    bis17 = coverage_lookup[("bis_federal_register_reviewed_subset", 2017)]
    bis22 = coverage_lookup[("bis_federal_register_reviewed_subset", 2022)]
    cdis17 = coverage_lookup[("imf_cdis_positions", 2017)]
    cdis22 = coverage_lookup[("imf_cdis_positions", 2022)]
    lines.extend([
        f"| BIS所选规则范围核对 | 12/12摘要行；{int(bis17.reviewed_subset_positive_hits)}个直接命中 | 12/12摘要行；{int(bis22.reviewed_subset_positive_hits)}个直接命中 | 摘要完整不等于覆盖全部BIS规则 |",
        f"| IMF CDIS任一方向有报告 | {int(cdis17.rows_with_observed_values)}/12（流入{int(cdis17.cdis_inward_values_reported)}/12、流出{int(cdis17.cdis_outward_values_reported)}/12） | {int(cdis22.rows_with_observed_values)}/12（流入{int(cdis22.cdis_inward_values_reported)}/12、流出{int(cdis22.cdis_outward_values_reported)}/12） | 2022行对应2021观测；空值不补0 |",
        "| GDELT、GTA/CSL | 未接入 | 未接入 | 缺少可复现事件导出或企业/产品匹配键，不生成国家分数 |",
        "",
        f"来源映射与连接检查：{int((checks_df['status'] == 'PASS').sum())}/{len(checks_df)} 通过。它们核对来源连接、字段血缘、缺失与口径边界，不是指数准确率、因果效度或预测能力。",
        "",
    ])
    report_text = "\n".join(lines)
    REPORT.write_text(report_text, encoding="utf-8")
    (PROJECT_ROOT / "outputs").mkdir(exist_ok=True)
    (PROJECT_ROOT / "outputs" / "multisource_integration_checks.csv").write_bytes(CHECKS.read_bytes())
    (PROJECT_ROOT / "outputs" / "source_registry.csv").write_bytes((OUTPUT_DIR / REGISTRY.name).read_bytes())
    (PROJECT_ROOT / "outputs" / "field_lineage.csv").write_bytes(LINEAGE.read_bytes())
    (PROJECT_ROOT / "outputs" / "source_coverage_by_year.csv").write_bytes(COVERAGE.read_bytes())
    (PROJECT_ROOT / "outputs" / REPORT.name).write_text(report_text, encoding="utf-8")

    append_progress(
        "Multi-source integration audit",
        "complete" if checks_df["status"].eq("PASS").all() else "failed checks require follow-up",
        [
            f"Generated a {len(registry)}-source registry, field-level lineage for {len(lineage_df)} panel columns, target-year coverage for {len(coverage_df)} source/year rows, aggregate SHA-256 provenance, and {len(checks_df)} connection checks.",
            f"Checks passed: {int(checks_df['status'].eq('PASS').sum())}/{len(checks_df)}.",
            f"The P2 source conflict is explicit (Mexico raw ATOP=1 vs OAS-audited active treaty=0); 2022 P2 values align to their official-source coding table.",
            f"CDIS lag mapping and P3 non-exhaustive evidence scope were checked; absent context values remain missing and are not part of the score.",
        ],
    )
    print(checks_df.to_string(index=False))
    print(f"Registry: {REGISTRY}; report: {REPORT}")
    return 0 if checks_df["status"].eq("PASS").all() else 1


if __name__ == "__main__":
    raise SystemExit(main())
