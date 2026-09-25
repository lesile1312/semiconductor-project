"""Build a conservative full-text legal-scope review queue for BIS P3 events."""
from __future__ import annotations
import re
import shutil
import pandas as pd
from gtri_config import COUNTRIES, PROCESSED_DIR, PROJECT_ROOT, RAW_DIR, append_progress, ensure_directories

EVIDENCE = PROCESSED_DIR / "bis_p3_evidence_coded_2017_2022.csv"
MANIFEST = RAW_DIR / "bis" / "document_detail_manifest.csv"
OUTPUT = PROCESSED_DIR / "bis_p3_fulltext_scope_coding_queue.csv"
SAMPLE_ALIASES = {r["country"]: {"South Korea": ("South Korea", "Republic of Korea", "Korea, South"), "Vietnam": ("Vietnam", "Viet Nam")}.get(r["country"], (r["country"],)) for r in COUNTRIES}
DIRECT_TERMS = ("semiconductor", "advanced computing", "supercomputer", "integrated circuit", "microelectronic", "semiconductor manufacturing")
ACTION_TERMS = ("addition", "additions", "export control", "commerce control list", "license requirement", "entity list", "removal", "revision", "sanction")

def snippets(text: str, patterns: tuple[str, ...], radius: int = 220) -> list[str]:
    found = []
    for term in patterns:
        for match in re.finditer(re.escape(term), text, flags=re.IGNORECASE):
            s = re.sub(r"\s+", " ", text[max(0, match.start()-radius):min(len(text), match.end()+radius)]).strip()
            if s not in found: found.append(s)
    return found[:20]

def main() -> int:
    ensure_directories()
    evidence = pd.read_csv(EVIDENCE, dtype={"document_number": "string"})
    manifest = pd.read_csv(MANIFEST, dtype={"document_number": "string"})
    rows = []
    for _, event in evidence.merge(manifest, on="document_number", how="left", validate="one_to_one").iterrows():
        available = event.get("raw_text_status") == "downloaded" and pd.notna(event.get("raw_text_path"))
        text = (PROJECT_ROOT / str(event["raw_text_path"])).read_text(encoding="utf-8", errors="replace") if available else ""
        direct = sorted({t for t in DIRECT_TERMS if t.lower() in text.lower()})
        actions = sorted({t for t in ACTION_TERMS if t.lower() in text.lower()})
        candidates = [c for c, aliases in SAMPLE_ALIASES.items() if any(re.search(r"(?<![A-Za-z])"+re.escape(a)+r"(?![A-Za-z])", text, re.I) for a in aliases)]
        priority = "blocked_no_full_text" if not available else ("highest_direct_rule_and_sample_country" if direct and candidates else "high_direct_rule_scope_review" if direct else "medium_entity_or_destination_scope_review" if candidates else "lower_no_sample_country_literal_match")
        rows.append({"event_year": event["event_year"], "publication_date": event["publication_date"], "document_number": event["document_number"], "title": event["title"], "full_text_available": bool(available), "direct_semiconductor_terms_in_full_text": "; ".join(direct) or pd.NA, "restrictive_or_relief_action_terms_in_full_text": "; ".join(actions) or pd.NA, "sample_country_literal_candidates": "; ".join(candidates) or pd.NA, "destination_or_scope_evidence_snippets": " || ".join(snippets(text, ("under the destination of", "destination", "located in", "entity list", "license requirement"))) or pd.NA, "review_priority": priority, "legal_scope_review_status": "pending_manual_review", "p3_merge_ready": False, "coding_note": "Automated lexical evidence locator only; country mention is not a legal target finding."})
    queue = pd.DataFrame(rows).sort_values(["event_year", "review_priority", "document_number"])
    if queue["document_number"].duplicated().any(): raise ValueError("Duplicate document_number in scope review queue")
    queue.to_csv(OUTPUT, index=False, encoding="utf-8-sig")
    public = PROJECT_ROOT / "outputs"; public.mkdir(exist_ok=True); shutil.copy2(OUTPUT, public / OUTPUT.name)
    append_progress("BIS P3 full-text scope review queue", "complete as non-merge-ready evidence locator", [f"Built one review row per {len(queue)} candidate document from archived official full text.", f"Review-priority counts: {queue['review_priority'].value_counts().to_dict()}.", f"Wrote evidence snippets and lexical candidates to {OUTPUT.as_posix()}.", "The queue does not determine legal targets, severity, or country-level P3 exposure; manual review remains required."])
    print(queue[["event_year", "document_number", "review_priority", "direct_semiconductor_terms_in_full_text", "sample_country_literal_candidates", "p3_merge_ready"]].to_string(index=False))
    return 0
if __name__ == "__main__": raise SystemExit(main())
