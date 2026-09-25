"""First-pass rule-based coding for BIS P3 evidence.

The output is an event-level evidence table. It intentionally does not create a
country-year P3 score because the mapping from legal scope to third-country
exposure needs manual legal-text review and a pre-specified exposure formula.
"""

from __future__ import annotations

import re
import shutil

import pandas as pd

from gtri_config import COUNTRIES, PROCESSED_DIR, PROJECT_ROOT, append_progress, ensure_directories


INPUT = PROCESSED_DIR / "bis_p3_candidate_events_2017_2022.csv"
OUTPUT = PROCESSED_DIR / "bis_p3_evidence_coded_2017_2022.csv"
SUMMARY_OUTPUT = PROCESSED_DIR / "bis_p3_country_year_evidence_summary.csv"
DOC_PATH = PROJECT_ROOT / "docs" / "p3_bis_coding_protocol.md"

DIRECT_SEMICON_TYPES = {"direct_semiconductor_or_advanced_computing"}
DIRECT_TERMS = (
    "semiconductor",
    "advanced computing",
    "supercomputer",
    "integrated circuit",
    "microelectronic",
)

COUNTRY_ALIASES = {
    "Malaysia": ["Malaysia"],
    "Vietnam": ["Vietnam", "Viet Nam"],
    "Singapore": ["Singapore"],
    "Thailand": ["Thailand"],
    "India": ["India"],
    "Indonesia": ["Indonesia"],
    "Philippines": ["Philippines"],
    "Japan": ["Japan"],
    "South Korea": ["South Korea", "Korea, South", "Republic of Korea"],
    "Mexico": ["Mexico"],
    "Germany": ["Germany"],
    "Netherlands": ["Netherlands"],
    "China": ["China", "Hong Kong", "Macau", "Macao"],
    "Russia": ["Russia", "Russian"],
    "Belarus": ["Belarus"],
    "Turkey": ["Turkey"],
    "Pakistan": ["Pakistan"],
    "United Arab Emirates": ["United Arab Emirates", "UAE"],
    "Armenia": ["Armenia"],
    "Greece": ["Greece"],
    "United Kingdom": ["United Kingdom", "U.K.", "UK"],
    "Switzerland": ["Switzerland"],
}

SAMPLE_COUNTRIES = {country["country"] for country in COUNTRIES}


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def _find_country_targets(text: str) -> list[str]:
    matches: list[str] = []
    for canonical, aliases in COUNTRY_ALIASES.items():
        for alias in aliases:
            pattern = r"(?<![A-Za-z])" + re.escape(alias) + r"(?![A-Za-z])"
            if re.search(pattern, text, flags=re.IGNORECASE):
                matches.append(canonical)
                break
    return sorted(set(matches))


def _classify_direction(title: str, abstract: str) -> str:
    text = f"{title} {abstract}".lower()
    increase_terms = (
        "addition",
        "additions",
        "adds",
        "added",
        "commerce control list",
        "imposition",
        "implementation of certain",
        "sanctions",
        "additional export controls",
        "implementation of additional",
        "license requirement",
        "new controls",
    )
    decrease_terms = (
        "removal",
        "removes",
        "temporary general license",
        "extension of validity",
    )
    administrative_terms = (
        "request for public comments",
        "public briefing",
        "information collection",
        "correction",
        "procedures for access",
    )
    has_increase = any(term in text for term in increase_terms)
    has_decrease = any(term in text for term in decrease_terms)
    has_admin = any(term in text for term in administrative_terms)
    if has_increase and has_decrease:
        return "mixed"
    if has_increase:
        return "increase"
    if has_decrease:
        return "decrease"
    if has_admin:
        return "administrative"
    return "needs_manual_review"


def _severity(row: pd.Series, direction: str, semicon_status: str) -> float | pd.NA:
    text = f"{row['title']} {row['abstract']}".lower()
    if direction == "administrative":
        return 1
    if semicon_status == "yes_direct" and (
        "advanced computing" in text
        or "semiconductor manufacturing" in text
        or "supercomputer" in text
    ):
        return 5
    if "wassenaar" in text or "commerce control list" in text:
        return 3
    if "sanctions" in text:
        return 4
    if direction == "increase":
        return 2
    if direction == "decrease":
        return 1
    return pd.NA


