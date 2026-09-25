"""Record conservative preliminary categories for remaining direct-rule candidates."""
from __future__ import annotations
import shutil
import pandas as pd
from gtri_config import PROCESSED_DIR, PROJECT_ROOT, append_progress, ensure_directories

INPUT = PROCESSED_DIR / "bis_p3_fulltext_scope_coding_queue.csv"
OUTPUT = PROCESSED_DIR / "bis_p3_preliminary_review_remaining_high.csv"
CATEGORIES = {
    "2022-07211": ("administrative_comment", "No sample-country candidate; public-comment notice rather than a binding control.", "administrative", 1),
    "2022-17125": ("technology_control_rule", "No sample-country candidate in lexical scan; Wassenaar implementation requires scope review.", "increase", 3),
    "2022-18268": ("entity_list_related", "No sample-country candidate; microelectronic wording needs entity-level review.", "increase", 2),
    "2022-21520": ("entity_list_related", "No sample-country candidate; semiconductor wording needs entity-level review.", "increase", 2),
    "2022-21658": ("technology_control_rule", "No sample-country candidate in lexical scan; major advanced-computing and semiconductor rule requires scope review.", "increase", 5),
    "2022-22037": ("administrative_briefing", "No sample-country candidate; public-briefing procedure rather than a binding control.", "administrative", 1),
    "2022-26662": ("technology_control_rule", "No sample-country candidate in lexical scan; advanced-computing and semiconductor scope requires review.", "increase", 5),
    "2022-27149": ("entity_list_related", "No sample-country candidate; microelectronic wording needs entity-level review.", "increase", 2),
}

def main() -> int:
    ensure_directories()
    q = pd.read_csv(INPUT, dtype={"document_number": "string"})
    selected = q[q.document_number.isin(CATEGORIES)].copy()
    if set(selected.document_number) != set(CATEGORIES): raise ValueError("Candidate set mismatch")
    rows=[]
    for _, r in selected.iterrows():
        scope, target_note, direction, severity = CATEGORIES[str(r.document_number)]
        rows.append({**r.to_dict(), "preliminary_semiconductor_scope": scope, "preliminary_target_scope": target_note, "preliminary_direction": direction, "preliminary_severity": severity, "review_status": "AI_assisted_preliminary_review_pending_human_legal_confirmation", "p3_merge_ready": False})
    out=pd.DataFrame(rows).sort_values(["event_year","document_number"])
    out.to_csv(OUTPUT,index=False,encoding="utf-8-sig")
    public=PROJECT_ROOT/"outputs"; public.mkdir(exist_ok=True); shutil.copy2(OUTPUT,public/OUTPUT.name)
    append_progress("BIS P3 remaining high-priority preliminary review", "complete but non-merge-ready", [f"Recorded preliminary categories for {len(out)} remaining high/direct candidates.", "Administrative notices, technology-control rules, and Entity List-related events are separated.", "All rows remain pending human legal confirmation and p3_merge_ready=False."])
    print(out[["document_number","preliminary_semiconductor_scope","preliminary_direction","preliminary_severity","p3_merge_ready"]].to_string(index=False)); return 0
if __name__ == "__main__": raise SystemExit(main())
