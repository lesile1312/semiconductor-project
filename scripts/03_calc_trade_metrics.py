"""Calculate N2, N3, N4, V1 and V2 from cleaned HS8542 trade."""

from __future__ import annotations

import math

import pandas as pd

from gtri_config import COUNTRIES, OUTPUT_DIR, PROCESSED_DIR, YEARS, append_progress, ensure_directories


CHINA_CODE = 156
US_CODE = 842

BENCHMARKS = {
    "Malaysia": {"N2": 0.1709, "N3": 0.0788, "N4": 0.0135, "V1": 0.148, "V2": 13},
    "Vietnam": {"N2": 0.1805, "N3": 0.0465, "N4": 0.0084, "V1": 0.207, "V2": 9},
}
TOLERANCE = {"N2": 0.002, "N3": 0.002, "N4": 0.001, "V1": 0.003, "V2": 0}


def value_for_partner(frame: pd.DataFrame, partner_code: int) -> float:
    values = frame.loc[frame["partner_code"] == partner_code, "trade_value"]
    return float(values.sum()) if len(values) else 0.0


def main() -> int:
    ensure_directories()
    clean_path = PROCESSED_DIR / "comtrade_hs8542_clean.csv"
    world_path = PROCESSED_DIR / "comtrade_hs8542_world_totals.csv"
    if not clean_path.exists() or not world_path.exists():
        raise FileNotFoundError("Run scripts/02_clean_comtrade.py first")
    clean = pd.read_csv(clean_path)
    world = pd.read_csv(world_path)
    rows: list[dict] = []
    issues: list[str] = []

    for country in COUNTRIES:
        for year in YEARS:
            base = clean[(clean["reporter_code"] == country["comtrade"]) & (clean["year"] == year)]
            imports = base[base["flow"] == "M"]
            exports = base[base["flow"] == "X"]
            wi = world[(world["reporter_code"] == country["comtrade"]) & (world["year"] == year) & (world["flow"] == "M")]
            wx = world[(world["reporter_code"] == country["comtrade"]) & (world["year"] == year) & (world["flow"] == "X")]
            if len(wi) != 1 or len(wx) != 1:
                issues.append(f"{country['country']} {year}: missing/non-unique World denominator")
                continue
            total_imports = float(wi.iloc[0]["trade_value"])
            total_exports = float(wx.iloc[0]["trade_value"])
            if total_imports <= 0 or total_exports <= 0:
                issues.append(f"{country['country']} {year}: non-positive World denominator")
                continue

            n2 = value_for_partner(imports, CHINA_CODE) / total_imports
            n3 = value_for_partner(exports, US_CODE) / total_exports
            shares = imports.loc[imports["trade_value"] > 0, "trade_value"] / total_imports
            row = {
                "country": country["country"],
                "iso3": country["iso3"],
                "year": year,
                "N2": n2,
                "N3": n3,
                "N4": n2 * n3,
                "V1": float((shares ** 2).sum()),
                "V2": int((shares >= 0.01).sum()),
                "world_import_value": total_imports,
                "world_export_value": total_exports,
                "china_import_value": value_for_partner(imports, CHINA_CODE),
                "us_export_value": value_for_partner(exports, US_CODE),
                "import_partner_share_sum": float(shares.sum()),
                "source_flag": "UN_Comtrade_official_reporter_HS8542",
            }
            if not math.isclose(row["import_partner_share_sum"], 1.0, rel_tol=1e-9, abs_tol=1e-6):
                issues.append(f"{country['country']} {year}: import partner shares do not sum to one")
            rows.append(row)

    result = pd.DataFrame(rows)
    qc_lines: list[str] = []
    qc_failures: list[str] = []
    for name, expected in BENCHMARKS.items():
        observed_row = result[(result["country"] == name) & (result["year"] == 2022)]
        if len(observed_row) != 1:
            qc_failures.append(f"{name}: 2022 row missing")
            continue
        observed = observed_row.iloc[0]
        comparisons = []
        for metric, target in expected.items():
            actual = float(observed[metric])
            difference = abs(actual - target)
            passed = difference <= TOLERANCE[metric]
            comparisons.append(f"{metric}={actual:.6f} vs {target} ({'PASS' if passed else 'FAIL'})")
            if not passed:
                qc_failures.append(f"{name} {metric}: {actual} vs {target}")
        qc_lines.append(f"{name}: " + "; ".join(comparisons))

    for year in YEARS:
        result[result["year"] == year].to_csv(
            OUTPUT_DIR / f"trade_metrics_{year}.csv", index=False, encoding="utf-8-sig"
        )
    result.to_csv(PROCESSED_DIR / "trade_metrics_all_years.csv", index=False, encoding="utf-8-sig")
    (PROCESSED_DIR / "trade_metrics_quality_check.txt").write_text(
        "\n".join(qc_lines + (["FAILURES:"] + qc_failures if qc_failures else ["All benchmark checks passed."])) + "\n",
        encoding="utf-8",
    )

    all_issues = issues + qc_failures
    append_progress(
        "HS8542 trade metrics",
        "complete" if not all_issues else "FAILED",
        [
            "Definitions: N2=China imports/World imports; N3=US exports/World exports; N4=N2*N3; V1=sum of squared import-partner shares; V2=count of import partner areas with share >=1%.",
            *qc_lines,
            *(all_issues or ["All 24 country-year rows calculated; benchmark and reconciliation checks passed."]),
        ],
    )
    if all_issues:
        raise RuntimeError("Trade metric quality check failed: " + "; ".join(all_issues))
    print(result[["country", "year", "N2", "N3", "N4", "V1", "V2"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
