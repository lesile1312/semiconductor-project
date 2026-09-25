"""Prepare a human-review packet for highest-priority BIS P3 rules."""
from __future__ import annotations
import re
import shutil
import pandas as pd
from gtri_config import PROCESSED_DIR, PROJECT_ROOT, append_progress, ensure_directories

QUEUE = PROCESSED_DIR / "bis_p3_fulltext_scope_coding_queue.csv"
OUTPUT = PROCESSED_DIR / "bis_p3_manual_review_packet_high_priority.csv"
READ_ME = PROJECT_ROOT / "docs" / "bis_p3_manual_review_instructions.md"

def extract_context(text: str, terms: list[str], radius: int = 700) -> str:
    hits = []
    for term in terms:
        m = re.search(re.escape(term), text, flags=re.I)
        if m:
            s = re.sub(r"\s+", " ", text[max(0, m.start()-radius):min(len(text), m.end()+radius)]).strip()
            if s not in hits: hits.append(s)
    return " || ".join(hits[:5])

def main() -> int:
    ensure_directories()
    queue = pd.read_csv(QUEUE, dtype={"document_number": "string"})
    selected = queue[queue["review_priority"] == "highest_direct_rule_and_sample_country"].copy()
    rows = []
    for _, event in selected.iterrows():
        path = PROJECT_ROOT / "data" / "raw" / "bis" / "documents" / f"{event['document_number']}.txt"
        text = path.read_text(encoding="utf-8", errors="replace")
        sample = [x.strip() for x in str(event["sample_country_literal_candidates"]).split(";") if x.strip()]
        evidence_terms = [x.strip() for x in str(event["direct_semiconductor_terms_in_full_text"]).split(";") if x.strip()]
        rows.append({
            "event_year": event["event_year"], "publication_date": event["publication_date"], "document_number": event["document_number"], "title": event["title"],
            "official_full_text_path": str(path.relative_to(PROJECT_ROOT)), "sample_country_literal_candidates": "; ".join(sample),
            "direct_terms": "; ".join(evidence_terms), "action_terms": event["restrictive_or_relief_action_terms_in_full_text"],
            "evidence_context": extract_context(text, evidence_terms + ["destination", "Entity List", "license requirement"]),
            "review_question_1_is_sample_country_a_legal_target": "",
            "review_question_2_rule_scope_or_entity_scope": "",
            "review_question_3_restriction_direction": "",
            "review_question_4_semiconductor_relevance": "",
            "review_question_5_evidence_page_or_section": "",
            "reviewer_name": "", "review_date": "", "p3_merge_ready": False,
            "review_note": "Fill only after reading the official full text; do not infer target status from literal mentions.",
        })
    packet = pd.DataFrame(rows)
    packet.to_csv(OUTPUT, index=False, encoding="utf-8-sig")
    READ_ME.write_text(
        "# BIS P3最高优先级人工复核说明\n\n"
        "本复核包只包含4条同时满足“全文命中直接半导体词 + 命中12国样本经济体字面提及”的规则。\n\n"
        "请逐条打开 `official_full_text_path` 指向的官方纯文本，确认：\n\n"
        "1. 样本国是否是法律文本明确指定的目的地、实体所在地或适用范围，而不是背景叙述、例示或引用；\n"
        "2. 规则对象是技术范围、实体清单对象还是其他行政事项；\n"
        "3. 行动方向是新增限制、修改、移除/缓解还是混合；\n"
        "4. 半导体相关性是否足以支持P3历史政策冲击标记；\n"
        "5. 记录页码、章节标题或原文定位。\n\n"
        "完成前不得填写 `p3_merge_ready`，不得把国家字面提及直接转换为国家暴露分数。\n",
        encoding="utf-8",
    )
    public = PROJECT_ROOT / "outputs"; public.mkdir(exist_ok=True)
    for path in (OUTPUT, READ_ME): shutil.copy2(path, public / path.name)
    append_progress("BIS P3 highest-priority manual review packet", "complete", [f"Prepared {len(packet)} direct-rule review rows with official full-text paths and evidence contexts.", f"Wrote reviewer-fillable packet to {OUTPUT.as_posix()}.", "Reviewer decisions remain blank and p3_merge_ready remains False for every row."])
    print(packet[["event_year", "document_number", "sample_country_literal_candidates", "direct_terms", "p3_merge_ready"]].to_string(index=False))
    return 0
if __name__ == "__main__": raise SystemExit(main())
