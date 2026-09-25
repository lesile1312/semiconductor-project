"""Create a legible, reproducible 2022 multi-source sandwich-node figure."""

from __future__ import annotations

import html
import math
import shutil

import pandas as pd

from gtri_config import OUTPUT_DIR, PROJECT_ROOT, append_progress, ensure_directories


FIGURE_YEAR = 2022
WIDTH, HEIGHT = 1480, 980
PLOT_LEFT, PLOT_RIGHT = 110, 835
PLOT_TOP, PLOT_BOTTOM = 165, 770


def _scale(value: float, domain: tuple[float, float], range_: tuple[float, float]) -> float:
    lo, hi = domain
    out_lo, out_hi = range_
    if hi == lo:
        return (out_lo + out_hi) / 2
    return out_lo + (value - lo) * (out_hi - out_lo) / (hi - lo)


def _fmt_pct(value: float) -> str:
    percent = value * 100
    return f"{percent:.0f}%" if percent.is_integer() else f"{percent:.1f}%"


def _p1_color(p1: float) -> str:
    """Blue means closer to China and red closer to the US in UNGA ideal-point space."""
    p1 = max(0.0, min(1.0, p1))
    stops = [(0.0, (45, 92, 180)), (0.5, (238, 238, 238)), (1.0, (190, 54, 54))]
    for (lo, c0), (hi, c1) in zip(stops, stops[1:]):
        if lo <= p1 <= hi:
            t = (p1 - lo) / (hi - lo)
            rgb = tuple(round(a + (b - a) * t) for a, b in zip(c0, c1))
            return f"rgb({rgb[0]},{rgb[1]},{rgb[2]})"
    return "rgb(190,54,54)"


