# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent.parent

MAINDATA_CSV = PROJECT_DIR / "maindata.csv"
COMP_SOURCE_CSV = PROJECT_DIR / "2.csv"
AJEX_SOURCE_CSV = PROJECT_DIR / "ajex.csv"

FIGURE1_START_YEAR = 1970
FIGURE1_PRE_MAIN_END_YEAR = 1979


def build_supplement(main: pd.DataFrame) -> pd.DataFrame:
    current_min_year = int(pd.to_numeric(main["fyear"], errors="coerce").min())
    end_year = min(current_min_year - 1, FIGURE1_PRE_MAIN_END_YEAR)
    if end_year < FIGURE1_START_YEAR:
        return main.iloc[0:0].copy()

    source = pd.read_csv(COMP_SOURCE_CSV, low_memory=False)
    source["fyear"] = pd.to_numeric(source["fyear"], errors="coerce")
    source = source[source["fyear"].between(FIGURE1_START_YEAR, end_year, inclusive="both")].copy()

    ajex = pd.read_csv(AJEX_SOURCE_CSV, usecols=["gvkey", "datadate", "ajex"], low_memory=False)
    source = source.merge(ajex, on=["gvkey", "datadate"], how="left", validate="one_to_one")

    missing_cols = sorted(set(main.columns) - set(source.columns))
    if missing_cols:
        raise ValueError(f"Supplement source is missing columns needed by maindata.csv: {missing_cols}")

    existing_keys = main[["gvkey", "datadate"]].drop_duplicates()
    supplement = source.merge(existing_keys, on=["gvkey", "datadate"], how="left", indicator=True)
    supplement = supplement[supplement["_merge"].eq("left_only")].drop(columns=["_merge"])
    return supplement.loc[:, main.columns].copy()


def main() -> None:
    if not MAINDATA_CSV.exists():
        raise FileNotFoundError(f"Missing maindata.csv: {MAINDATA_CSV}")
    if not COMP_SOURCE_CSV.exists():
        raise FileNotFoundError(f"Missing Compustat source CSV: {COMP_SOURCE_CSV}")
    if not AJEX_SOURCE_CSV.exists():
        raise FileNotFoundError(f"Missing ajex source CSV: {AJEX_SOURCE_CSV}")

    maindata = pd.read_csv(MAINDATA_CSV, low_memory=False)
    supplement = build_supplement(maindata)
    if supplement.empty:
        print("maindata.csv already covers the Figure 1 pre-1980 supplement window.")
        return

    combined = pd.concat([maindata, supplement], ignore_index=True)
    temp_path = MAINDATA_CSV.with_suffix(".csv.tmp")
    combined.to_csv(temp_path, index=False)
    temp_path.replace(MAINDATA_CSV)

    years = pd.to_numeric(supplement["fyear"], errors="coerce")
    print(f"Added {len(supplement)} rows to {MAINDATA_CSV}")
    print(f"Supplement years: {int(years.min())}-{int(years.max())}")
    print(f"maindata.csv rows after supplement: {len(combined)}")


if __name__ == "__main__":
    main()
