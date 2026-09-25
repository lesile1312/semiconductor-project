"""Build competition-ready descriptive statistics and validation evidence."""

from __future__ import annotations

import shutil

import numpy as np
import pandas as pd

from gtri_config import DOCS_DIR, OUTPUT_DIR, PROJECT_ROOT, append_progress, ensure_directories


MASTER = OUTPUT_DIR / "master_country_year.csv"
DESCRIPTIVE = OUTPUT_DIR / "descriptive_statistics_2017_2022.csv"
CHANGE = OUTPUT_DIR / "country_indicator_changes_2017_2022.csv"
VALIDATION = OUTPUT_DIR / "measurement_validation_checks.csv"
REPORT = DOCS_DIR / "measurement_validation_report.md"

METRICS = {
    "p1_unga_relative_alignment": "P1 UNGA relative alignment",
    "p2_us_formal_alliance": "P2 active formal defense tie (source-aware)",
    "n1_electronics_foreign_va_share": "N1 electronics foreign value-added share",
    "n2_china_hs8542_import_share": "N2 China HS8542 import share",
    "n3_us_hs8542_export_share": "N3 US HS8542 export share",
    "n4_dual_dependency": "N4 dual dependency",
    "v1_hs8542_import_hhi": "V1 HS8542 import HHI",
    "v2_effective_supplier_count": "V2 effective supplier count",
}

BENCHMARKS = (
    ("Malaysia", 2022, "n2_china_hs8542_import_share", 0.1709, 0.0030),
    ("Malaysia", 2022, "n3_us_hs8542_export_share", 0.0788, 0.0030),
    ("Malaysia", 2022, "n4_dual_dependency", 0.0135, 0.0010),
    ("Malaysia", 2022, "v1_hs8542_import_hhi", 0.1480, 0.0050),
    ("Malaysia", 2022, "v2_effective_supplier_count", 13.0, 0.0),
    ("Vietnam", 2022, "n2_china_hs8542_import_share", 0.1805, 0.0030),
    ("Vietnam", 2022, "n3_us_hs8542_export_share", 0.0465, 0.0030),
    ("Vietnam", 2022, "n4_dual_dependency", 0.0084, 0.0010),
    ("Vietnam", 2022, "v1_hs8542_import_hhi", 0.2070, 0.0050),
    ("Vietnam", 2022, "v2_effective_supplier_count", 9.0, 0.0),
)


def to_markdown_table(frame: pd.DataFrame) -> str:
    """Render a compact Markdown table without optional tabulate dependency."""
    display = frame.copy()
    for column in display.columns:
        display[column] = display[column].map(
            lambda value: "" if pd.isna(value) else (f"{value:.6g}" if isinstance(value, (float, np.floating)) else str(value))
        )
    header = "| " + " | ".join(display.columns) + " |"
    divider = "| " + " | ".join("---" for _ in display.columns) + " |"
    body = ["| " + " | ".join(row) + " |" for row in display.astype(str).itertuples(index=False, name=None)]
    return "\n".join([header, divider, *body])