def build_svg(df: pd.DataFrame) -> str:
    required = [
        "country", "iso3", "year", "p1_unga_relative_alignment",
        "p2_us_formal_alliance", "n1_electronics_foreign_va_share",
        "n2_china_hs8542_import_share", "n3_us_hs8542_export_share",
        "n4_dual_dependency", "v1_hs8542_import_hhi", "v2_effective_supplier_count",
    ]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(missing))
    points = df.loc[df["year"].eq(FIGURE_YEAR), required].copy()
    if len(points) != 12 or points[required].isna().any().any():
        raise ValueError("Expected 12 complete country observations for 2022")

    x_max = max(0.42, float(points["n2_china_hs8542_import_share"].max()) * 1.12)
    y_max = max(0.85, float(points["n3_us_hs8542_export_share"].max()) * 1.08)
    x_domain = (0.0, x_max)
    hhi_domain = (float(points["v1_hs8542_import_hhi"].min()), float(points["v1_hs8542_import_hhi"].max()))
    points["x"] = points["n2_china_hs8542_import_share"].map(lambda v: _scale(v, x_domain, (PLOT_LEFT, PLOT_RIGHT)))
    # A disclosed square-root display scale makes the dense low-N3 range legible without changing values.
    points["y"] = points["n3_us_hs8542_export_share"].map(
        lambda v: _scale(math.sqrt(max(float(v), 0)), (0.0, math.sqrt(y_max)), (PLOT_BOTTOM, PLOT_TOP))
    )
    points["r"] = points["v1_hs8542_import_hhi"].map(lambda v: _scale(v, hhi_domain, (16, 29)))
    points = points.sort_values("n4_dual_dependency", ascending=False).reset_index(drop=True)
    points["id"] = [f"{i:02d}" for i in range(1, len(points) + 1)]

    x_ticks = [i / 10 for i in range(0, int(x_max * 10) + 1)]
    y_ticks = [0, .01, .025, .05, .10, .20, .40, .80]
    y_ticks = [tick for tick in y_ticks if tick <= y_max]
    x_mid = float(points["n2_china_hs8542_import_share"].median())
    y_mid = float(points["n3_us_hs8542_export_share"].median())

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">',
        '<title id="title">2022年第三方经济体的中美半导体夹层暴露</title>',
        '<desc id="desc">十二国气泡图：横轴为对华HS8542进口份额，纵轴为对美HS8542出口份额并采用明确标示的平方根显示尺度；气泡面积随进口来源HHI增加，颜色显示UNGA相对位置，实线或虚线边框表示所选官方来源识别的目标年正式集体防御安排。</desc>',
        '<style>text{font-family:"Microsoft YaHei",Arial,sans-serif;fill:#202b36}.title{font-size:33px;font-weight:700}.subtitle{font-size:19px;fill:#586673}.axis{stroke:#65727d;stroke-width:1.3}.grid{stroke:#e4e9ed;stroke-width:1}.median{stroke:#87939e;stroke-dasharray:5 5;stroke-width:1.4}.tick{font-size:17px;fill:#566370}.axis-title{font-size:20px;font-weight:700}.node{fill-opacity:.86;stroke-width:2.5}.ally{stroke:#19252d}.nonally{stroke:#59656f;stroke-dasharray:5 4}.node-id{font-size:11px;font-weight:700;text-anchor:middle;dominant-baseline:central;fill:#18222c;paint-order:stroke;stroke:#fff;stroke-width:2px;stroke-linejoin:round}.panel{fill:#f6f8f9;stroke:#e0e5e8}.row{font-size:20px}.muted{font-size:17px;fill:#5b6874}.small{font-size:15px;fill:#5b6874}.rank{font-size:12px;font-weight:700;fill:#fff}.header{font-size:17px;font-weight:700;fill:#5b6874;letter-spacing:.3px}</style>',
        '<defs><linearGradient id="p1grad" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" stop-color="rgb(45,92,180)"/><stop offset="50%" stop-color="rgb(238,238,238)"/><stop offset="100%" stop-color="rgb(190,54,54)"/></linearGradient></defs>',
        '<rect width="100%" height="100%" fill="#fff"/>',
        '<text class="title" x="62" y="55">第三方节点：对华投入与对美市场的双向暴露</text>',
        '<text class="subtitle" x="62" y="88">2022 年｜12 个经济体｜编号与右侧明细一一对应；N4 由 N2 × N3 计算</text>',
        '<text class="header" x="895" y="143">节点明细（按 N4 从高到低）</text>',
    ]

    for tick in x_ticks:
        tx = _scale(tick, x_domain, (PLOT_LEFT, PLOT_RIGHT))
        out.extend([
            f'<line class="grid" x1="{tx:.1f}" y1="{PLOT_TOP}" x2="{tx:.1f}" y2="{PLOT_BOTTOM}"/>',
            f'<text class="tick" x="{tx:.1f}" y="{PLOT_BOTTOM + 25}" text-anchor="middle">{_fmt_pct(tick)}</text>',
        ])
    for tick in y_ticks:
        ty = _scale(math.sqrt(tick), (0.0, math.sqrt(y_max)), (PLOT_BOTTOM, PLOT_TOP))
        out.extend([
            f'<line class="grid" x1="{PLOT_LEFT}" y1="{ty:.1f}" x2="{PLOT_RIGHT}" y2="{ty:.1f}"/>',
            f'<text class="tick" x="{PLOT_LEFT - 12}" y="{ty + 5:.1f}" text-anchor="end">{_fmt_pct(tick)}</text>',
        ])
    x_median = _scale(x_mid, x_domain, (PLOT_LEFT, PLOT_RIGHT))
    y_median = _scale(math.sqrt(y_mid), (0.0, math.sqrt(y_max)), (PLOT_BOTTOM, PLOT_TOP))
    out.extend([
        f'<line class="axis" x1="{PLOT_LEFT}" y1="{PLOT_BOTTOM}" x2="{PLOT_RIGHT}" y2="{PLOT_BOTTOM}"/>',
        f'<line class="axis" x1="{PLOT_LEFT}" y1="{PLOT_TOP}" x2="{PLOT_LEFT}" y2="{PLOT_BOTTOM}"/>',
        f'<line class="median" x1="{x_median:.1f}" y1="{PLOT_TOP}" x2="{x_median:.1f}" y2="{PLOT_BOTTOM}"/>',
        f'<line class="median" x1="{PLOT_LEFT}" y1="{y_median:.1f}" x2="{PLOT_RIGHT}" y2="{y_median:.1f}"/>',
        f'<text class="small" x="{x_median + 5:.1f}" y="{PLOT_TOP + 17}">样本中位数</text>',
        f'<text class="axis-title" x="{(PLOT_LEFT + PLOT_RIGHT) / 2:.1f}" y="{PLOT_BOTTOM + 63}" text-anchor="middle">N2｜中国占本国 HS8542 进口的份额</text>',
        f'<text class="small" x="{PLOT_LEFT}" y="{PLOT_TOP - 16}" text-anchor="start">N3｜美国占本国 HS8542 出口的份额（纵轴按平方根映射）</text>',
    ])

    for _, row in points.iterrows():
        country = html.escape(str(row["country"]))
        p2 = int(row["p2_us_formal_alliance"])
        class_name = "ally" if p2 == 1 else "nonally"
        tooltip = (f"{country}: N2={_fmt_pct(row['n2_china_hs8542_import_share'])}, "
                   f"N3={_fmt_pct(row['n3_us_hs8542_export_share'])}, "
                   f"N4={row['n4_dual_dependency']:.5f}, HHI={row['v1_hs8542_import_hhi']:.3f}, "
                   f"P1={row['p1_unga_relative_alignment']:.3f}, P2={p2}")
        out.append(
            f'<circle class="node {class_name}" cx="{row["x"]:.1f}" cy="{row["y"]:.1f}" r="{row["r"]:.1f}" fill="{_p1_color(row["p1_unga_relative_alignment"])}"><title>{html.escape(tooltip)}</title></circle>'
        )
        out.append(f'<text class="node-id" x="{row["x"]:.1f}" y="{row["y"]:.1f}">{row["id"]}</text>')

    for index, row in points.iterrows():
        y = 171 + index * 43
        if index % 2 == 1:
            out.append(f'<rect x="878" y="{y-24}" width="544" height="39" rx="4" fill="#fff"/>')
        n4 = float(row["n4_dual_dependency"])
        out.extend([
            f'<circle cx="902" cy="{y-5}" r="12" fill="#354550"/><text class="rank" x="902" y="{y-1}" text-anchor="middle">{row["id"]}</text>',
            f'<text class="row" x="928" y="{y}">{html.escape(str(row["country"]))}</text>',
            f'<text class="muted" x="1400" y="{y}" text-anchor="end">N4 {n4:.3f}</text>',
            f'<text class="small" x="928" y="{y+16}">N2 {_fmt_pct(row["n2_china_hs8542_import_share"])}　N3 {_fmt_pct(row["n3_us_hs8542_export_share"])}　HHI {row["v1_hs8542_import_hhi"]:.2f}</text>',
        ])

    out.extend([
        '<rect class="panel" x="62" y="858" width="1360" height="83" rx="6"/>',
        '<circle cx="91" cy="887" r="12" fill="#9aaed7" stroke="#19252d" stroke-width="2.5"/><text class="small" x="113" y="892">实线边框：按目标年来源识别的正式集体防御安排</text>',
        '<circle cx="91" cy="919" r="12" fill="#9aaed7" stroke="#59656f" stroke-dasharray="5 4" stroke-width="2.5"/><text class="small" x="113" y="924">虚线边框：本次所选来源未识别到该类安排；不等于不存在其他安全合作</text>',
        '<rect x="660" y="876" width="210" height="13" fill="url(#p1grad)"/><text class="small" x="660" y="908">UNGA P1 相对位置：靠近中国</text><text class="small" x="870" y="908" text-anchor="end">靠近美国</text>',
        '<circle cx="1000" cy="885" r="8" fill="#738799"/><circle cx="1034" cy="885" r="14" fill="#738799"/><text class="small" x="1058" y="890">气泡面积随进口来源 HHI 增加</text>',
        '<text class="small" x="660" y="928">纵轴采用平方根显示尺度（刻度仍标原始 N3）；虚线为样本中位数。</text>',
        '<text class="small" x="62" y="965">来源：UN Comtrade、UNGA ideal points、目标年 P2 编码。P2 两年来源断点、P3 非计分及 CDIS 缺失边界见研究报告/来源说明。</text>',
        '</svg>',
    ])
    return "\n".join(out)


