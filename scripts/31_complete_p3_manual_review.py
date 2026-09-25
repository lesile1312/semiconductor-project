"""Publish the human-coded BIS candidate review table and a scoped summary."""

from __future__ import annotations

import pandas as pd

from gtri_config import COUNTRIES, OUTPUT_DIR, PROCESSED_DIR, RAW_DIR, YEARS, append_progress, ensure_directories


INPUT = RAW_DIR / "bis" / "bis_p3_manual_review_completed_2017_2022.csv"
EXPECTED_COLUMNS = {
    "event_year", "document_number", "sample_country_literal_candidates", "action_type",
    "direction", "semiconductor_relevance", "manual_scope_finding", "official_source", "review_status",
}


def main() -> int:
    ensure_directories()
    if not INPUT.is_file():
        raise FileNotFoundError(f"Human-reviewed BIS source table is missing: {INPUT}")

    reviewed = pd.read_csv(INPUT, keep_default_na=False)
    missing_columns = EXPECTED_COLUMNS - set(reviewed.columns)
    if missing_columns:
        raise RuntimeError(f"BIS manual-review schema missing columns: {sorted(missing_columns)}")
    if reviewed.empty or reviewed["document_number"].duplicated().any():
        raise RuntimeError("BIS manual-review table must contain unique, non-empty document numbers")
    if not reviewed["review_status"].eq("reviewed").all():
        raise RuntimeError("Only rows marked reviewed may be published as manually reviewed evidence")
    if not reviewed["official_source"].str.startswith("https://www.federalregister.gov/").all():
        raise RuntimeError("BIS review rows must point to official Federal Register sources")
    if not set(pd.to_numeric(reviewed["event_year"], errors="raise").astype(int)).issubset(YEARS):
        raise RuntimeError("BIS manual-review table contains an out-of-scope year")

    reviewed_path = PROCESSED_DIR / "bis_p3_manual_review_completed_2017_2022.csv"
    reviewed.to_csv(reviewed_path, index=False, encoding="utf-8-sig")
    review_lookup = {
        (int(row.event_year), country)
        for row in reviewed.itertuples(index=False)
        for country in str(row.sample_country_literal_candidates).split("; ")
        if country
    }

    direct_positive = reviewed[
        reviewed["direction"].eq("increase")
        & reviewed["semiconductor_relevance"].eq("yes_direct")
        & reviewed["review_status"].eq("reviewed")
    ]
    positive_lookup: dict[tuple[int, str], int] = {}
    for row in direct_positive.itertuples(index=False):
        for country in str(row.sample_country_literal_candidates).split("; "):
            if country:
                key = (int(row.event_year), country)
                positive_lookup[key] = positive_lookup.get(key, 0) + 1

    summary_rows = []
    for year in YEARS:
        for economy in COUNTRIES:
            summary_rows.append(
                {
                    "country": economy["country"],
                    "iso3": economy["iso3"],
                    "year": year,
                    "reviewed_candidate_literal_count": sum(
                        1 for row_year, country in review_lookup if row_year == year and country == economy["country"]
                    ),
                    "direct_semiconductor_increase_events": positive_lookup.get((year, economy["country"]), 0),
                    "p3_direct_increase_within_reviewed_subset": int(
                        positive_lookup.get((year, economy["country"]), 0) > 0
                    ),
                    "scope": "selected_reviewed_candidate_events_only_not_exhaustive",
                    "scoring_status": "evidence_only_not_scored",
                    "notes": "Zero means no positive finding in the selected reviewed candidate set; it does not establish no exposure outside that set.",
                }
            )

    summary = pd.DataFrame(summary_rows)
    if len(summary) != len(COUNTRIES) * len(YEARS) or summary.duplicated(["iso3", "year"]).any():
        raise RuntimeError("BIS summary must have a unique 12-economy x 2-year grid")
    summary_path = PROCESSED_DIR / "bis_p3_country_year_reviewed_summary.csv"
    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    reviewed.to_csv(OUTPUT_DIR / reviewed_path.name, index=False, encoding="utf-8-sig")
    summary.to_csv(OUTPUT_DIR / summary_path.name, index=False, encoding="utf-8-sig")

    append_progress(
        "BIS selected-candidate manual-review evidence",
        "complete for supplied 10-rule review set; non-exhaustive and non-scoring",
        [
            f"Validated and published {len(reviewed)} human-coded Federal Register candidate rules and {len(summary)} country-year evidence rows.",
            f"Found {len(direct_positive)} reviewed direct semiconductor-related increase rule(s); country-year hits={int(summary['p3_direct_increase_within_reviewed_subset'].sum())}.",
            "Country names in a rule are retained as literal candidate mentions unless the manual scope finding establishes direct semiconductor relevance; no country-level absence claim is made.",
            "This selected-rule review table is joined as a non-scoring evidence layer and does not constitute an exhaustive P3 event census or legal advice.",
        ],
    )
    print(f"reviewed_rules={len(reviewed)}; country_year_rows={len(summary)}; positive_hits={int(summary['p3_direct_increase_within_reviewed_subset'].sum())}")
    print(summary[summary["p3_direct_increase_within_reviewed_subset"].eq(1)].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
