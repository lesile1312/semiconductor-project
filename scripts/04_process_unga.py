"""Download UNGA ideal points and construct three-year relative alignment P1."""

from __future__ import annotations

import hashlib
import json
from io import BytesIO

import pandas as pd
import requests

from gtri_config import COUNTRIES, PROCESSED_DIR, RAW_DIR, YEARS, append_progress, ensure_directories, utc_now


PERSISTENT_ID = "doi:10.7910/DVN/LEJUQZ"
METADATA_URL = "https://dataverse.harvard.edu/api/datasets/:persistentId/"
DATAFILE_URL = "https://dataverse.harvard.edu/api/access/datafile/{file_id}"
PREFERRED_FILENAMES = ("IdealpointsJuly2025.tab", "IdealpointestimatesAll_Jun2024.csv")


def main() -> int:
    ensure_directories()
    raw_dir = RAW_DIR / "unga"
    session = requests.Session()
    session.headers.update({"User-Agent": "GTRI-academic-research/0.1"})
    try:
        meta_response = session.get(METADATA_URL, params={"persistentId": PERSISTENT_ID}, timeout=120)
        meta_response.raise_for_status()
        metadata = meta_response.json()
        (raw_dir / "dataverse_metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        files = metadata["data"]["latestVersion"]["files"]
        by_name = {f["dataFile"]["filename"]: f["dataFile"] for f in files}
        selected = next((by_name[name] for name in PREFERRED_FILENAMES if name in by_name), None)
        if selected is None:
            raise RuntimeError("No recognized country-year ideal-point file in official Dataverse dataset")
        filename = selected["filename"]
        raw_path = raw_dir / filename
        if not raw_path.exists():
            response = session.get(DATAFILE_URL.format(file_id=selected["id"]), timeout=180)
            response.raise_for_status()
            raw_path.write_bytes(response.content)
        payload = raw_path.read_bytes()
        sep = "\t" if filename.lower().endswith(".tab") else ","
        df = pd.read_csv(BytesIO(payload), sep=sep)
        required = {"iso3c", "countryname", "year", "idealpointall"}
        if not required.issubset(df.columns):
            raise RuntimeError(f"Unexpected ideal-point columns; missing {sorted(required - set(df.columns))}")
        df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
        df["idealpointall"] = pd.to_numeric(df["idealpointall"], errors="coerce")

        detail_rows: list[dict] = []
        summary_rows: list[dict] = []
        for country in COUNTRIES:
            for target_year in YEARS:
                window = list(range(target_year - 1, target_year + 2))
                country_rows = df[(df["iso3c"] == country["iso3"]) & (df["year"].isin(window))]
                china_rows = df[(df["iso3c"] == "CHN") & (df["year"].isin(window))]
                us_rows = df[(df["iso3c"] == "USA") & (df["year"].isin(window))]
                merged = (
                    country_rows[["year", "idealpointall"]]
                    .rename(columns={"idealpointall": "country_ideal_point"})
                    .merge(china_rows[["year", "idealpointall"]].rename(columns={"idealpointall": "china_ideal_point"}), on="year")
                    .merge(us_rows[["year", "idealpointall"]].rename(columns={"idealpointall": "us_ideal_point"}), on="year")
                    .sort_values("year")
                )
                if len(merged) != 3 or merged.isna().any().any():
                    raise RuntimeError(f"Incomplete three-year UNGA window for {country['country']} {target_year}: {window}")
                merged["distance_to_china"] = (merged["country_ideal_point"] - merged["china_ideal_point"]).abs()
                merged["distance_to_us"] = (merged["country_ideal_point"] - merged["us_ideal_point"]).abs()
                for _, item in merged.iterrows():
                    detail_rows.append(
                        {
                            "country": country["country"], "iso3": country["iso3"],
                            "target_year": target_year, "window_year": int(item["year"]),
                            "country_ideal_point": item["country_ideal_point"],
                            "china_ideal_point": item["china_ideal_point"],
                            "us_ideal_point": item["us_ideal_point"],
                            "distance_to_china": item["distance_to_china"],
                            "distance_to_us": item["distance_to_us"],
                        }
                    )
                dc = float(merged["distance_to_china"].mean())
                du = float(merged["distance_to_us"].mean())
                denom = dc + du
                summary_rows.append(
                    {
                        "country": country["country"], "iso3": country["iso3"], "year": target_year,
                        "p1_unga_relative_alignment": dc / denom if denom else pd.NA,
                        "avg_distance_to_china": dc, "avg_distance_to_us": du,
                        "window_start": window[0], "window_end": window[-1],
                        "ideal_point_column": "idealpointall",
                        "source_flag": f"UNGA_Voeten_Dataverse_file_{selected['id']}",
                    }
                )

        details = pd.DataFrame(detail_rows)
        summary = pd.DataFrame(summary_rows)
        details.to_csv(PROCESSED_DIR / "unga_p1_window_detail.csv", index=False, encoding="utf-8-sig")
        summary.to_csv(PROCESSED_DIR / "unga_p1_country_year.csv", index=False, encoding="utf-8-sig")
        source_meta = {
            "downloaded_at_utc": utc_now(), "persistent_id": PERSISTENT_ID,
            "file_id": selected["id"], "filename": filename,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "formula": "mean(abs(country-China)) / (mean(abs(country-China)) + mean(abs(country-USA)))",
            "window": "centered three-year window [target_year-1, target_year, target_year+1]",
            "ideal_point_column": "idealpointall",
        }
        (raw_dir / "source_metadata.json").write_text(
            json.dumps(source_meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        append_progress(
            "UNGA ideal points / P1",
            "complete",
            [
                f"Downloaded official Harvard Dataverse file {filename} (file id {selected['id']}); SHA-256 retained.",
                "Used idealpointall and centered three-year windows: 2016-2018 for 2017, 2021-2023 for 2022.",
                "P1 = average distance to China / (average distance to China + average distance to USA). Higher values indicate relative proximity to the US pole.",
                f"Produced {len(summary)} summary rows and {len(details)} auditable country-window-year detail rows; no missing windows.",
            ],
        )
        print(summary.to_string(index=False))
        return 0
    except Exception as exc:
        append_progress("UNGA ideal points / P1", "FAILED", [str(exc), "No missing values were fabricated."])
        raise


if __name__ == "__main__":
    raise SystemExit(main())
