"""Extract auditable country mentions and short contexts from BIS full text."""

from __future__ import annotations

import re
import shutil

import pandas as pd

from gtri_config import COUNTRIES, PROCESSED_DIR, PROJECT_ROOT, RAW_DIR, append_progress, ensure_directories


INPUT = PROCESSED_DIR / "bis_p3_evidence_coded_2017_2022.csv"
MANIFEST = RAW_DIR / "bis" / "document_detail_manifest.csv"
OUTPUT = PROCESSED_DIR / "bis_p3_country_mentions_fulltext_2017_2022.csv"
COVERAGE = PROCESSED_DIR / "bis_p3_fulltext_review_coverage.csv"
REVIEW_QUEUE = PROCESSED_DIR / "bis_p3_sample_country_review_queue.csv"

ALIASES = {
    "Malaysia": ("Malaysia",),
    "Vietnam": ("Vietnam", "Viet Nam"),
    "Singapore": ("Singapore",),
    "Thailand": ("Thailand",),
    "India": ("India",),
    "Indonesia": ("Indonesia",),
    "Philippines": ("Philippines",),
    "Japan": ("Japan",),
    "South Korea": ("South Korea", "Republic of Korea", "Korea, South"),
    "Mexico": ("Mexico",),
    "Germany": ("Germany",),
    "Netherlands": ("Netherlands",),
    "China": ("China", "People's Republic of China", "PRC", "Hong Kong", "Macau", "Macao"),
    "Russia": ("Russia", "Russian Federation"),
    "Belarus": ("Belarus",),
    "Turkey": ("Turkey", "Türkiye"),
    "Pakistan": ("Pakistan",),
    "Iran": ("Iran",),
    "United Arab Emirates": ("United Arab Emirates", "UAE"),
    "Armenia": ("Armenia",),
    "United Kingdom": ("United Kingdom", "U.K."),
    "Switzerland": ("Switzerland",),
}
SAMPLE = {row["country"] for row in COUNTRIES}


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def contexts(text: str, alias: str, radius: int = 180) -> list[str]:
    pattern = re.compile(r"(?<![A-Za-z])" + re.escape(alias) + r"(?![A-Za-z])", re.IGNORECASE)
    snippets: list[str] = []
    for match in pattern.finditer(text):
        snippet = normalize_space(text[max(0, match.start() - radius) : min(len(text), match.end() + radius)])
        if snippet not in snippets:
            snippets.append(snippet)
    return snippets


def main() -> int:
    ensure_directories()
    evidence = pd.read_csv(INPUT, dtype={"document_number": "string"})
    manifest = pd.read_csv(MANIFEST, dtype={"document_number": "string"})
    merged = evidence.merge(
        manifest[["document_number", "raw_text_status", "raw_text_path", "raw_text_sha256"]],
        on="document_number",
        how="left",
        validate="one_to_one",
    )

    rows: list[dict] = []
    coverage_rows: list[dict] = []
    for _, event in merged.iterrows():
        available = event.get("raw_text_status") == "downloaded" and pd.notna(event.get("raw_text_path"))
        countries_found: set[str] = set()
        mention_total = 0
        if available:
            path = PROJECT_ROOT / str(event["raw_text_path"])
            text = path.read_text(encoding="utf-8", errors="replace")
            for country, aliases in ALIASES.items():
                country_contexts: list[str] = []
                for alias in aliases:
                    country_contexts.extend(contexts(text, alias))
                country_contexts = list(dict.fromkeys(country_contexts))
                if country_contexts:
                    countries_found.add(country)
                    mention_total += len(country_contexts)
                    for sequence, context in enumerate(country_contexts, start=1):
                        rows.append(
                            {
                                "event_year": event["event_year"],
                                "publication_date": event["publication_date"],
                                "document_number": event["document_number"],
                                "title": event["title"],
                                "country_mentioned": country,
                                "country_in_12_economy_sample": country in SAMPLE,
                                "context_sequence": sequence,
                                "context": context,
                                "raw_text_sha256": event["raw_text_sha256"],
                                "source_flag": "Federal_Register_official_full_text_literal_match",
                                "review_status": "literal_mention_not_yet_legal_scope_coding",
                                "p3_merge_ready": False,
                            }
                        )
        coverage_rows.append(
            {
                "event_year": event["event_year"],
                "document_number": event["document_number"],
                "full_text_available": bool(available),
                "distinct_countries_mentioned": len(countries_found),
                "sample_countries_mentioned": "; ".join(sorted(countries_found & SAMPLE)) or pd.NA,
                "all_countries_mentioned": "; ".join(sorted(countries_found)) or pd.NA,
                "context_rows": mention_total,
                "legal_scope_review_status": "pending_manual_review",
                "p3_merge_ready": False,
            }
        )

    mentions = pd.DataFrame(rows)
    coverage = pd.DataFrame(coverage_rows)
    if not mentions.empty and mentions.duplicated(["document_number", "country_mentioned", "context_sequence"]).any():
        raise ValueError("Duplicate country-context evidence key detected.")
    mentions.to_csv(OUTPUT, index=False, encoding="utf-8-sig")
    coverage.to_csv(COVERAGE, index=False, encoding="utf-8-sig")

    if mentions.empty:
        review_queue = pd.DataFrame(
            columns=[
                "event_year", "publication_date", "document_number", "title",
                "country_mentioned", "literal_context_count", "first_context",
                "legal_scope_review_status", "p3_merge_ready",
            ]
        )
    else:
        review_queue = (
            mentions.loc[mentions["country_in_12_economy_sample"]]
            .groupby(
                ["event_year", "publication_date", "document_number", "title", "country_mentioned"],
                as_index=False,
            )
            .agg(literal_context_count=("context", "count"), first_context=("context", "first"))
            .sort_values(["event_year", "document_number", "country_mentioned"])
        )
        review_queue["legal_scope_review_status"] = "pending_manual_review"
        review_queue["p3_merge_ready"] = False
    review_queue.to_csv(REVIEW_QUEUE, index=False, encoding="utf-8-sig")

    public_outputs = PROJECT_ROOT / "outputs"
    public_outputs.mkdir(exist_ok=True)
    for path in (OUTPUT, COVERAGE, REVIEW_QUEUE, MANIFEST):
        shutil.copy2(path, public_outputs / path.name)

    append_progress(
        "BIS P3 full-text country mention extraction",
        "complete as non-merge-ready evidence",
        [
            f"Full text was available for {int(coverage['full_text_available'].sum())} of {len(coverage)} candidate events.",
            f"Wrote {len(mentions)} literal country-context rows to {OUTPUT.as_posix()}.",
            f"Coverage and unresolved manual legal-scope status are recorded in {COVERAGE.as_posix()}.",
            f"Wrote {len(review_queue)} event-by-sample-country rows to the manual review queue {REVIEW_QUEUE.as_posix()}.",
            "Literal mentions are not treated as targeted exposure; every row remains p3_merge_ready=False.",
        ],
    )
    print(coverage.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