def descriptive_table(panel: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    for year in sorted(panel["year"].unique()):
        subset = panel.loc[panel["year"] == year]
        for field, label in METRICS.items():
            values = pd.to_numeric(subset[field], errors="coerce")
            rows.append(
                {
                    "year": year,
                    "indicator": field,
                    "indicator_label": label,
                    "n": int(values.notna().sum()),
                    "missing_n": int(values.isna().sum()),
                    "mean": values.mean(),
                    "std": values.std(ddof=1),
                    "min": values.min(),
                    "median": values.median(),
                    "max": values.max(),
                }
            )
    return pd.DataFrame(rows)


def change_table(panel: pd.DataFrame) -> pd.DataFrame:
    wide = panel.pivot(index=["country", "iso3"], columns="year", values=list(METRICS))
    rows: list[dict] = []
    for country, iso3 in wide.index:
        row = {"country": country, "iso3": iso3}
        for field in METRICS:
            value_2017 = wide.loc[(country, iso3), (field, 2017)]
            value_2022 = wide.loc[(country, iso3), (field, 2022)]
            row[f"{field}_2017"] = value_2017
            row[f"{field}_2022"] = value_2022
            row[f"{field}_change_2022_minus_2017"] = (
                value_2022 - value_2017 if pd.notna(value_2017) and pd.notna(value_2022) else np.nan
            )
        rows.append(row)
    return pd.DataFrame(rows).sort_values("country")


def validation_table(panel: pd.DataFrame) -> pd.DataFrame:
    checks: list[dict] = []
    for country, year, field, expected, tolerance in BENCHMARKS:
        actual = panel.loc[(panel["country"] == country) & (panel["year"] == year), field]
        if len(actual) != 1:
            actual_value = np.nan
            passed = False
        else:
            actual_value = float(actual.iloc[0])
            passed = abs(actual_value - expected) <= tolerance
        checks.append(
            {
                "check_group": "external_manual_benchmark",
                "check_id": f"{country}_{year}_{field}",
                "observed": actual_value,
                "expected": expected,
                "tolerance": tolerance,
                "absolute_difference": abs(actual_value - expected) if pd.notna(actual_value) else np.nan,
                "status": "PASS" if passed else "FAIL",
                "interpretation": "既有人工核对参考值，仅用于检查数据口径；不是独立外部验证。",
            }
        )

    n4_diff = (panel["n4_dual_dependency"] - panel["n2_china_hs8542_import_share"] * panel["n3_us_hs8542_export_share"]).abs().max()
    checks.append(
        {
            "check_group": "internal_formula",
            "check_id": "all_rows_N4_equals_N2_times_N3",
            "observed": n4_diff,
            "expected": 0.0,
            "tolerance": 1e-12,
            "absolute_difference": n4_diff,
            "status": "PASS" if n4_diff <= 1e-12 else "FAIL",
            "interpretation": "Checks mathematical consistency for every country-year.",
        }
    )
    checks.extend(
        [
            {
                "check_group": "range_and_coverage",
                "check_id": "unique_country_year_keys",
                "observed": int(panel.duplicated(["country", "year"]).sum()),
                "expected": 0,
                "tolerance": 0,
                "absolute_difference": int(panel.duplicated(["country", "year"]).sum()),
                "status": "PASS" if not panel.duplicated(["country", "year"]).any() else "FAIL",
                "interpretation": "Panel keys must be unique.",
            },
            {
                "check_group": "range_and_coverage",
                "check_id": "complete_12_by_2_panel",
                "observed": len(panel),
                "expected": 24,
                "tolerance": 0,
                "absolute_difference": abs(len(panel) - 24),
                "status": "PASS" if len(panel) == 24 else "FAIL",
                "interpretation": "Expected 12 economies in 2017 and 2022.",
            },
            {
                "check_group": "range_and_coverage",
                "check_id": "share_and_hhi_ranges",
                "observed": int(
                    panel[["p1_unga_relative_alignment", "n2_china_hs8542_import_share", "n3_us_hs8542_export_share", "n4_dual_dependency", "v1_hs8542_import_hhi"]]
                    .apply(lambda s: s.between(0, 1) | s.isna()).all().all()
                ),
                "expected": 1,
                "tolerance": 0,
                "absolute_difference": 0,
                "status": "PASS" if panel[["p1_unga_relative_alignment", "n2_china_hs8542_import_share", "n3_us_hs8542_export_share", "n4_dual_dependency", "v1_hs8542_import_hhi"]].apply(lambda s: s.between(0, 1) | s.isna()).all().all() else "FAIL",
                "interpretation": "All shares, relative positions, and HHI values must lie in [0,1].",
            },
            {
                "check_group": "source_coverage",
                "check_id": "target_year_P2_sources_and_values_complete",
                "observed": int(panel["p2_us_formal_alliance"].notna().sum()),
                "expected": len(panel),
                "tolerance": 0,
                "absolute_difference": abs(int(panel["p2_us_formal_alliance"].notna().sum()) - len(panel)),
                "status": "PASS" if panel["p2_us_formal_alliance"].notna().all()
                and panel.loc[panel["year"] == 2017, "p2_source_year"].eq(2017).all()
                and panel.loc[panel["year"] == 2022, "p2_source_year"].eq(2022).all() else "FAIL",
                "interpretation": "2017 P2 is ATOP-based (Mexico audited against OAS treaty status); 2022 P2 screens State TIF 2020 and its 2021-2023 supplement with target-year bilateral documents and NATO accession dates. Source break is explicit.",
            },
            {
                "check_group": "source_conflict_resolution",
                "check_id": "Mexico_2017_ATOP_raw_vs_OAS_audited_P2",
                "observed": int(panel.loc[(panel["iso3"] == "MEX") & (panel["year"] == 2017), "p2_us_formal_alliance"].iloc[0]),
                "expected": 0,
                "tolerance": 0,
                "absolute_difference": abs(int(panel.loc[(panel["iso3"] == "MEX") & (panel["year"] == 2017), "p2_us_formal_alliance"].iloc[0]) - 0),
                "status": "PASS" if int(panel.loc[(panel["iso3"] == "MEX") & (panel["year"] == 2017), "p2_atop_observed"].iloc[0]) == 1
                and int(panel.loc[(panel["iso3"] == "MEX") & (panel["year"] == 2017), "p2_us_formal_alliance"].iloc[0]) == 0
                and bool(panel.loc[(panel["iso3"] == "MEX") & (panel["year"] == 2017), "p2_oas_adjustment"].iloc[0]) else "FAIL",
                "interpretation": "Preserves raw ATOP=1 while using the OAS-recorded 2004 treaty cessation for audited active-tie P2=0.",
            },
        ]
    )
    return pd.DataFrame(checks)


def main() -> int:
    ensure_directories()
    panel = pd.read_csv(MASTER)
    required = {"country", "iso3", "year", *METRICS}
    missing = sorted(required - set(panel.columns))
    if missing:
        raise ValueError(f"Master panel missing required fields: {missing}")

    descriptive = descriptive_table(panel)
    changes = change_table(panel)
    validation = validation_table(panel)
    descriptive.to_csv(DESCRIPTIVE, index=False, encoding="utf-8-sig")
    changes.to_csv(CHANGE, index=False, encoding="utf-8-sig")
    validation.to_csv(VALIDATION, index=False, encoding="utf-8-sig")

    correlations = []
    for field, label in METRICS.items():
        paired = changes[[f"{field}_2017", f"{field}_2022"]].dropna()
        rho = paired.corr(method="spearman").iloc[0, 1] if len(paired) >= 3 else np.nan
        correlations.append((label, len(paired), rho))
    largest_n4 = changes.nlargest(5, "n4_dual_dependency_2022")[["country", "n4_dual_dependency_2017", "n4_dual_dependency_2022", "n4_dual_dependency_change_2022_minus_2017"]]

    validation_display = validation[["check_group", "check_id", "observed", "expected", "tolerance", "status"]].copy()
    group_labels = {
        "external_manual_benchmark": "人工核对参考值",
        "internal_formula": "公式一致性",
        "range_and_coverage": "取值与覆盖范围",
        "source_coverage": "来源覆盖",
        "source_conflict_resolution": "来源冲突处理",
    }
    check_labels = {
        "all_rows_N4_equals_N2_times_N3": "全部样本：N4 = N2 × N3",
        "unique_country_year_keys": "国家—年份主键唯一",
        "complete_12_by_2_panel": "12国 × 2年面板完整",
        "share_and_hhi_ranges": "比例与HHI位于[0,1]",
        "target_year_P2_sources_and_values_complete": "P2目标年份来源与数值齐全",
        "Mexico_2017_ATOP_raw_vs_OAS_audited_P2": "墨西哥2017：ATOP原值与OAS核验值并列",
    }
    validation_display["check_group"] = validation_display["check_group"].map(lambda v: group_labels.get(v, v))
    validation_display["check_id"] = validation_display["check_id"].map(lambda v: check_labels.get(v, v))
    lines = [
        "# 芯链哨兵数据与测量检查报告",
        "",
        "## 检查说明",
        "",
        "本报告检查人工核对基准、指标公式、取值范围、样本键，以及两个年份的来源覆盖。P2按目标年份使用对应证据，但2017与2022的来源类型不同，因此只能作有边界的结构对照。报告不把内部检查解释为预测准确率。",
        "",
        "## 自动检查",
        "",
        f"共完成{len(validation)}项检查，{int((validation['status'] == 'PASS').sum())}项通过，{int((validation['status'] == 'FAIL').sum())}项未通过。" if (validation["status"] == "PASS").all() else f"共{int((validation['status'] == 'FAIL').sum())}项检查未通过，需要复核。",
        "",
        to_markdown_table(validation_display),
        "",
        "## 2017—2022排序对照",
        "",
        "Spearman相关比较同一指标在2017与2022年的国家排序，只用于描述结构变化；不代表信度系数，也不验证最终指数的预测能力。P2存在来源口径变化，相关性尤其应谨慎解释。",
        "",
        to_markdown_table(pd.DataFrame(correlations, columns=["indicator", "paired_countries", "spearman_2017_2022"])),
        "",
        "## 2022年双重依赖较高的经济体",
        "",
        to_markdown_table(largest_n4),
        "",
        "## 数据边界",
        "",
        "- P2的2017值以ATOP为基础，墨西哥保留原始值并按OAS条约状态作单项修正；2022逐国核对美国国务院《Treaties in Force 2020》及2021—2023补编、目标年双边资料和NATO成员加入年份。不同来源带来的时间可比性限制已单列。",
        "- BIS P3只整合所选且已人工复核的候选规则，范围并非穷尽；只作证据层，不纳入指数分数。",
        "- IMF CDIS显示的是按直接对手方拆分的年末投资头寸；2022目标行使用2021观测（滞后一年），且不是半导体专项数据，不计分。",
        "- 历史对照是描述性分析，不构成因果识别或未来预测。",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    public = PROJECT_ROOT / "outputs"
    public.mkdir(exist_ok=True)
    for path in (DESCRIPTIVE, CHANGE, VALIDATION, REPORT):
        shutil.copy2(path, public / path.name)
    append_progress(
        "Competition measurement validation and historical backtest",
        "complete",
        [
            f"Generated descriptive statistics for {len(METRICS)} indicators in 2017 and 2022.",
            f"Generated country-level changes for {len(changes)} economies.",
            f"Automated validation checks passed: {int((validation['status'] == 'PASS').sum())}/{len(validation)}.",
            "Validation includes external manual benchmarks, formula/range checks, and a 2017-to-2022 historical comparison.",
            "Pilot GTRI-v0 was recalculated separately; this script does not determine index weights.",
        ],
    )
    print(validation.to_string(index=False))
    return 0 if (validation["status"] == "PASS").all() else 1


if __name__ == "__main__":
    raise SystemExit(main())