def code_row(row: pd.Series) -> dict:
    title = str(row.get("title", ""))
    abstract = str(row.get("abstract", ""))
    text = f"{title} {abstract}"
    direct = row.get("candidate_type") in DIRECT_SEMICON_TYPES or _contains_any(text, DIRECT_TERMS)
    countries = _find_country_targets(text)
    direction = _classify_direction(title, abstract)
    if direct and direction != "administrative":
        semicon_status = "yes_direct"
        event_scope = "direct_semiconductor_rule"
    elif direct:
        semicon_status = "administrative_or_comment"
        event_scope = "direct_semiconductor_rule"
    else:
        semicon_status = "needs_manual_review"
        event_scope = "entity_list_event"

    if countries:
        target_status = "coded_from_title_abstract"
        target_in_sample = int(bool(SAMPLE_COUNTRIES.intersection(countries)))
    else:
        target_status = "needs_full_text_or_rule_scope_review"
        target_in_sample = pd.NA

    severity = _severity(row, direction, semicon_status)
    if pd.isna(severity) or semicon_status == "needs_manual_review":
        severity_status = "needs_manual_review"
    else:
        severity_status = "rule_based_first_pass"

    return {
        "p3_event_scope": event_scope,
        "country_target": "; ".join(countries) if countries else pd.NA,
        "country_target_coding_status": target_status,
        "target_in_sample": target_in_sample,
        "semiconductor_related_status": semicon_status,
        "restriction_direction": direction,
        "severity_rule_based": severity,
        "severity_coding_status": severity_status,
        "p3_merge_ready": False,
        "p3_coding_notes": (
            "First-pass metadata coding only; do not merge into master panel until full-text review and exposure formula are approved."
        ),
    }


def main() -> int:
    ensure_directories()
    if not INPUT.exists():
        raise FileNotFoundError(f"Missing BIS candidate table: {INPUT}")
    if not DOC_PATH.exists():
        raise FileNotFoundError(f"Missing P3 coding protocol: {DOC_PATH}")

    source = pd.read_csv(INPUT)
    if source["document_number"].duplicated().any():
        dupes = source.loc[source["document_number"].duplicated(), "document_number"].tolist()
        raise ValueError(f"Duplicate document_number values in candidate table: {dupes}")

    generated_columns = {
        "country_target",
        "country_target_coding_status",
        "semiconductor_related_status",
        "severity_rule_based",
        "severity_coding_status",
    }
    source_for_output = source.drop(columns=[c for c in generated_columns if c in source.columns])
    coded = pd.concat(
        [source_for_output.reset_index(drop=True), pd.DataFrame([code_row(row) for _, row in source.iterrows()])],
        axis=1,
    )
    coded.to_csv(OUTPUT, index=False, encoding="utf-8-sig")

    exploded = coded.assign(country_target=coded["country_target"].str.split("; ")).explode("country_target")
    summary = (
        exploded.dropna(subset=["country_target"])
        .groupby(["event_year", "country_target"], as_index=False)
        .agg(
            p3_candidate_events=("document_number", "count"),
            direct_semiconductor_events=("semiconductor_related_status", lambda s: int((s == "yes_direct").sum())),
            restriction_increase_events=("restriction_direction", lambda s: int((s == "increase").sum())),
            restriction_decrease_events=("restriction_direction", lambda s: int((s == "decrease").sum())),
            mixed_direction_events=("restriction_direction", lambda s: int((s == "mixed").sum())),
            metadata_only_events_needing_manual_review=(
                "severity_coding_status",
                lambda s: int((s == "needs_manual_review").sum()),
            ),
        )
        .sort_values(["event_year", "country_target"])
    )
    summary.to_csv(SUMMARY_OUTPUT, index=False, encoding="utf-8-sig")

    public_outputs = PROJECT_ROOT / "outputs"
    public_outputs.mkdir(exist_ok=True)
    for path in (OUTPUT, SUMMARY_OUTPUT, DOC_PATH):
        shutil.copy2(path, public_outputs / path.name)

    status_counts = coded["semiconductor_related_status"].value_counts(dropna=False).to_dict()
    target_status = coded["country_target_coding_status"].value_counts(dropna=False).to_dict()
    append_progress(
        "BIS P3 first-pass coding",
        "complete as non-merge-ready evidence",
        [
            f"Coded {len(coded)} candidate Federal Register events using docs/p3_bis_coding_protocol.md.",
            f"Semiconductor status counts: {status_counts}.",
            f"Country-target coding status counts: {target_status}.",
            f"Wrote event evidence to {OUTPUT.as_posix()} and country-year evidence summary to {SUMMARY_OUTPUT.as_posix()}.",
            "No country-level P3 score was generated; p3_merge_ready is False for every row.",
        ],
    )
    print(coded[["event_year", "document_number", "p3_event_scope", "country_target", "semiconductor_related_status", "restriction_direction", "severity_rule_based", "p3_merge_ready"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
