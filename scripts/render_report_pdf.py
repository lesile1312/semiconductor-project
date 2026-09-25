"""Render the Markdown research report and its reviewed SVG figures to A4 PDF."""

from __future__ import annotations

import base64
import html
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "docs"
SOURCE = REPORT_DIR / "研究报告_芯链哨兵.md"
OUTPUT = REPORT_DIR / "研究报告_芯链哨兵.pdf"
FIGURES = {"gtri_n4_change_slope_2017_2022.svg", "gtri_sandwich_nodes_2022.svg"}
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


def inline_markup(text: str) -> str:
    result = html.escape(text)
    result = re.sub(r"`([^`]+)`", r"<code>\1</code>", result)
    result = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", result)
    return result


def markdown_to_html(source: str) -> str:
    out: list[str] = []
    title_seen = False
    cover_open = False
    figure_number = 0
    for raw in source.splitlines():
        line = raw.strip()
        if not line:
            continue
        image = re.fullmatch(r"!\[([^]]*)\]\(([^)]+)\)", line)
        if image:
            alt, file_name = image.groups()
            if file_name not in FIGURES:
                raise ValueError(f"Unreviewed figure path: {file_name}")
            image_path = (REPORT_DIR / file_name).resolve()
            if not image_path.is_file():
                raise FileNotFoundError(image_path)
            payload = base64.b64encode(image_path.read_bytes()).decode("ascii")
            figure_number += 1
            # The report already has a visible numbered heading above each figure;
            # avoid repeating the same title below the embedded SVG.
            out.append(f'<figure><img src="data:image/svg+xml;base64,{payload}" alt="{html.escape(alt)}"></figure>')
            continue
        if line.startswith("# "):
            if title_seen:
                out.append(f"<h1>{inline_markup(line[2:])}</h1>")
            else:
                title_seen = True
                cover_open = True
                out.append(f'<section class="cover"><p class="kicker">赛道A｜风险感知与地平线扫描</p><h1>{inline_markup(line[2:])}</h1>')
            continue
        if line.startswith("## "):
            if cover_open:
                out.append(f'<p class="subtitle">{inline_markup(line[3:])}</p>')
                out.append('<p class="cover-meta">2022基准 / 2017结构对照　｜　12个经济体</p>')
                out.append('<p class="cover-meta">阅读提示：GTRI-v0用于尽调筛查，不是法律意见、投资建议或未来风险概率。P3所选10条候选规则已做范围核对，但集合非穷尽、不计分。</p></section>')
                cover_open = False
            else:
                out.append(f"<h2>{inline_markup(line[3:])}</h2>")
            continue
        if line.startswith("### "):
            out.append(f"<h3>{inline_markup(line[4:])}</h3>")
            continue
        if line.startswith("**") and line.endswith("**") and line.count("**") == 2:
            out.append(f'<h3 class="figure-title">{inline_markup(line[2:-2])}</h3>')
            continue
        if line.startswith("- "):
            out.append(f'<p class="bullet">{inline_markup(line[2:])}</p>')
            continue
        out.append(f"<p>{inline_markup(line)}</p>")
    if cover_open:
        out.append("</section>")
    return """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>芯链哨兵｜研究报告</title>
<style>
@page{size:A4;margin:13mm 17mm 15mm}
*{box-sizing:border-box}html{background:#edf2f5}body{margin:0 auto;max-width:176mm;color:#192a38;background:#fff;font-family:"Microsoft YaHei","Noto Sans CJK SC",Arial,sans-serif;font-size:10.2pt;line-height:1.62}
.cover{margin:0 0 16pt;padding:15pt 17pt 13pt;border-left:5px solid #19877f;background:linear-gradient(120deg,#edf8f7,#fff);break-inside:avoid}.cover h1{margin:0 0 10pt;color:#102b42;font-size:23pt;line-height:1.22;letter-spacing:.02em}.kicker{margin:0 0 8pt;color:#19877f;font-size:9pt;font-weight:700;letter-spacing:.08em}.subtitle{margin:0 0 7pt;text-align:left;font-size:13pt;color:#405d70}.cover-meta{margin:6pt 0 0;text-align:left;color:#586f7f;font-size:9pt}
h2{margin:14pt 0 6pt;padding-bottom:4pt;border-bottom:1px solid #d9e4ea;color:#14516a;font-size:14pt;break-after:avoid}h3{margin:9pt 0 4pt;color:#236b79;font-size:11.3pt;break-after:avoid}.figure-title{margin:9pt 0 4pt;color:#236b79;font-size:11.3pt}p{margin:0 0 5pt;text-align:justify;orphans:3;widows:3}p.bullet{padding-left:14pt;text-indent:-10pt}p.bullet:before{content:"• ";color:#19877f}strong{color:#123f58}code{font-family:Consolas,monospace;font-size:.92em;color:#216a65;background:#eff6f5;padding:0 2pt}
figure{margin:7pt 0 10pt;text-align:center;break-inside:avoid}figure img{display:block;width:100%;height:auto;max-height:151mm;object-fit:contain;margin:0 auto 3pt}figcaption{color:#627686;font-size:8.8pt}
@page{@bottom-center{content:"芯链哨兵｜研究报告 · " counter(page);font-family:"Microsoft YaHei",Arial,sans-serif;font-size:8pt;color:#83929e}}
@media print{html{background:#fff}body{max-width:none}}
</style></head><body>
""" + "\n".join(out) + "\n</body></html>"


def main() -> int:
    if not EDGE.is_file():
        raise FileNotFoundError(f"Microsoft Edge not found: {EDGE}")
    html_doc = markdown_to_html(SOURCE.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="gtri-report-", dir=REPORT_DIR) as temp_name:
        temp = Path(temp_name)
        html_path = temp / "report.html"
        candidate_pdf = temp / OUTPUT.name
        html_path.write_text(html_doc, encoding="utf-8")
        command = [str(EDGE), "--headless=new", "--disable-gpu", "--no-first-run", "--no-pdf-header-footer", "--virtual-time-budget=2500", f"--print-to-pdf={candidate_pdf}", html_path.resolve().as_uri()]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
        if result.returncode != 0 or not candidate_pdf.is_file() or candidate_pdf.stat().st_size < 20_000:
            raise RuntimeError(f"Edge PDF rendering failed ({result.returncode}): {result.stderr[-2000:]}")
        info = subprocess.run(["pdfinfo", str(candidate_pdf)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20)
        if info.returncode != 0 or "Pages:" not in info.stdout:
            raise RuntimeError(f"pdfinfo validation failed: {info.stderr[-1000:]}")
        shutil.copy2(candidate_pdf, OUTPUT)
        page_line = next(line.strip() for line in info.stdout.splitlines() if line.startswith("Pages:"))
        print(f"pdf_render=PASS bytes={OUTPUT.stat().st_size} {page_line} output={OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
