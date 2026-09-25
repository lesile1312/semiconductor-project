"""Create an auditable, legible 2017-2022 N4 dumbbell comparison."""
from __future__ import annotations

import html
import shutil

import pandas as pd

from gtri_config import OUTPUT_DIR, PROJECT_ROOT, append_progress, ensure_directories


COUNTRY_ORDER = [
    "Malaysia", "Vietnam", "Singapore", "Thailand", "India", "Indonesia",
    "Philippines", "Japan", "South Korea", "Mexico", "Germany", "Netherlands",
]


def main() -> int:
    ensure_directories()
    panel = pd.read_csv(OUTPUT_DIR / "master_country_year.csv")
    values = panel.pivot(index="country", columns="year", values="n4_dual_dependency")
    if set(values.columns) < {2017, 2022} or values[[2017, 2022]].isna().any().any():
        raise ValueError("N4 comparison requires observed 2017 and 2022 values for every economy")
    values = values.reindex([country for country in COUNTRY_ORDER if country in values.index])
    values = values.sort_values(2022, ascending=False)

    width, height = 1440, 900
    left, right, top, bottom = 220, 970, 178, 758
    max_value = max(float(values[[2017, 2022]].max().max()) * 1.08, 0.25)
    x = lambda value: left + value / max_value * (right - left)
    row_y = lambda i: top + i * (bottom - top) / (len(values) - 1)
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">2017至2022年中美双重依赖指标比较</title>',
        '<desc id="desc">十二个经济体的N4双点图。横轴为N4，点分别表示2017和2022，右侧列出两年数值和百分点变化。N4等于中国进口份额乘以美国出口份额。</desc>',
        '<style>text{font-family:"Microsoft YaHei",Arial,sans-serif;fill:#202b36}.title{font-size:31px;font-weight:700}.subtitle{font-size:17px;fill:#5c6975}.country{font-size:18px;font-weight:600}.small{font-size:15px;fill:#566370}.value{font-size:16px;font-variant-numeric:tabular-nums}.axis{stroke:#63717d;stroke-width:1.4}.grid{stroke:#e4e9ed;stroke-width:1}.increase{stroke:#b66b38}.decrease{stroke:#397c87}.header{font-size:14px;fill:#5b6874;font-weight:700;letter-spacing:.4px}.legend{font-size:15px;fill:#495663}</style>',
        '<rect width="100%" height="100%" fill="#fff"/>',
        '<text class="title" x="70" y="66">第三方节点的双重依赖，如何变化？</text>',
        '<text class="subtitle" x="70" y="101">2017 与 2022 年 N4 对照｜N4 = 中国 HS8542 进口份额 × 美国 HS8542 出口份额</text>',
        '<text class="small" x="70" y="132">圆点位置使用同一横轴（0—{:.0%}）；右侧变化列以百分点计。仅作样本内描述，不代表因果或预测。</text>'.format(max_value),
    ]
    for tick in [i / 20 for i in range(0, int(max_value * 20) + 1)]:
        tx = x(tick)
        out.extend([
            f'<line class="grid" x1="{tx:.1f}" y1="{top-18}" x2="{tx:.1f}" y2="{bottom+20}"/>',
            f'<text class="small" x="{tx:.1f}" y="{bottom+47}" text-anchor="middle">{tick:.0%}</text>',
        ])
    out.extend([
        f'<line class="axis" x1="{left}" y1="{bottom+20}" x2="{right}" y2="{bottom+20}"/>',
        '<text class="header" x="1070" y="151" text-anchor="middle">2017</text>',
        '<text class="header" x="1190" y="151" text-anchor="middle">2022</text>',
        '<text class="header" x="1320" y="151" text-anchor="middle">变化（百分点）</text>',
    ])
    for index, (country, row) in enumerate(values.iterrows()):
        y = row_y(index)
        old, new = float(row[2017]), float(row[2022])
        delta_pp = (new - old) * 100
        cls = "increase" if delta_pp > 0.05 else "decrease" if delta_pp < -0.05 else "small"
        color = "#b66b38" if cls == "increase" else "#397c87" if cls == "decrease" else "#87929b"
        out.append(f'<line x1="{left}" y1="{y+23:.1f}" x2="1380" y2="{y+23:.1f}" stroke="#f0f2f4"/>')
        out.append(f'<text class="country" x="{left-22}" y="{y+6:.1f}" text-anchor="end">{html.escape(country)}</text>')
        out.append(f'<line x1="{x(old):.1f}" y1="{y:.1f}" x2="{x(new):.1f}" y2="{y:.1f}" stroke="{color}" stroke-width="4" stroke-linecap="round" opacity=".72"/>')
        out.append(f'<circle cx="{x(old):.1f}" cy="{y:.1f}" r="7" fill="#fff" stroke="#566574" stroke-width="3"><title>{html.escape(country)} 2017 N4={old:.5f}</title></circle>')
        out.append(f'<circle cx="{x(new):.1f}" cy="{y:.1f}" r="7" fill="{color}" stroke="#fff" stroke-width="2"><title>{html.escape(country)} 2022 N4={new:.5f}</title></circle>')
        out.append(f'<text class="value" x="1070" y="{y+6:.1f}" text-anchor="middle">{old:.3f}</text>')
        out.append(f'<text class="value" x="1190" y="{y+6:.1f}" text-anchor="middle">{new:.3f}</text>')
        out.append(f'<text class="value" x="1320" y="{y+6:.1f}" text-anchor="middle" fill="{color}">{delta_pp:+.2f}</text>')
    out.extend([
        '<circle cx="290" cy="833" r="7" fill="#fff" stroke="#566574" stroke-width="3"/>',
        '<text class="legend" x="307" y="838">2017</text>',
        '<circle cx="395" cy="833" r="7" fill="#397c87"/>',
        '<text class="legend" x="412" y="838">2022</text>',
        '<line x1="510" y1="833" x2="552" y2="833" stroke="#b66b38" stroke-width="4"/>',
        '<text class="legend" x="563" y="838">N4 上升</text>',
        '<line x1="672" y1="833" x2="714" y2="833" stroke="#397c87" stroke-width="4"/>',
        '<text class="legend" x="725" y="838">N4 下降</text>',
        '<text class="small" x="70" y="878">数据：UN Comtrade 自报 HS8542；每国两年口径按主面板。线段仅连接年度观测值，不表示中间年份路径。</text>',
        '</svg>',
    ])
    path = OUTPUT_DIR / "gtri_n4_change_slope_2017_2022.svg"
    path.write_text("\n".join(out), encoding="utf-8")
    public = PROJECT_ROOT / "outputs"
    public.mkdir(exist_ok=True)
    shutil.copy2(path, public / path.name)
    append_progress("2017-2022 N4 comparison figure", "complete", [
        f"Wrote same-scale dumbbell SVG to {path.as_posix()}.",
        "2017/2022 values are independently observed; change is reported in percentage points.",
        "Chart is descriptive and does not encode P3 or final GTRI weights.",
    ])
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