def main() -> int:
    ensure_directories()
    panel_path = OUTPUT_DIR / "master_country_year.csv"
    if not panel_path.exists():
        raise FileNotFoundError(f"Missing master panel: {panel_path}")
    panel = pd.read_csv(panel_path)
    svg = build_svg(panel)
    output_path = OUTPUT_DIR / "gtri_sandwich_nodes_2022.svg"
    output_path.write_text(svg, encoding="utf-8")
    public_outputs = PROJECT_ROOT / "outputs"
    public_outputs.mkdir(exist_ok=True)
    shutil.copy2(output_path, public_outputs / output_path.name)

    top = panel.loc[panel["year"].eq(FIGURE_YEAR)].nlargest(3, "n4_dual_dependency")
    append_progress("2022 multi-source sandwich-node figure", "complete", [
        f"Wrote numbered, tabulated SVG figure to {output_path.as_posix()}.",
        "Encoding: N2 horizontal position, square-root-display N3 vertical position (raw ticks retained), V1 bubble area, P1 color, target-year P2 outline; every economy is listed with N2/N3/HHI/N4.",
        "P2 has a source break: 2017 ATOP observations and 2022 selected official US State/NATO coding; the outline is not a homogeneous time series.",
        "P3 remains non-scoring because the selected BIS manual review set is non-exhaustive.",
        "Largest 2022 N4 values: " + "; ".join(f"{r.country}={r.n4_dual_dependency:.4f}" for r in top.itertuples(index=False)),
    ])
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
