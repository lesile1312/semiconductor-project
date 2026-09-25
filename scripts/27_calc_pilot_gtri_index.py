"""Calculate an auditable pilot GTRI-v0 index.

The pilot index closes the competition deliverable without pretending that the
unfinished BIS P3 legal coding is ready for country scoring. It uses only
available, reproducible fields and keeps the transformed component scores.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from gtri_config import OUTPUT_DIR, PROJECT_ROOT, append_progress, ensure_directories


COMPONENTS = [
    ("p1_unga_relative_alignment", "risk_p1_unga"),
    ("p2_us_formal_alliance", "risk_p2_active_formal_defense_tie"),
    ("n1_electronics_foreign_va_share", "risk_n1_tiva"),
    ("n2_china_hs8542_import_share", "risk_n2_china_input"),
    ("n3_us_hs8542_export_share", "risk_n3_us_market"),
    ("n4_dual_dependency", "risk_n4_dual_dependency"),
    ("v1_hs8542_import_hhi", "risk_v1_import_concentration"),
]


def minmax(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    lo, hi = s.min(skipna=True), s.max(skipna=True)
    if pd.isna(lo) or pd.isna(hi) or hi == lo:
        return pd.Series([0.0] * len(s), index=s.index)
    return (s - lo) / (hi - lo)


def main() -> int:
    ensure_directories()
    panel = pd.read_csv(OUTPUT_DIR / "master_country_year.csv")
    out = panel[["country", "iso3", "year"]].copy()

    for raw, score in COMPONENTS:
        out[score] = minmax(panel[raw])

    # V2 is protective: more effective supplier countries means lower risk.
    out["risk_v2_low_supplier_diversity"] = 1 - minmax(panel["v2_effective_supplier_count"])

    score_cols = [score for _, score in COMPONENTS] + ["risk_v2_low_supplier_diversity"]
    out["gtri_v0_equal_weight"] = out[score_cols].mean(axis=1)

    theory_weights = {
        "risk_p1_unga": 0.125,
        "risk_p2_active_formal_defense_tie": 0.075,
        "risk_n1_tiva": 0.10,
        "risk_n2_china_input": 0.15,
        "risk_n3_us_market": 0.15,
        "risk_n4_dual_dependency": 0.20,
        "risk_v1_import_concentration": 0.10,
        "risk_v2_low_supplier_diversity": 0.10,
    }
    out["gtri_v0_theory_weight"] = sum(out[col] * w for col, w in theory_weights.items())

    out["rank_equal_weight_within_year"] = out.groupby("year")["gtri_v0_equal_weight"].rank(
        ascending=False, method="min"
    ).astype(int)
    out["rank_theory_weight_within_year"] = out.groupby("year")["gtri_v0_theory_weight"].rank(
        ascending=False, method="min"
    ).astype(int)

    out["index_scope"] = (
        "pilot_v0; uses target-year P2 evidence with source break documented; "
        "excludes non-exhaustive BIS P3 and non-scoring IMF CDIS context"
    )

    index_path = OUTPUT_DIR / "pilot_gtri_v0_index.csv"
    out.to_csv(index_path, index=False, encoding="utf-8-sig")
    out.to_csv(PROJECT_ROOT / "outputs" / "pilot_gtri_v0_index.csv", index=False, encoding="utf-8-sig")

    latest = out[out["year"] == 2022].sort_values("rank_equal_weight_within_year")
    md = [
        "# GTRI-v0 试点指数排名",
        "",
        "说明：本排名使用目标年份可核验的P2来源：2017为ATOP观察值（墨西哥另按OAS退约状态修正），2022逐国核对美国国务院《Treaties in Force 2020》及2021—2023补编、目标年双边资料与NATO成员年份。跨年P2存在来源方法变化，ATOP 2018结构字段另行保留。BIS P3是有限候选集证据、CDIS为非半导体专项且滞后的背景层，均未并入总分。",
        "",
        "## 2022等权基准排名",
        "",
        "| rank | country | GTRI-v0 | N4 | V1 | V2 |",
        "| ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    for _, r in latest.iterrows():
        panel_row = panel[(panel["country"] == r["country"]) & (panel["year"] == 2022)].iloc[0]
        md.append(
            f"| {int(r['rank_equal_weight_within_year'])} | {r['country']} | "
            f"{r['gtri_v0_equal_weight']:.3f} | {panel_row['n4_dual_dependency']:.4f} | "
            f"{panel_row['v1_hs8542_import_hhi']:.3f} | {int(panel_row['v2_effective_supplier_count'])} |"
        )
    md.append("")
    md.append("## 解释边界")
    md.append("")
    md.append("- 排名是筛查顺序，不是投资结论或法律意见。")
    md.append("- 等权版强调透明；理论权重版提高N4双重依赖权重，用于稳健性对照。")
    md.append("- 企业落地时应回到N2、N3、N4、V1和V2的结构画像，而不是只看总分。")
    (PROJECT_ROOT / "docs" / "pilot_gtri_v0_index.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    append_progress(
        "Pilot GTRI-v0 index closure",
        "complete",
        [
            "Generated pilot_gtri_v0_index.csv with equal-weight and theory-weight scores.",
            "P2 now uses target-year source-aware values; ATOP 2018 remains a separate structural cross-reference, not a 2022 observation.",
            "Non-exhaustive BIS P3 candidate evidence and lagged IMF CDIS context remain outside the score.",
        ],
    )
    print(index_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
