"""Download ATOP 5.1 and construct US formal-defense-alliance indicator P2."""

from __future__ import annotations

import hashlib
import json
import zipfile

import pandas as pd
import requests

from gtri_config import COUNTRIES, PROCESSED_DIR, RAW_DIR, YEARS, append_progress, ensure_directories, utc_now


ATOP_URL = "https://www.atopdata.org/uploads/6/9/1/3/69134503/atop_5.1__.csv_.zip"
DYAD_MEMBER = "ATOP 5.1 (.csv)/atop5_1dy.csv"
US_COW_CODE = 2
SOURCE_END_YEAR = 2018


def get_dyad_row(df: pd.DataFrame, state_code: int, year: int) -> pd.Series | None:
    match = df[
        (df["year"] == year)
        & (((df["mem1"] == US_COW_CODE) & (df["mem2"] == state_code))
           | ((df["mem2"] == US_COW_CODE) & (df["mem1"] == state_code)))
    ]
    if len(match) > 1:
        raise RuntimeError(f"Duplicate US dyad for COW code {state_code}, year {year}")
    return None if match.empty else match.iloc[0]


def obligations(row: pd.Series | None) -> dict[str, int]:
    fields = ("atopally", "defense", "offense", "neutral", "nonagg", "consul", "number")
    # The dyad-year file enumerates active alliance dyads. Absence within coverage means zero.
    return {field: int(row[field]) if row is not None and pd.notna(row[field]) else 0 for field in fields}


def main() -> int:
    ensure_directories()
    raw_dir = RAW_DIR / "atop"
    zip_path = raw_dir / "atop_5.1_csv.zip"
    try:
        if not zip_path.exists():
            response = requests.get(ATOP_URL, headers={"User-Agent": "GTRI-academic-research/0.1"}, timeout=180)
            response.raise_for_status()
            zip_path.write_bytes(response.content)
        with zipfile.ZipFile(zip_path) as archive:
            if DYAD_MEMBER not in archive.namelist():
                raise RuntimeError(f"Expected {DYAD_MEMBER} not found in ATOP archive")
            extracted_path = raw_dir / "atop5_1dy.csv"
            extracted_path.write_bytes(archive.read(DYAD_MEMBER))
        dyads = pd.read_csv(extracted_path, low_memory=False)
        if int(dyads["year"].max()) != SOURCE_END_YEAR:
            raise RuntimeError(f"Unexpected ATOP coverage end: {dyads['year'].max()}")

        rows: list[dict] = []
        for country in COUNTRIES:
            observed_2017 = obligations(get_dyad_row(dyads, country["cow"], 2017))
            structural_2018 = obligations(get_dyad_row(dyads, country["cow"], SOURCE_END_YEAR))
            for year in YEARS:
                is_observed = year <= SOURCE_END_YEAR
                observed = observed_2017 if year == 2017 else None
                rows.append(
                    {
                        "country": country["country"], "iso3": country["iso3"], "year": year,
                        # Primary P2 is a formal mutual/conditional defense obligation, not a
                        # non-aggression-only ATOP tie. All obligation components are retained.
                        "p2_us_formal_alliance": observed["defense"] if is_observed else pd.NA,
                        "p2_us_formal_alliance_structural_2018": structural_2018["defense"],
                        "p2_source_year": year if is_observed else SOURCE_END_YEAR,
                        "atopally": observed["atopally"] if is_observed else pd.NA,
                        "defense": observed["defense"] if is_observed else pd.NA,
                        "offense": observed["offense"] if is_observed else pd.NA,
                        "neutral": observed["neutral"] if is_observed else pd.NA,
                        "nonagg": observed["nonagg"] if is_observed else pd.NA,
                        "consultation": observed["consul"] if is_observed else pd.NA,
                        "alliance_count": observed["number"] if is_observed else pd.NA,
                        "source_flag": "ATOP_v5.1_observed" if is_observed else "ATOP_v5.1_structural_2018_only",
                        "notes": "" if is_observed else "source coverage ends 2018; 2022 dynamic P2 intentionally missing; structural field is 2018 status",
                    }
                )
        result = pd.DataFrame(rows)
        result.to_csv(PROCESSED_DIR / "atop_p2_country_year.csv", index=False, encoding="utf-8-sig")
        meta = {
            "downloaded_at_utc": utc_now(), "source_url": ATOP_URL, "version": "5.1",
            "coverage_end_year": SOURCE_END_YEAR, "dyad_file": DYAD_MEMBER,
            "sha256": hashlib.sha256(zip_path.read_bytes()).hexdigest(),
            "p2_definition": "ATOP dyad-year defense obligation with the United States (COW code 2)",
            "why_not_atopally": "atopally also marks non-aggression-only ties; obligation fields are retained for audit",
        }
        (raw_dir / "source_metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        append_progress(
            "ATOP v5.1 / P2",
            "complete with coverage limitation",
            [
                "Downloaded official ATOP v5.1 CSV archive and retained SHA-256; dyad-year source coverage ends 2018.",
                "P2 is coded from the defense obligation with the United States. The broader atopally flag and all component obligations are retained for audit.",
                "2017 is observed. 2022 dynamic P2 is intentionally blank; a separately named structural_2018 field is supplied and is not presented as 2022 observation.",
                "No post-2018 alliance value was fabricated.",
            ],
        )
        print(result.to_string(index=False))
        return 0
    except Exception as exc:
        append_progress("ATOP v5.1 / P2", "FAILED", [str(exc), "No missing values were fabricated."])
        raise


if __name__ == "__main__":
    raise SystemExit(main())
