"""Create self-contained, offline-ready copies of the three website pages."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGES = {
    "index.html": "portable/index.html",
    "risk-migration-lens.html": "portable/risk-migration-lens.html",
    "enterprise-scan.html": "portable/enterprise-scan.html",
}
SCRIPT_TAG = re.compile(
    r"<script\b(?P<attrs>[^>]*?)\bsrc=(?P<q>['\"])(?P<src>[^'\"]+)(?P=q)(?P<tail>[^>]*)>\s*</script>",
    re.IGNORECASE,
)


def inline_local_scripts(html: str, page: str) -> str:
    def replace(match: re.Match) -> str:
        src = match.group("src")
        if not src.startswith("assets/"):
            return match.group(0)
        asset_path = src.split("?", 1)[0]
        asset = (ROOT / asset_path).resolve()
        if ROOT.resolve() not in asset.parents or not asset.is_file():
            raise FileNotFoundError(f"{page}: local script not found: {asset_path}")
        attrs = (match.group("attrs") + match.group("tail")).strip()
        attrs = re.sub(r"\bsrc=(['\"]).*?\1", "", attrs, flags=re.IGNORECASE).strip()
        suffix = f" {attrs}" if attrs else ""
        return f"<script{suffix}>\n{asset.read_text(encoding='utf-8')}\n</script>"

    return SCRIPT_TAG.sub(replace, html)


def main() -> int:
    generated: list[Path] = []
    for source_name, target_name in PAGES.items():
        source = ROOT / source_name
        target = ROOT / target_name
        target.parent.mkdir(parents=True, exist_ok=True)
        rendered = inline_local_scripts(source.read_text(encoding="utf-8"), source_name)
        unresolved = re.findall(r"<script\b[^>]*\bsrc=['\"]assets/", rendered, flags=re.IGNORECASE)
        if unresolved:
            raise SystemExit(f"Portable output still references relative JavaScript: {target_name}")
        target.write_text(rendered, encoding="utf-8")
        generated.append(target)
    for path in generated:
        print(f"Built {path.relative_to(ROOT)} ({path.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
