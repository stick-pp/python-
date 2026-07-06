from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter


# ---------------------------------------------------------------------------
# User-facing configuration
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent.parent
SHARED_PYTHON_OUT = PROJECT_DIR / "shared_artifacts" / "python_out"
MAIN_CSV = BASE_DIR / "2.csv"
AJEX_CSV = BASE_DIR / "ajex.csv"
CCM_LINK_CSV = BASE_DIR / "CCM Link Table.csv"
CRSP_DSE_NAMES_CSV = BASE_DIR / "crsp_dse_names.csv"
PAST_STOCK_RETURN_CSV = BASE_DIR / "Past stock return.csv"
OUTPUT_DIR = SHARED_PYTHON_OUT


# ---------------------------------------------------------------------------
# Constants and display helpers
# ---------------------------------------------------------------------------

FIG_DIR = OUTPUT_DIR / "figures"
TABLE_DIR = OUTPUT_DIR / "tables"
STATA_DIR = OUTPUT_DIR / "stata"
QA_DIR = OUTPUT_DIR / "qa"

PAGE = (11.0, 8.5)
COLOR_EARNINGS = "#1f4e79"
COLOR_SPECIAL = "#8c564b"
COLOR_DIVIDENDS = "#2ca02c"
COLOR_REPURCHASES = "#d62728"
GRID_COLOR = "#d9d9d9"

GROUP_NAMES = {
    1: "Non-payers",
    2: "Regular div. + regular rep.",
    3: "Occasional rep. only",
    4: "Regular rep. only",
    5: "Dividend-only regular",
}

GROUP_NAMES_CN = {
    1: "Group I: Non-payers",
    2: "Group II: Regular dividends and regular repurchases",
    3: "Group III: Occasional repurchases only",
    4: "Group IV: Regular repurchases only",
    5: "Group V: Dividend-only regular payers",
}

PUBLISHED_GROUP_COUNTS = {
    1: 3983,
    2: 345,
    3: 2518,
    4: 351,
    5: 141,
}

PUBLISHED_TABLE1_TOTALS = {
    (1980, 1989): 5690,
    (1985, 1994): 6622,
    (1990, 1999): 7744,
    (1995, 2004): 7595,
}

PUBLISHED_TABLE2_TOTAL = 10675
PUBLISHED_TABLE2_ZERO_DIV_COLUMN = 6852

PUBLISHED_TABLE3_N = {
    ("Panel A", "1980-1994"): 4801,
    ("Panel A", "1995-2005"): 3510,
    ("Panel A", "1995-2005 ESO"): 3173,
    ("Panel B", "1980-1994"): 11581,
    ("Panel B", "1995-2005"): 15279,
    ("Panel B", "1995-2005 ESO"): 12965,
}

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"],
        "font.size": 10,
        "axes.titlesize": 13,
        "axes.labelsize": 10,
        "legend.fontsize": 9,
        "figure.dpi": 150,
        "savefig.dpi": 220,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.unicode_minus": False,
    }
)


def ensure_dirs() -> None:
    for folder in [OUTPUT_DIR, FIG_DIR, TABLE_DIR, STATA_DIR, QA_DIR]:
        folder.mkdir(parents=True, exist_ok=True)


def fmt_millions_axis(x: float, _pos: int) -> str:
    return f"{x:,.0f}"


def safe_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def fmt_pct(value: float) -> str:
    if pd.isna(value):
        return ""
    return f"{value * 100:.1f}%"


def fmt_int(value: float) -> str:
    if pd.isna(value):
        return ""
    return f"{int(round(value)):,.0f}"


def fmt_money(value: float) -> str:
    if pd.isna(value):
        return ""
    return f"{value:,.0f}"


def fmt_frac(value: float) -> str:
    if pd.isna(value):
        return ""
    value = 0.0 if abs(value) < 0.0005 else value
    return f"{value:.3f}"


def sum_observed(series: pd.Series) -> float:
    return series.sum(min_count=1)


def place_xaxis_at_zero(ax: plt.Axes) -> None:
    ax.spines["bottom"].set_position(("data", 0))
    ax.spines["bottom"].set_visible(True)
    ax.spines["top"].set_visible(False)
    ax.xaxis.set_ticks_position("bottom")
    ax.xaxis.set_label_position("bottom")


def assert_unique_firm_year(df: pd.DataFrame, context: str) -> None:
    dup_mask = df.duplicated(["gvkey", "fyear"], keep=False)
    if not dup_mask.any():
        return
    examples = (
        df.loc[dup_mask, ["gvkey", "fyear", "datadate"]]
        .head(10)
        .to_dict(orient="records")
    )
    raise ValueError(f"{context} has duplicated gvkey-fyear rows. Examples: {examples}")


# ---------------------------------------------------------------------------
# Data processing
# ---------------------------------------------------------------------------


def read_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if not MAIN_CSV.exists():
        raise FileNotFoundError(f"Missing main WRDS file: {MAIN_CSV}")
    if not AJEX_CSV.exists():
        raise FileNotFoundError(f"Missing adjustment-factor file: {AJEX_CSV}")
    if not CCM_LINK_CSV.exists():
        raise FileNotFoundError(f"Missing CCM link table: {CCM_LINK_CSV}")
    if not CRSP_DSE_NAMES_CSV.exists():
        raise FileNotFoundError(f"Missing CRSP name history file: {CRSP_DSE_NAMES_CSV}")
    if not PAST_STOCK_RETURN_CSV.exists():
        raise FileNotFoundError(f"Missing past stock return price file: {PAST_STOCK_RETURN_CSV}")

    main = pd.read_csv(MAIN_CSV, low_memory=False)
    ajex = pd.read_csv(AJEX_CSV, low_memory=False)
    ccm_link = pd.read_csv(
        CCM_LINK_CSV,
        usecols=["gvkey", "LPERMNO", "LINKDT", "LINKENDDT", "LINKTYPE", "LINKPRIM"],
        low_memory=False,
    )
    crsp_names = pd.read_csv(
        CRSP_DSE_NAMES_CSV,
        usecols=["DATE", "NAMEENDT", "PERMNO", "SHRCD", "EXCHCD"],
        low_memory=False,
    )
    past_stock_prices = pd.read_csv(PAST_STOCK_RETURN_CSV, low_memory=False)

    required_main = {
        "costat",
        "curcd",
        "datafmt",
        "indfmt",
        "consol",
        "gvkey",
        "datadate",
        "fic",
        "sic",
        "sich",
        "fyear",
        "at",
        "ceq",
        "che",
        "re",
        "tstkc",
        "dvc",
        "ib",
        "oibdp",
        "sale",
        "spi",
        "xintopt",
        "prstkc",
        "sstk",
        "csho",
        "prcc_f",
    }
    required_ajex = {"gvkey", "datadate", "ajex"}
    required_past_stock_prices = {
        "costat",
        "curcd",
        "datafmt",
        "indfmt",
        "consol",
        "gvkey",
        "datadate",
        "sic",
        "sich",
        "fyear",
        "prcc_f",
        "ajex",
    }
    missing_main = sorted(required_main - set(main.columns))
    missing_ajex = sorted(required_ajex - set(ajex.columns))
    missing_past_stock_prices = sorted(required_past_stock_prices - set(past_stock_prices.columns))
    if missing_main:
        raise ValueError(f"Main CSV is missing variables: {missing_main}")
    if missing_ajex:
        raise ValueError(f"ajex CSV is missing variables: {missing_ajex}")
    if missing_past_stock_prices:
        raise ValueError(f"Past stock return CSV is missing variables: {missing_past_stock_prices}")

    if main.duplicated(["gvkey", "datadate"]).any():
        raise ValueError("Main CSV has duplicated gvkey-datadate rows.")
    if ajex.duplicated(["gvkey", "datadate"]).any():
        raise ValueError("ajex CSV has duplicated gvkey-datadate rows.")
    return main, ajex, ccm_link, crsp_names, past_stock_prices


def parse_wrds_date(series: pd.Series, *, open_ended: bool = False) -> pd.Series:
    values = series.astype("string").str.strip()
    values = values.mask(values.eq(""))
    if open_ended:
        values = values.replace({"E": "2099-12-31"})
    return pd.to_datetime(values, errors="coerce")


def prepare_ccm_link_table(ccm_link: pd.DataFrame) -> pd.DataFrame:
    ccm = ccm_link.rename(columns=str.lower).copy()
    ccm["gvkey"] = safe_numeric(ccm["gvkey"])
    ccm["lpermno"] = safe_numeric(ccm["lpermno"])
    ccm["linkdt"] = parse_wrds_date(ccm["linkdt"])
    ccm["linkenddt"] = parse_wrds_date(ccm["linkenddt"], open_ended=True).fillna(pd.Timestamp("2099-12-31"))
    ccm["linktype"] = ccm["linktype"].astype("string").str.strip().str.upper()
    ccm["linkprim"] = ccm["linkprim"].astype("string").str.strip().str.upper()
    return ccm[
        ccm["linktype"].isin(["LC", "LU", "LS"])
        & ccm["linkprim"].isin(["P", "C"])
        & ccm["gvkey"].notna()
        & ccm["lpermno"].notna()
        & ccm["linkdt"].notna()
    ].copy()


def prepare_crsp_name_history(crsp_names: pd.DataFrame) -> pd.DataFrame:
    names = crsp_names.rename(columns=str.lower).rename(columns={"date": "namedt"}).copy()
    names["permno"] = safe_numeric(names["permno"])
    names["shrcd"] = safe_numeric(names["shrcd"])
    names["exchcd"] = safe_numeric(names["exchcd"])
    names["namedt"] = parse_wrds_date(names["namedt"])
    names["nameendt"] = parse_wrds_date(names["nameendt"], open_ended=True).fillna(pd.Timestamp("2099-12-31"))
    return names[
        names["shrcd"].isin([10, 11])
        & names["exchcd"].isin([1, 2, 3])
        & names["permno"].notna()
        & names["namedt"].notna()
    ].copy()


def apply_crsp_ccm_stock_screen(
    df: pd.DataFrame,
    ccm_link: pd.DataFrame,
    crsp_names: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, float]]:
    ccm = prepare_ccm_link_table(ccm_link)
    names = prepare_crsp_name_history(crsp_names)
    work = df.copy()
    work["datadate_dt"] = parse_wrds_date(work["datadate"])
    valid_datadate = work["datadate_dt"].notna()

    linked = work[valid_datadate].merge(ccm, on="gvkey", how="inner")
    linked = linked[
        linked["datadate_dt"].ge(linked["linkdt"])
        & linked["datadate_dt"].le(linked["linkenddt"])
    ].copy()

    screened = linked.merge(names, left_on="lpermno", right_on="permno", how="inner")
    screened = screened[
        screened["datadate_dt"].ge(screened["namedt"])
        & screened["datadate_dt"].le(screened["nameendt"])
    ].copy()

    helper_cols = [
        "datadate_dt",
        "lpermno",
        "linkdt",
        "linkenddt",
        "linktype",
        "linkprim",
        "permno",
        "namedt",
        "nameendt",
        "shrcd",
        "exchcd",
    ]
    screened = screened.drop(columns=helper_cols, errors="ignore")
    summary = {
        "ccm_link_rows_used": len(ccm),
        "crsp_name_rows_used": len(names),
        "crsp_ccm_valid_datadate_rows": int(valid_datadate.sum()),
        "crsp_ccm_linked_rows": len(linked),
        "crsp_ccm_linked_firms": int(linked["gvkey"].nunique()),
        "crsp_ccm_screened_rows": len(screened),
        "crsp_ccm_screened_firms": int(screened["gvkey"].nunique()),
    }
    return screened, summary


def nearest_adjusted_price_lag3(
    df: pd.DataFrame,
    tolerance_days: int = 183,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    work = df[["gvkey", "datadate", "adjusted_price"]].copy()
    work["datadate_dt"] = parse_wrds_date(work["datadate"])
    work["target_lag3_date"] = work["datadate_dt"] - pd.DateOffset(years=3)
    lag_price = pd.Series(np.nan, index=df.index, dtype="float64")
    matched = pd.Series(False, index=df.index)
    distance_days = pd.Series(np.nan, index=df.index, dtype="float64")
    history = work.dropna(subset=["gvkey", "datadate_dt", "adjusted_price"]).copy()
    history_groups = {gvkey: group.sort_values("datadate_dt") for gvkey, group in history.groupby("gvkey")}

    for gvkey, idx in work.groupby("gvkey").groups.items():
        hist = history_groups.get(gvkey)
        if hist is None or hist.empty:
            continue

        current = work.loc[idx]
        dates = hist["datadate_dt"].to_numpy(dtype="datetime64[ns]")
        prices = hist["adjusted_price"].to_numpy(dtype="float64")
        targets = current["target_lag3_date"].to_numpy(dtype="datetime64[ns]")
        positions = np.searchsorted(dates, targets)
        best_positions = np.full(len(current), -1, dtype=int)
        best_distances = np.full(len(current), np.inf)

        for candidates in [positions - 1, positions]:
            valid = (candidates >= 0) & (candidates < len(dates))
            if not valid.any():
                continue
            candidate_distances = np.full(len(current), np.inf)
            candidate_distances[valid] = np.abs(
                (dates[candidates[valid]] - targets[valid]).astype("timedelta64[D]").astype(float)
            )
            take = candidate_distances < best_distances
            best_distances[take] = candidate_distances[take]
            best_positions[take] = candidates[take]

        usable = (best_positions >= 0) & (best_distances <= tolerance_days)
        lag_price.loc[current.index[usable]] = prices[best_positions[usable]]
        matched.loc[current.index[usable]] = True
        distance_days.loc[current.index[usable]] = best_distances[usable]

    return lag_price, matched, distance_days


def prepare_past_stock_return_price_history(
    price_history: pd.DataFrame,
    ccm_link: pd.DataFrame,
    crsp_names: pd.DataFrame,
    use_crsp_ccm_screen: bool = True,
) -> tuple[pd.DataFrame, dict[str, float]]:
    history = price_history.copy()
    numeric_cols = ["gvkey", "fyear", "sic", "sich", "prcc_f", "ajex"]
    for col in numeric_cols:
        history[col] = safe_numeric(history[col])

    raw_rows = len(history)
    raw_firms = int(history["gvkey"].nunique())
    format_mask = (
        (history["consol"] == "C")
        & (history["indfmt"] == "INDL")
        & (history["datafmt"] == "STD")
        & (history["curcd"] == "USD")
    )
    history = history[format_mask].copy()
    format_rows = len(history)
    format_firms = int(history["gvkey"].nunique())

    history["sic_use"] = history["sich"].where(history["sich"].notna(), history["sic"])
    industry_excluded = history["sic_use"].between(6000, 6999, inclusive="both") | history["sic_use"].between(
        4900, 4999, inclusive="both"
    )
    history = history[~industry_excluded].copy()
    industry_rows = len(history)
    industry_firms = int(history["gvkey"].nunique())

    if use_crsp_ccm_screen:
        history, stock_summary = apply_crsp_ccm_stock_screen(history, ccm_link, crsp_names)
        stock_summary = {f"past_return_price_{key}": value for key, value in stock_summary.items()}
    else:
        stock_summary = {
            "past_return_price_crsp_ccm_linked_rows": len(history),
            "past_return_price_crsp_ccm_linked_firms": int(history["gvkey"].nunique()),
            "past_return_price_crsp_ccm_screened_rows": len(history),
            "past_return_price_crsp_ccm_screened_firms": int(history["gvkey"].nunique()),
        }

    history["datadate_dt"] = parse_wrds_date(history["datadate"])
    history["adjusted_price"] = np.where(
        history["prcc_f"].notna() & history["prcc_f"].gt(0) & history["ajex"].notna() & history["ajex"].gt(0),
        history["prcc_f"] / history["ajex"],
        np.nan,
    )
    history = history[history["gvkey"].notna() & history["fyear"].notna() & history["datadate_dt"].notna()].copy()
    history["has_external_adjusted_price"] = history["adjusted_price"].notna()
    history = history.sort_values(["gvkey", "fyear", "has_external_adjusted_price", "datadate_dt"])
    duplicate_gvkey_fyear_rows = int(history.duplicated(["gvkey", "fyear"]).sum())
    history = history.drop_duplicates(["gvkey", "fyear"], keep="last").copy()

    stats = {
        "past_return_price_raw_rows": raw_rows,
        "past_return_price_raw_firms": raw_firms,
        "past_return_price_format_rows": format_rows,
        "past_return_price_format_firms": format_firms,
        "past_return_price_industry_rows": industry_rows,
        "past_return_price_industry_firms": industry_firms,
        "past_return_price_duplicate_gvkey_fyear_rows_removed": duplicate_gvkey_fyear_rows,
        "past_return_price_final_rows": len(history),
        "past_return_price_final_firms": int(history["gvkey"].nunique()),
        "past_return_price_adjusted_price_nonmissing": int(history["adjusted_price"].notna().sum()),
        **stock_summary,
    }
    keep_cols = ["gvkey", "fyear", "datadate", "datadate_dt", "adjusted_price"]
    return history[keep_cols].copy(), stats


def nearest_adjusted_price_lag3_from_history(
    target: pd.DataFrame,
    history: pd.DataFrame,
    tolerance_days: int = 183,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    work = target[["gvkey", "datadate"]].copy()
    work["datadate_dt"] = parse_wrds_date(work["datadate"])
    work["target_lag3_date"] = work["datadate_dt"] - pd.DateOffset(years=3)
    lag_price = pd.Series(np.nan, index=target.index, dtype="float64")
    matched = pd.Series(False, index=target.index)
    distance_days = pd.Series(np.nan, index=target.index, dtype="float64")
    usable_history = history.dropna(subset=["gvkey", "datadate_dt", "adjusted_price"]).copy()
    history_groups = {gvkey: group.sort_values("datadate_dt") for gvkey, group in usable_history.groupby("gvkey")}

    for gvkey, idx in work.groupby("gvkey").groups.items():
        hist = history_groups.get(gvkey)
        if hist is None or hist.empty:
            continue

        current = work.loc[idx]
        dates = hist["datadate_dt"].to_numpy(dtype="datetime64[ns]")
        prices = hist["adjusted_price"].to_numpy(dtype="float64")
        targets = current["target_lag3_date"].to_numpy(dtype="datetime64[ns]")
        positions = np.searchsorted(dates, targets)
        best_positions = np.full(len(current), -1, dtype=int)
        best_distances = np.full(len(current), np.inf)

        for candidates in [positions - 1, positions]:
            valid = (candidates >= 0) & (candidates < len(dates))
            if not valid.any():
                continue
            candidate_distances = np.full(len(current), np.inf)
            candidate_distances[valid] = np.abs(
                (dates[candidates[valid]] - targets[valid]).astype("timedelta64[D]").astype(float)
            )
            take = candidate_distances < best_distances
            best_distances[take] = candidate_distances[take]
            best_positions[take] = candidates[take]

        usable = (best_positions >= 0) & (best_distances <= tolerance_days)
        lag_price.loc[current.index[usable]] = prices[best_positions[usable]]
        matched.loc[current.index[usable]] = True
        distance_days.loc[current.index[usable]] = best_distances[usable]

    return lag_price, matched, distance_days


def apply_external_past_stock_return(df: pd.DataFrame, price_history: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    current_prices = price_history[["gvkey", "fyear", "adjusted_price"]].rename(
        columns={"adjusted_price": "adjusted_price_external"}
    )
    out = out.merge(current_prices, on=["gvkey", "fyear"], how="left", validate="one_to_one")
    out["adjusted_price"] = out["adjusted_price_external"]

    price_lag = price_history[["gvkey", "fyear", "adjusted_price"]].copy()
    price_lag["fyear"] = price_lag["fyear"] + 3
    price_lag["has_adjusted_price_lag3_row"] = True
    price_lag = price_lag.rename(columns={"adjusted_price": "adjusted_price_lag3"})
    out = out.merge(price_lag, on=["gvkey", "fyear"], how="left", validate="one_to_one")
    out["has_adjusted_price_lag3_row"] = out["has_adjusted_price_lag3_row"].eq(True)

    lag3_date_price, lag3_date_matched, lag3_date_distance = nearest_adjusted_price_lag3_from_history(out, price_history)
    need_date_lag = out["adjusted_price_lag3"].isna()
    out["adjusted_price_lag3_date"] = lag3_date_price
    out["has_adjusted_price_lag3_date_match"] = lag3_date_matched
    out["adjusted_price_lag3_date_distance_days"] = lag3_date_distance
    out.loc[need_date_lag, "adjusted_price_lag3"] = out.loc[need_date_lag, "adjusted_price_lag3_date"]
    out["past_stock_return_source"] = pd.Series(pd.NA, index=out.index, dtype="object")
    out.loc[out["has_adjusted_price_lag3_row"], "past_stock_return_source"] = "past_return_csv_exact_fyear_lag3"
    out.loc[
        need_date_lag & out["has_adjusted_price_lag3_date_match"],
        "past_stock_return_source",
    ] = "past_return_csv_nearest_datadate_lag3"
    out["past_stock_return"] = np.where(
        out["adjusted_price"].notna() & out["adjusted_price_lag3"].notna() & out["adjusted_price_lag3"].gt(0),
        out["adjusted_price"] / out["adjusted_price_lag3"] - 1,
        np.nan,
    )
    return out


def clean_and_construct(
    main: pd.DataFrame,
    ajex: pd.DataFrame,
    ccm_link: pd.DataFrame,
    crsp_names: pd.DataFrame,
    past_stock_prices: pd.DataFrame,
    use_crsp_ccm_screen: bool = True,
) -> tuple[pd.DataFrame, dict[str, float]]:
    df = main.merge(
        ajex[["gvkey", "datadate", "ajex"]],
        on=["gvkey", "datadate"],
        how="left",
        validate="one_to_one",
    )

    numeric_cols = [
        "gvkey",
        "fyear",
        "fyr",
        "sic",
        "sich",
        "at",
        "ceq",
        "che",
        "re",
        "tstkc",
        "dvc",
        "ib",
        "oibdp",
        "sale",
        "spi",
        "xintopt",
        "prstkc",
        "sstk",
        "csho",
        "prcc_f",
        "ajex",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = safe_numeric(df[col])

    raw_rows = len(df)
    raw_firms = int(df["gvkey"].nunique())
    ajex_match_rate = float(df["ajex"].notna().mean())

    format_mask = (
        (df["consol"] == "C")
        & (df["indfmt"] == "INDL")
        & (df["datafmt"] == "STD")
        & (df["curcd"] == "USD")
    )
    df = df[format_mask].copy()
    wrds_rows = len(df)
    wrds_firms = int(df["gvkey"].nunique())

    df = df[df["fic"] == "USA"].copy()
    usa_rows = len(df)
    usa_firms = int(df["gvkey"].nunique())

    df["sic_use"] = df["sich"].where(df["sich"].notna(), df["sic"])
    sic_use_from_sich_rows = int(df["sich"].notna().sum())
    sic_use_from_sic_rows = int((df["sich"].isna() & df["sic"].notna()).sum())
    both_sic_missing = df["sic"].isna() & df["sich"].isna()

    df["is_financial"] = df["sic_use"].between(6000, 6999, inclusive="both")
    df["is_utility"] = df["sic_use"].between(4900, 4999, inclusive="both")
    industry_excluded = df["is_financial"] | df["is_utility"]
    industry_excluded_rows = int(industry_excluded.sum())
    industry_excluded_firms = int(df.loc[industry_excluded, "gvkey"].nunique())
    industry_excluded_financial_rows = int(df["is_financial"].sum())
    industry_excluded_utility_rows = int(df["is_utility"].sum())
    sic_sich_missing_rows = int(both_sic_missing.sum())
    sic_sich_missing_firms = int(df.loc[both_sic_missing, "gvkey"].nunique())

    df = df[~industry_excluded].copy()
    clean_rows_before_year = len(df)
    clean_firms_before_year = int(df["gvkey"].nunique())

    if use_crsp_ccm_screen:
        df, stock_screen_summary = apply_crsp_ccm_stock_screen(df, ccm_link, crsp_names)
        sample_context = "CRSP/CCM-screened clean Compustat sample"
    else:
        stock_screen_summary = {
            "ccm_link_rows_used": 0,
            "crsp_name_rows_used": 0,
            "crsp_ccm_valid_datadate_rows": len(df),
            "crsp_ccm_linked_rows": len(df),
            "crsp_ccm_linked_firms": int(df["gvkey"].nunique()),
            "crsp_ccm_screened_rows": len(df),
            "crsp_ccm_screened_firms": int(df["gvkey"].nunique()),
        }
        sample_context = "Compustat sample without CRSP/CCM stock screen"

    df = df.sort_values(["gvkey", "fyear", "datadate"]).reset_index(drop=True)
    assert_unique_firm_year(df, sample_context)

    df["dividend"] = df["dvc"]
    df["dividend_dummy"] = np.select(
        [df["dvc"].gt(0), df["dvc"].eq(0)],
        [1.0, 0.0],
        default=np.nan,
    )
    df["special_items"] = df["spi"].fillna(0)
    df["earnings"] = df["ib"]
    df["adjusted_earnings"] = np.where(
        df["ib"].notna(),
        df["ib"] - 0.6 * df["special_items"],
        np.nan,
    )

    lag_tstkc = df[["gvkey", "fyear", "tstkc"]].copy()
    lag_tstkc["fyear"] = lag_tstkc["fyear"] + 1
    lag_tstkc["has_tstkc_lag1_row"] = True
    lag_tstkc = lag_tstkc.rename(columns={"tstkc": "tstkc_lag1"})
    df = df.merge(lag_tstkc, on=["gvkey", "fyear"], how="left", validate="one_to_one")
    df["has_tstkc_lag1_row"] = df["has_tstkc_lag1_row"].eq(True)

    tstkc_pair_observed = df["tstkc"].notna() & df["tstkc_lag1"].notna()
    retirement_method = tstkc_pair_observed & df["tstkc"].eq(0) & df["tstkc_lag1"].eq(0)
    treasury_method = tstkc_pair_observed & ~retirement_method
    cashflow_complete = df["prstkc"].notna() & df["sstk"].notna()
    retirement_complete = retirement_method & cashflow_complete
    missing_tstkc_pair_cashflow_complete = ~tstkc_pair_observed & cashflow_complete

    df["repurchase"] = np.nan
    df["repurchase_source"] = pd.Series(pd.NA, index=df.index, dtype="object")
    df.loc[treasury_method, "repurchase"] = df.loc[treasury_method, "tstkc"] - df.loc[treasury_method, "tstkc_lag1"]
    df.loc[treasury_method, "repurchase_source"] = "treasury_stock_change"
    df.loc[retirement_complete, "repurchase"] = (
        df.loc[retirement_complete, "prstkc"] - df.loc[retirement_complete, "sstk"]
    )
    df.loc[retirement_complete, "repurchase_source"] = "retirement_method"
    df.loc[retirement_method & ~cashflow_complete, "repurchase_source"] = "missing_cashflow_inputs"
    df.loc[missing_tstkc_pair_cashflow_complete, "repurchase_source"] = "missing_tstkc_pair_cashflow_available_not_used"
    df.loc[~tstkc_pair_observed & ~cashflow_complete, "repurchase_source"] = "missing_tstkc_pair_and_cashflow_inputs"
    df["repurchase"] = df["repurchase"].replace([np.inf, -np.inf], np.nan).clip(lower=0)
    df["repurchase_dummy"] = np.select(
        [df["repurchase"].gt(0), df["repurchase"].eq(0)],
        [1.0, 0.0],
        default=np.nan,
    )

    df["total_payout"] = df["dividend"] + df["repurchase"]
    df["loss"] = np.where(df["earnings"].notna(), (df["earnings"] < 0).astype(float), np.nan)

    lag_at = df[["gvkey", "fyear", "at"]].copy()
    lag_at["fyear"] = lag_at["fyear"] + 1
    lag_at["has_at_lag1_row"] = True
    lag_at = lag_at.rename(columns={"at": "at_lag1"})
    df = df.merge(lag_at, on=["gvkey", "fyear"], how="left", validate="one_to_one")
    df["has_at_lag1_row"] = df["has_at_lag1_row"].eq(True)
    df["roa"] = np.where(
        df["oibdp"].notna() & df["at_lag1"].notna() & df["at_lag1"].gt(0),
        df["oibdp"] / df["at_lag1"],
        np.nan,
    )
    df["cash"] = np.where(
        df["che"].notna() & df["at"].notna() & df["at"].gt(0),
        df["che"] / df["at"],
        np.nan,
    )
    past_return_price_history, past_return_price_summary = prepare_past_stock_return_price_history(
        past_stock_prices,
        ccm_link,
        crsp_names,
        use_crsp_ccm_screen=use_crsp_ccm_screen,
    )
    df = apply_external_past_stock_return(df, past_return_price_history)
    df["eso_dilution"] = np.where(
        df["fyear"].ge(1995)
        & df["xintopt"].notna()
        & df["sale"].notna()
        & df["sale"].gt(0)
        & df["past_stock_return"].notna(),
        (df["xintopt"] / df["sale"]) * df["past_stock_return"],
        np.nan,
    )

    summary = {
        "raw_rows": raw_rows,
        "raw_firms": raw_firms,
        "ajex_match_rate": ajex_match_rate,
        "wrds_rows": wrds_rows,
        "wrds_firms": wrds_firms,
        "usa_rows": usa_rows,
        "usa_firms": usa_firms,
        "industry_excluded_rows": industry_excluded_rows,
        "industry_excluded_firms": industry_excluded_firms,
        "industry_excluded_financial_rows": industry_excluded_financial_rows,
        "industry_excluded_utility_rows": industry_excluded_utility_rows,
        "sic_use_from_sich_rows": sic_use_from_sich_rows,
        "sic_use_from_sic_rows": sic_use_from_sic_rows,
        "sic_sich_missing_rows": sic_sich_missing_rows,
        "sic_sich_missing_firms": sic_sich_missing_firms,
        "clean_rows_before_year": clean_rows_before_year,
        "clean_firms_before_year": clean_firms_before_year,
        "firm_year_duplicate_rows_after_clean": 0,
        **stock_screen_summary,
        **past_return_price_summary,
    }
    return df, summary


def div_bucket_table1(n: int) -> str:
    if n == 0:
        return "0"
    if n <= 4:
        return "1-4"
    if n <= 9:
        return "5-9"
    return "10"


def rep_bucket_table1(n: int) -> str:
    if n == 0:
        return "0"
    if n <= 4:
        return "1-4"
    return "5+"


def bucket_table2(n: int) -> str:
    if n == 0:
        return "0"
    if n <= 5:
        return "1-5"
    if n <= 10:
        return "6-10"
    if n <= 15:
        return "11-15"
    if n <= 20:
        return "16-20"
    return ">20"


def firm_period_counts(df: pd.DataFrame, start: int, end: int) -> pd.DataFrame:
    period = df[(df["fyear"] >= start) & (df["fyear"] <= end)].copy()
    firm = (
        period.groupby("gvkey")
        .agg(
            div_years=("dividend_dummy", lambda x: int((x == 1).sum())),
            rep_years=("repurchase_dummy", lambda x: int((x == 1).sum())),
            div_valid_years=("dividend_dummy", "count"),
            rep_valid_years=("repurchase_dummy", "count"),
            firm_years=("fyear", "nunique"),
            total_payout=("total_payout", sum_observed),
        )
        .reset_index()
    )
    firm["div_missing_years"] = firm["firm_years"] - firm["div_valid_years"]
    firm["rep_missing_years"] = firm["firm_years"] - firm["rep_valid_years"]
    firm["main_sample_entry"] = firm["div_valid_years"].ge(1) & firm["rep_valid_years"].ge(1)
    firm["div_status_complete"] = firm["div_valid_years"].eq(firm["firm_years"])
    firm["rep_status_complete"] = firm["rep_valid_years"].eq(firm["firm_years"])
    firm["payout_status_complete"] = firm["div_status_complete"] & firm["rep_status_complete"]
    firm["payout_classifiable"] = firm["main_sample_entry"]
    return firm


def add_long_run_groups(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    firm = firm_period_counts(df, 1980, 2005)
    entrant = firm["main_sample_entry"]
    firm["div_bucket_t2"] = firm["div_years"].map(bucket_table2)
    firm["rep_bucket_t2"] = firm["rep_years"].map(bucket_table2)

    conditions = [
        (entrant & firm["div_years"].eq(0) & firm["rep_years"].eq(0)),
        (entrant & firm["div_years"].ge(16) & firm["rep_years"].ge(11)),
        (entrant & firm["div_years"].eq(0) & firm["rep_years"].between(1, 5, inclusive="both")),
        (entrant & firm["div_years"].eq(0) & firm["rep_years"].ge(6)),
        (entrant & firm["rep_years"].eq(0) & firm["div_years"].ge(6)),
    ]
    choices = [1, 2, 3, 4, 5]
    firm["group_id"] = pd.Series(pd.NA, index=firm.index, dtype="Int64")
    for condition, choice in zip(conditions, choices):
        firm.loc[condition, "group_id"] = choice
    firm.loc[entrant & firm["group_id"].isna(), "group_id"] = 0
    firm["group_name"] = firm["group_id"].map(GROUP_NAMES)
    firm.loc[firm["group_id"].eq(0).fillna(False), "group_name"] = "Other"
    firm["group_name"] = firm["group_name"].fillna("No 1980-2005 observation")

    out = df.merge(firm[["gvkey", "group_id", "group_name"]], on="gvkey", how="left")
    out["regular_dummy"] = np.nan
    out.loc[out["group_id"].eq(4).fillna(False), "regular_dummy"] = 1.0
    out.loc[out["group_id"].eq(3).fillna(False), "regular_dummy"] = 0.0
    out["roa_regular"] = out["roa"] * out["regular_dummy"]
    return out, firm


# ---------------------------------------------------------------------------
# Tables and figures
# ---------------------------------------------------------------------------


def build_figure1(df: pd.DataFrame) -> pd.DataFrame:
    sample = df[(df["fyear"] >= 1970) & (df["fyear"] <= 2005)].copy()
    annual = (
        sample.groupby("fyear")
        .agg(
            earnings=("earnings", sum_observed),
            special_items=("special_items", sum_observed),
            dividends=("dividend", sum_observed),
            net_repurchases=("repurchase", sum_observed),
            firms=("gvkey", "nunique"),
        )
        .reset_index()
    )
    annual.to_csv(TABLE_DIR / "figure1_annual_aggregates.csv", index=False)
    return annual


def plot_figure1(annual: pd.DataFrame) -> plt.Figure:
    fig, ax = plt.subplots(figsize=PAGE)
    ax.plot(annual["fyear"], annual["earnings"], color=COLOR_EARNINGS, lw=2.2, label="Compustat earnings")
    ax.plot(
        annual["fyear"],
        annual["special_items"],
        color=COLOR_SPECIAL,
        lw=1.8,
        ls=(0, (5, 2, 1, 2)),
        label="Special items",
    )
    ax.plot(annual["fyear"], annual["dividends"], color=COLOR_DIVIDENDS, lw=1.9, ls="--", label="Dividends")
    ax.plot(
        annual["fyear"],
        annual["net_repurchases"],
        color=COLOR_REPURCHASES,
        lw=1.9,
        ls=(0, (8, 3)),
        label="Net repurchases",
    )
    place_xaxis_at_zero(ax)
    ax.set_xlim(1970, 2005)
    ax.set_ylim(-400000, 600000)
    ax.margins(x=0)
    ax.set_title("Figure 1  Aggregate Compustat earnings, special items, dividends, and net repurchases, 1970-2005")
    ax.set_xlabel("Fiscal year")
    ax.set_ylabel("$ millions")
    ax.yaxis.set_major_formatter(FuncFormatter(fmt_millions_axis))
    ax.grid(axis="y", color=GRID_COLOR, lw=0.6)
    ax.legend(loc="upper left", frameon=False, ncol=2)
    fig.text(
        0.09,
        0.03,
        "Notes: Amounts are in Compustat $ millions. The earnings line uses Compustat ib.",
        fontsize=8.5,
    )
    fig.tight_layout(rect=(0, 0.06, 1, 0.98))
    return fig


def table1_window(df: pd.DataFrame, start: int, end: int) -> dict[str, pd.DataFrame]:
    firm = firm_period_counts(df, start, end)
    window_firm = firm[firm["main_sample_entry"]].copy()
    window_firm["div_bucket"] = window_firm["div_years"].map(div_bucket_table1)
    window_firm["rep_bucket"] = window_firm["rep_years"].map(rep_bucket_table1)
    div_order = ["0", "1-4", "5-9", "10"]
    rep_order = ["0", "1-4", "5+"]

    count = pd.crosstab(window_firm["rep_bucket"], window_firm["div_bucket"]).reindex(
        index=rep_order, columns=div_order, fill_value=0
    )
    payout = (
        window_firm.pivot_table(
            index="rep_bucket",
            columns="div_bucket",
            values="total_payout",
            aggfunc=sum_observed,
            fill_value=0,
        )
        .reindex(index=rep_order, columns=div_order, fill_value=0)
    )
    count_frac = count / count.values.sum()
    payout_frac = payout / payout.values.sum()

    count_display = count.copy().astype(str)
    payout_display = payout.copy().astype(str)
    for r in count.index:
        for c in count.columns:
            count_display.loc[r, c] = f"{fmt_int(count.loc[r, c])}\n({fmt_pct(count_frac.loc[r, c])})"
            payout_display.loc[r, c] = f"{fmt_money(payout.loc[r, c])}\n({fmt_pct(payout_frac.loc[r, c])})"

    count_raw = count.copy()
    payout_raw = payout.copy()
    count_raw.to_csv(TABLE_DIR / f"table1_counts_{start}_{end}.csv")
    payout_raw.to_csv(TABLE_DIR / f"table1_payouts_{start}_{end}.csv")
    return {
        "count_display": count_display,
        "payout_display": payout_display,
        "count_raw": count_raw,
        "payout_raw": payout_raw,
        "firm": firm,
        "classifiable_firm": window_firm,
        "window_firm": window_firm,
    }


def add_sum_margins(table: pd.DataFrame) -> pd.DataFrame:
    out = table.copy()
    out["Sum"] = out.sum(axis=1)
    out.loc["Sum"] = out.sum(axis=0)
    return out


def build_table1_combined(table1: dict[tuple[int, int], dict[str, pd.DataFrame]]) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    columns = ["0", "1-4", "5-9", "10", "Sum"]
    rep_order = ["0", "1-4", "5+", "Sum"]

    for (start, end), data in table1.items():
        count = add_sum_margins(data["count_raw"]).reindex(index=rep_order, columns=columns)
        payout = add_sum_margins(data["payout_raw"]).reindex(index=rep_order, columns=columns)
        count_total = float(count.loc["Sum", "Sum"])
        payout_total = float(payout.loc["Sum", "Sum"])
        count_frac = count / count_total if count_total else count * np.nan
        payout_frac = payout / payout_total if payout_total else payout * np.nan

        for rep_bucket in rep_order:
            row: dict[str, str] = {}
            row_label = f"{start}-{end} | {rep_bucket}"
            for div_bucket in columns:
                row[div_bucket] = (
                    f"{fmt_int(count.loc[rep_bucket, div_bucket])} / {fmt_money(payout.loc[rep_bucket, div_bucket])}"
                    f"\n({fmt_pct(count_frac.loc[rep_bucket, div_bucket])}; {fmt_pct(payout_frac.loc[rep_bucket, div_bucket])})"
                )
            rows.append({"row_label": row_label, **row})

    combined = pd.DataFrame(rows).set_index("row_label")
    combined.to_csv(TABLE_DIR / "table1_combined_counts_payouts.csv")
    return combined


def build_table1_paper_panels(table1: dict[tuple[int, int], dict[str, pd.DataFrame]]) -> tuple[pd.DataFrame, pd.DataFrame]:
    columns = ["0", "1-4", "5-9", "10", "Sum"]
    rep_order = ["0", "1-4", "5+", "Sum"]
    rep_display = {"0": "0", "1-4": "1-4", "5+": "5-10", "Sum": "Sum"}

    count_rows: list[dict[str, str]] = []
    payout_rows: list[dict[str, str]] = []
    for (start, end), data in table1.items():
        count = add_sum_margins(data["count_raw"]).reindex(index=rep_order, columns=columns)
        payout = add_sum_margins(data["payout_raw"]).reindex(index=rep_order, columns=columns)
        count_total = float(count.loc["Sum", "Sum"])
        payout_total = float(payout.loc["Sum", "Sum"])
        count_frac = count / count_total if count_total else count * np.nan
        payout_frac = payout / payout_total if payout_total else payout * np.nan

        for i, rep_bucket in enumerate(rep_order):
            row_label = f"{start}-{end}\n{rep_display[rep_bucket]}" if i == 0 else rep_display[rep_bucket]
            count_row = {"row_label": row_label}
            payout_row = {"row_label": row_label}
            for div_bucket in columns:
                count_row[div_bucket] = f"{fmt_int(count.loc[rep_bucket, div_bucket])}\n({fmt_frac(count_frac.loc[rep_bucket, div_bucket])})"
                payout_row[div_bucket] = f"{fmt_money(payout.loc[rep_bucket, div_bucket])}\n({fmt_frac(payout_frac.loc[rep_bucket, div_bucket])})"
            count_rows.append(count_row)
            payout_rows.append(payout_row)

    count_panel = pd.DataFrame(count_rows).set_index("row_label")
    payout_panel = pd.DataFrame(payout_rows).set_index("row_label")
    count_panel.to_csv(TABLE_DIR / "table1_panel_a_counts_display.csv")
    payout_panel.to_csv(TABLE_DIR / "table1_panel_b_payouts_display.csv")
    return count_panel, payout_panel


def build_table2(firm_groups: pd.DataFrame) -> pd.DataFrame:
    order = ["0", "1-5", "6-10", "11-15", "16-20", ">20"]
    table2_firms = firm_groups[firm_groups["main_sample_entry"]].copy()
    tab = pd.crosstab(table2_firms["rep_bucket_t2"], table2_firms["div_bucket_t2"]).reindex(
        index=order, columns=order, fill_value=0
    )
    tab["Sum"] = tab.sum(axis=1)
    total_row = tab.sum(axis=0).to_frame().T
    total_row.index = ["Sum"]
    tab = pd.concat([tab, total_row])
    tab.to_csv(TABLE_DIR / "table2_counts_1980_2005.csv")
    return tab


def build_sample_audit_table(summary: dict[str, float], df: pd.DataFrame) -> pd.DataFrame:
    sample_1970 = df[(df["fyear"] >= 1970) & (df["fyear"] <= 2005)]
    sample_1980 = df[(df["fyear"] >= 1980) & (df["fyear"] <= 2005)]
    rows = [
        (
            "Merged raw data",
            summary["raw_rows"],
            summary["raw_firms"],
            "Observations after merging 2.csv and ajex.csv by gvkey and datadate.",
        ),
        (
            "After WRDS format screen",
            summary["wrds_rows"],
            summary["wrds_firms"],
            "Keep consol=C, indfmt=INDL, datafmt=STD, and curcd=USD.",
        ),
        (
            "US-incorporated firms",
            summary["usa_rows"],
            summary["usa_firms"],
            "Keep fic=USA.",
        ),
        (
            "After industry screen",
            summary["clean_rows_before_year"],
            summary["clean_firms_before_year"],
            "Use sich first and sic as fallback for sic_use; exclude financial SIC 6000-6999 and utility SIC 4900-4999.",
        ),
        (
            "After CRSP/CCM stock screen",
            summary["crsp_ccm_screened_rows"],
            summary["crsp_ccm_screened_firms"],
            "Keep valid CCM LC/LU/LS links with LINKPRIM P/C and CRSP common shares SHRCD 10/11 on NYSE/AMEX/NASDAQ EXCHCD 1/2/3.",
        ),
        (
            "sic_use from sich",
            summary["sic_use_from_sich_rows"],
            np.nan,
            "Diagnostic count of firm-years whose industry screen uses historical SIC sich.",
        ),
        (
            "sic_use from sic",
            summary["sic_use_from_sic_rows"],
            np.nan,
            "Diagnostic count of firm-years whose industry screen uses sic fallback.",
        ),
        (
            "Excluded by sic_use screen",
            summary["industry_excluded_rows"],
            summary["industry_excluded_firms"],
            f"Financial firm-years: {summary['industry_excluded_financial_rows']:,.0f}; utility firm-years: {summary['industry_excluded_utility_rows']:,.0f}.",
        ),
        (
            "Both sic and sich missing",
            summary["sic_sich_missing_rows"],
            summary["sic_sich_missing_firms"],
            "Diagnostic count; observations are retained but separately reported.",
        ),
        (
            "1970-2005 sample",
            len(sample_1970),
            sample_1970["gvkey"].nunique(),
            "Used for Figure 1.",
        ),
        (
            "1980-2005 sample",
            len(sample_1980),
            sample_1980["gvkey"].nunique(),
            "Used for Table 2, Figure 2, Figure 3, and Table 3 grouping.",
        ),
    ]
    out = pd.DataFrame(rows, columns=["stage", "firm_years", "firms", "note"]).set_index("stage")
    out["firm_years"] = out["firm_years"].map(fmt_int)
    out["firms"] = out["firms"].map(fmt_int)
    out.to_csv(TABLE_DIR / "sample_audit.csv")
    return out


def build_group_diagnostics(df: pd.DataFrame, firm_groups: pd.DataFrame) -> pd.DataFrame:
    sample = df[(df["fyear"] >= 1980) & (df["fyear"] <= 2005) & df["group_id"].isin([1, 2, 3, 4, 5])].copy()
    rows: list[dict[str, object]] = []
    for gid in [1, 2, 3, 4, 5]:
        g = sample[sample["group_id"] == gid]
        g_1995 = g[(g["fyear"] >= 1995) & (g["fyear"] <= 2005)]
        current_firms = int((firm_groups["group_id"] == gid).sum())
        published_firms = PUBLISHED_GROUP_COUNTS[gid]
        rows.append(
            {
                "group": GROUP_NAMES_CN[gid],
                "published_firms": published_firms,
                "current_firms": current_firms,
                "difference": current_firms - published_firms,
                "firm_years": len(g),
                "earnings_sum": sum_observed(g["earnings"]),
                "dividend_sum": sum_observed(g["dividend"]),
                "repurchase_sum": sum_observed(g["repurchase"]),
                "loss_rate": g["loss"].mean(),
                "roa_median": g["roa"].median(),
                "cash_median": g["cash"].median(),
                "past_stock_return_median": g["past_stock_return"].median(),
                "eso_coverage": g_1995["eso_dilution"].notna().mean(),
            }
        )
    out = pd.DataFrame(rows).set_index("group")
    display = out.copy()
    for col in ["published_firms", "current_firms", "difference", "firm_years", "earnings_sum", "dividend_sum", "repurchase_sum"]:
        display[col] = display[col].map(fmt_int)
    for col in ["loss_rate", "eso_coverage"]:
        display[col] = display[col].map(fmt_pct)
    for col in ["roa_median", "cash_median", "past_stock_return_median"]:
        display[col] = display[col].map(lambda x: "" if pd.isna(x) else f"{x:.3f}")
    out.to_csv(TABLE_DIR / "group_diagnostics_raw.csv")
    display.to_csv(TABLE_DIR / "group_diagnostics_display.csv")
    return display


def build_figure2(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    panel_a, panel_b = figure2_source_data(df)
    panel_a.to_csv(TABLE_DIR / "figure2_panel_a_earnings.csv", index=False)
    panel_b.to_csv(TABLE_DIR / "figure2_panel_b_earnings.csv", index=False)
    return panel_a, panel_b


def figure2_source_data(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    sample = df[(df["fyear"] >= 1980) & (df["fyear"] <= 2005)].copy()
    all_earnings = sample.groupby("fyear")["adjusted_earnings"].apply(sum_observed).rename("All industrials").reset_index()
    group2 = (
        sample[sample["group_id"] == 2]
        .groupby("fyear")["adjusted_earnings"]
        .apply(sum_observed)
        .rename("Regular div. + regular rep.")
        .reset_index()
    )
    panel_a = all_earnings.merge(group2, on="fyear", how="left")
    panel_a["Regular div. + regular rep."] = panel_a["Regular div. + regular rep."].fillna(0)

    wanted = [1, 3, 4, 5]
    panel_b = (
        sample[sample["group_id"].isin(wanted)]
        .groupby(["fyear", "group_name"])["adjusted_earnings"]
        .apply(sum_observed)
        .reset_index()
        .rename(columns={"adjusted_earnings": "earnings"})
    )
    return panel_a, panel_b


def plot_figure2(panel_a: pd.DataFrame, panel_b: pd.DataFrame) -> plt.Figure:
    fig, axes = plt.subplots(2, 1, figsize=PAGE, gridspec_kw={"height_ratios": [1.0, 1.0]})
    ax = axes[0]
    ax.plot(panel_a["fyear"], panel_a["All industrials"], color=COLOR_EARNINGS, lw=2.2, ls="--", label="All industrials")
    ax.plot(
        panel_a["fyear"],
        panel_a["Regular div. + regular rep."],
        color=COLOR_REPURCHASES,
        lw=2.0,
        label="Group II",
    )
    place_xaxis_at_zero(ax)
    ax.set_xlim(1980, 2005)
    ax.set_ylim(0, 600000)
    ax.margins(x=0)
    ax.set_title("Panel A: All industrials and Group II")
    ax.set_xlabel("Fiscal year")
    ax.set_ylabel("$ millions")
    ax.yaxis.set_major_formatter(FuncFormatter(fmt_millions_axis))
    ax.grid(axis="y", color=GRID_COLOR, lw=0.6)
    ax.legend(frameon=False, loc="upper left")

    ax = axes[1]
    styles = {
        "Non-payers": ("#7f7f7f", "-"),
        "Occasional rep. only": ("#9467bd", "--"),
        "Regular rep. only": ("#ff7f0e", "-"),
        "Dividend-only regular": ("#2ca02c", ":"),
    }
    legend_labels = {
        "Non-payers": "Group I: Non-payers",
        "Occasional rep. only": "Group III: Occasional rep.",
        "Regular rep. only": "Group IV: Regular rep.",
        "Dividend-only regular": "Group V: Dividend only",
    }
    plotted = False
    for name, g in panel_b.groupby("group_name"):
        color, ls = styles.get(name, ("black", "-"))
        ax.plot(g["fyear"], g["earnings"], color=color, lw=1.9, ls=ls, label=legend_labels.get(name, name))
        plotted = True
    if not plotted:
        y_min = min(0.0, float(panel_a["All industrials"].min(skipna=True)) * 1.05)
        y_max = max(1.0, float(panel_a["All industrials"].max(skipna=True)) * 1.05)
        ax.set_xlim(1980, 2005)
        ax.set_ylim(y_min, y_max)
        ax.text(
            0.5,
            0.52,
            "No plottable Group I, III, IV, or V observations under the current classification.",
            transform=ax.transAxes,
            ha="center",
            va="center",
            fontsize=9,
            color="#555555",
        )
    place_xaxis_at_zero(ax)
    ax.set_xlim(1980, 2005)
    ax.set_ylim(-80000, 40000)
    ax.margins(x=0)
    ax.set_title("Panel B: Other long-run payout groups")
    ax.set_xlabel("Fiscal year")
    ax.set_ylabel("$ millions")
    ax.yaxis.set_major_formatter(FuncFormatter(fmt_millions_axis))
    ax.grid(axis="y", color=GRID_COLOR, lw=0.6)
    if plotted:
        ax.legend(frameon=False, loc="best", fontsize=8)

    fig.suptitle("Figure 2  Earnings by long-run payout group, 1980-2005", y=0.98, fontsize=13)
    fig.text(
        0.07,
        0.03,
        "Notes: Figure 2 uses the CRSP/CCM-screened Compustat sample. Earnings are ib - 0.6 x spi, with missing spi set to zero.",
        fontsize=8.5,
    )
    fig.tight_layout(rect=(0, 0.06, 1, 0.94), h_pad=2.0)
    return fig


def build_figure3(df: pd.DataFrame) -> pd.DataFrame:
    sample = df[(df["fyear"] >= 1980) & (df["fyear"] <= 2005) & (df["group_id"].isin([1, 2, 3, 4, 5]))].copy()
    loss = (
        sample.groupby(["fyear", "group_name"])["loss"]
        .mean()
        .reset_index()
        .rename(columns={"loss": "loss_fraction"})
    )
    loss.to_csv(TABLE_DIR / "figure3_loss_fractions.csv", index=False)
    return loss


def plot_figure3(loss: pd.DataFrame) -> plt.Figure:
    fig, ax = plt.subplots(figsize=PAGE)
    styles = {
        "Regular div. + regular rep.": ("#d62728", "-"),
        "Dividend-only regular": ("#2ca02c", ":"),
        "Occasional rep. only": ("#9467bd", "--"),
        "Regular rep. only": ("#ff7f0e", "-."),
        "Non-payers": ("#7f7f7f", "-"),
    }
    order = [
        "Regular div. + regular rep.",
        "Dividend-only regular",
        "Occasional rep. only",
        "Regular rep. only",
        "Non-payers",
    ]
    legend_labels = {
        "Regular div. + regular rep.": "Group II: Both",
        "Dividend-only regular": "Group V: Div only",
        "Occasional rep. only": "Group III: Occ. rep.",
        "Regular rep. only": "Group IV: Reg. rep.",
        "Non-payers": "Group I: Non-payers",
    }
    plotted = False
    for name in order:
        g = loss[loss["group_name"] == name]
        if g.empty:
            continue
        color, ls = styles[name]
        ax.plot(g["fyear"], g["loss_fraction"], lw=2.0, color=color, ls=ls, label=legend_labels.get(name, name))
        plotted = True
    if not plotted:
        ax.set_xlim(1980, 2005)
        ax.text(
            0.5,
            0.52,
            "No plottable Group I-V loss-fraction observations under the current classification.",
            transform=ax.transAxes,
            ha="center",
            va="center",
            fontsize=10,
            color="#555555",
        )
    ax.set_xlim(1980, 2005)
    ax.set_ylim(0, 0.9)
    ax.margins(x=0)
    ax.set_title("Figure 3  Fraction of firms reporting losses by long-run payout group, 1980-2005")
    ax.set_xlabel("Fiscal year")
    ax.set_ylabel("Fraction of firms with negative Compustat earnings")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _pos: f"{x * 100:.0f}%"))
    ax.grid(axis="y", color=GRID_COLOR, lw=0.6)
    if plotted:
        ax.legend(frameon=False, loc="upper left", ncol=2)
    fig.text(
        0.08,
        0.03,
        "Notes: Losses are based on Compustat earnings. Groups are based on long-run payout behavior over 1980-2005.",
        fontsize=8.5,
    )
    fig.tight_layout(rect=(0, 0.06, 1, 0.98))
    return fig


# ---------------------------------------------------------------------------
# Table 3: Stata input artifacts
# ---------------------------------------------------------------------------


def build_table3_data(df: pd.DataFrame) -> pd.DataFrame:
    sample = df[(df["fyear"] >= 1980) & (df["fyear"] <= 2005) & (df["group_id"].isin([2, 3, 4]))].copy()
    cols = [
        "gvkey",
        "fyear",
        "group_id",
        "repurchase_dummy",
        "regular_dummy",
        "roa",
        "roa_regular",
        "past_stock_return",
        "cash",
        "eso_dilution",
    ]
    reg = sample[cols].replace([np.inf, -np.inf], np.nan).copy()
    reg["group_id"] = reg["group_id"].astype(int)
    valid_y = reg["repurchase_dummy"].isin([0, 1])
    reg["sample_A_1980_1994"] = (
        reg["group_id"].eq(2)
        & reg["fyear"].between(1980, 1994)
        & valid_y
        & reg[["roa", "past_stock_return", "cash"]].notna().all(axis=1)
    ).astype(int)
    reg["sample_A_1995_2005"] = (
        reg["group_id"].eq(2)
        & reg["fyear"].between(1995, 2005)
        & valid_y
        & reg[["roa", "past_stock_return", "cash"]].notna().all(axis=1)
    ).astype(int)
    reg["sample_A_1995_2005_eso"] = (
        reg["group_id"].eq(2)
        & reg["fyear"].between(1995, 2005)
        & valid_y
        & reg[["roa", "past_stock_return", "cash", "eso_dilution"]].notna().all(axis=1)
    ).astype(int)
    reg["sample_B_1980_1994"] = (
        reg["group_id"].isin([3, 4])
        & reg["fyear"].between(1980, 1994)
        & valid_y
        & reg[["regular_dummy", "roa", "roa_regular", "past_stock_return", "cash"]].notna().all(axis=1)
    ).astype(int)
    reg["sample_B_1995_2005"] = (
        reg["group_id"].isin([3, 4])
        & reg["fyear"].between(1995, 2005)
        & valid_y
        & reg[["regular_dummy", "roa", "roa_regular", "past_stock_return", "cash"]].notna().all(axis=1)
    ).astype(int)
    reg["sample_B_1995_2005_eso"] = (
        reg["group_id"].isin([3, 4])
        & reg["fyear"].between(1995, 2005)
        & valid_y
        & reg[["regular_dummy", "roa", "roa_regular", "past_stock_return", "cash", "eso_dilution"]].notna().all(axis=1)
    ).astype(int)
    reg.to_csv(STATA_DIR / "table3_regression_data.csv", index=False)
    try:
        reg.to_stata(STATA_DIR / "table3_regression_data.dta", write_index=False, version=118)
    except Exception as exc:
        print(f"Warning: could not export Stata .dta file: {exc}")
    return reg


def stata_do_code(stata_dir: Path = STATA_DIR) -> str:
    dta_path = (stata_dir / "table3_regression_data.dta").as_posix()
    results_path = (stata_dir / "table3_stata_results.dta").as_posix()
    csv_path = (stata_dir / "table3_stata_results.csv").as_posix()
    log_path = (stata_dir / "table3_stata.log").as_posix()
    return f"""
clear all
set more off
capture log close
log using "{log_path}", replace text
use "{dta_path}", clear

capture postclose results
postfile results str8 panel str16 model str24 term double coef se p pseudo_r2 N y1 y0 using "{results_path}", replace

program define post_one_model
    syntax, Panel(string) Model(string) Terms(string)
    local r2 = e(r2_p)
    local n = e(N)
    quietly summarize repurchase_dummy if e(sample), meanonly
    local y1 = r(sum)
    local y0 = `n' - `y1'
    foreach t of local terms {{
        local b = .
        local s = .
        local p = .
        capture local b = _b[`t']
        if _rc == 0 {{
            capture local s = _se[`t']
            if _rc == 0 {{
                local p = 2 * normal(-abs(`b' / `s'))
            }}
        }}
        post results ("`panel'") ("`model'") ("`t'") (`b') (`s') (`p') (`r2') (`n') (`y1') (`y0')
    }}
end

local terms_a "_cons roa past_stock_return cash eso_dilution"
local terms_b "_cons regular_dummy roa roa_regular past_stock_return cash eso_dilution"

quietly logit repurchase_dummy roa past_stock_return cash if sample_A_1980_1994 == 1
post_one_model, panel("Panel A") model("1980-1994") terms("`terms_a'")

quietly logit repurchase_dummy roa past_stock_return cash if sample_A_1995_2005 == 1
post_one_model, panel("Panel A") model("1995-2005") terms("`terms_a'")

quietly logit repurchase_dummy roa past_stock_return cash eso_dilution if sample_A_1995_2005_eso == 1
post_one_model, panel("Panel A") model("1995-2005 ESO") terms("`terms_a'")

quietly logit repurchase_dummy regular_dummy roa roa_regular past_stock_return cash if sample_B_1980_1994 == 1
post_one_model, panel("Panel B") model("1980-1994") terms("`terms_b'")

quietly logit repurchase_dummy regular_dummy roa roa_regular past_stock_return cash if sample_B_1995_2005 == 1
post_one_model, panel("Panel B") model("1995-2005") terms("`terms_b'")

quietly logit repurchase_dummy regular_dummy roa roa_regular past_stock_return cash eso_dilution if sample_B_1995_2005_eso == 1
post_one_model, panel("Panel B") model("1995-2005 ESO") terms("`terms_b'")

postclose results
use "{results_path}", clear
export delimited using "{csv_path}", replace
log close
""".strip()


def prepare_logit_sample(data: pd.DataFrame, required_cols: list[str]) -> pd.DataFrame:
    return data[required_cols].replace([np.inf, -np.inf], np.nan).dropna().copy()


def table3_terms() -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    terms_a = [
        ("const", "Intercept"),
        ("roa", "ROA"),
        ("past_stock_return", "Past stock return"),
        ("cash", "Cash"),
        ("eso_dilution", "ESO dilution"),
    ]
    terms_b = [
        ("const", "Intercept"),
        ("regular_dummy", "Regular dummy"),
        ("roa", "ROA"),
        ("roa_regular", "ROA x Regular"),
        ("past_stock_return", "Past stock return"),
        ("cash", "Cash"),
        ("eso_dilution", "ESO dilution"),
    ]
    return terms_a, terms_b


def table3_model_specs(reg: pd.DataFrame) -> list[tuple[str, str, pd.DataFrame, list[str], list[tuple[str, str]]]]:
    terms_a, terms_b = table3_terms()
    specs = [
        ("Panel A", "1980-1994", reg[reg["sample_A_1980_1994"].eq(1)], ["roa", "past_stock_return", "cash"], terms_a),
        ("Panel A", "1995-2005", reg[reg["sample_A_1995_2005"].eq(1)], ["roa", "past_stock_return", "cash"], terms_a),
        (
            "Panel A",
            "1995-2005 ESO",
            reg[reg["sample_A_1995_2005_eso"].eq(1)],
            ["roa", "past_stock_return", "cash", "eso_dilution"],
            terms_a,
        ),
        (
            "Panel B",
            "1980-1994",
            reg[reg["sample_B_1980_1994"].eq(1)],
            ["regular_dummy", "roa", "roa_regular", "past_stock_return", "cash"],
            terms_b,
        ),
        (
            "Panel B",
            "1995-2005",
            reg[reg["sample_B_1995_2005"].eq(1)],
            ["regular_dummy", "roa", "roa_regular", "past_stock_return", "cash"],
            terms_b,
        ),
        (
            "Panel B",
            "1995-2005 ESO",
            reg[reg["sample_B_1995_2005_eso"].eq(1)],
            ["regular_dummy", "roa", "roa_regular", "past_stock_return", "cash", "eso_dilution"],
            terms_b,
        ),
    ]
    return specs


def table3_all_models_estimable(reg: pd.DataFrame) -> bool:
    for _panel, _model_label, data, xvars, _display_terms in table3_model_specs(reg):
        complete = prepare_logit_sample(data, ["repurchase_dummy"] + xvars)
        complete = complete[complete["repurchase_dummy"].isin([0, 1])]
        if len(complete) == 0 or complete["repurchase_dummy"].nunique() < 2:
            return False
    return True


def table3_python_sample_audit(reg: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for panel, model_label, data, xvars, _display_terms in table3_model_specs(reg):
        complete = prepare_logit_sample(data, ["repurchase_dummy"] + xvars)
        complete = complete[complete["repurchase_dummy"].isin([0, 1])]
        rows.append(
            {
                "panel": panel,
                "model": model_label,
                "python_N": int(len(complete)),
                "python_y1": int(complete["repurchase_dummy"].sum()) if len(complete) else 0,
                "python_y0": int(len(complete) - complete["repurchase_dummy"].sum()) if len(complete) else 0,
            }
        )
    return pd.DataFrame(rows)


def write_cleaning_qa_outputs(
    df: pd.DataFrame,
    firm_groups: pd.DataFrame,
    table1: dict[tuple[int, int], dict[str, pd.DataFrame]],
    table2: pd.DataFrame,
    reg: pd.DataFrame,
) -> None:
    raw_missing = (
        df.groupby("fyear")
        .agg(
            rows=("gvkey", "size"),
            dvc_missing_rate=("dvc", lambda x: x.isna().mean()),
            tstkc_missing_rate=("tstkc", lambda x: x.isna().mean()),
            prstkc_missing_rate=("prstkc", lambda x: x.isna().mean()),
            sstk_missing_rate=("sstk", lambda x: x.isna().mean()),
        )
        .reset_index()
    )
    raw_missing.to_csv(TABLE_DIR / "qa_raw_payout_field_missing_rates_by_year.csv", index=False)

    rep_source = pd.crosstab(df["fyear"], df["repurchase_source"].fillna("unassigned"))
    rep_source.to_csv(TABLE_DIR / "qa_repurchase_source_counts_by_year.csv")

    retirement_method = df["tstkc"].notna() & df["tstkc_lag1"].notna() & df["tstkc"].eq(0) & df["tstkc_lag1"].eq(0)
    rep_reasons = pd.DataFrame(
        {
            "fyear": df["fyear"],
            "no_exact_fyear_minus_1_tstkc": (~df["has_tstkc_lag1_row"]).astype(int),
            "current_tstkc_missing": df["tstkc"].isna().astype(int),
            "lag_tstkc_missing": (df["has_tstkc_lag1_row"] & df["tstkc_lag1"].isna()).astype(int),
            "retirement_prstkc_missing": (retirement_method & df["prstkc"].isna()).astype(int),
            "retirement_sstk_missing": (retirement_method & df["sstk"].isna()).astype(int),
            "retirement_both_cashflow_missing": (retirement_method & df["prstkc"].isna() & df["sstk"].isna()).astype(int),
        }
    )
    rep_reasons.groupby("fyear").sum().to_csv(TABLE_DIR / "qa_repurchase_missing_reason_counts_by_year.csv")

    industry_screen = pd.DataFrame(
        [
            {
                "sic_use_from_sich_rows": int(df["sich"].notna().sum()),
                "sic_use_from_sic_rows": int((df["sich"].isna() & df["sic"].notna()).sum()),
                "sic_use_missing_rows": int((df["sich"].isna() & df["sic"].isna()).sum()),
                "financial_rows_by_sic_use_after_screen": int(df["is_financial"].sum()) if "is_financial" in df else 0,
                "utility_rows_by_sic_use_after_screen": int(df["is_utility"].sum()) if "is_utility" in df else 0,
            }
        ]
    )
    industry_screen.to_csv(TABLE_DIR / "qa_sic_use_industry_screen.csv", index=False)

    classification_rows: list[dict[str, object]] = []
    for (start, end), data in table1.items():
        firm = data["firm"]
        classification_rows.append(
            {
                "sample": f"Table 1 {start}-{end}",
                "total_firms": len(firm),
                "window_entry_firms": int(firm["main_sample_entry"].sum()),
                "firms_not_entering_window": int((~firm["main_sample_entry"]).sum()),
                "firms_with_complete_payout_status": int(firm["payout_status_complete"].sum()),
                "firms_with_dividend_status_missing": int((firm["div_missing_years"] > 0).sum()),
                "firms_with_repurchase_status_missing": int((firm["rep_missing_years"] > 0).sum()),
            }
        )
    classification_rows.append(
        {
            "sample": "Table 2 1980-2005",
            "total_firms": len(firm_groups),
            "window_entry_firms": int(firm_groups["main_sample_entry"].sum()),
            "firms_not_entering_window": int((~firm_groups["main_sample_entry"]).sum()),
            "firms_with_complete_payout_status": int(firm_groups["payout_status_complete"].sum()),
            "firms_with_dividend_status_missing": int((firm_groups["div_missing_years"] > 0).sum()),
            "firms_with_repurchase_status_missing": int((firm_groups["rep_missing_years"] > 0).sum()),
        }
    )
    pd.DataFrame(classification_rows).to_csv(TABLE_DIR / "qa_payout_classification_audit.csv", index=False)

    table_comparison_rows: list[dict[str, object]] = []
    for window, published_total in PUBLISHED_TABLE1_TOTALS.items():
        current_total = int(table1[window]["count_raw"].values.sum())
        table_comparison_rows.append(
            {
                "item": f"Table 1 {window[0]}-{window[1]} window-entry firms",
                "current": current_total,
                "published": published_total,
                "difference": current_total - published_total,
            }
        )
    table_comparison_rows.extend(
        [
            {
                "item": "Table 2 total firms",
                "current": int(table2.loc["Sum", "Sum"]),
                "published": PUBLISHED_TABLE2_TOTAL,
                "difference": int(table2.loc["Sum", "Sum"]) - PUBLISHED_TABLE2_TOTAL,
            },
            {
                "item": "Table 2 zero-dividend column",
                "current": int(table2.loc["Sum", "0"]),
                "published": PUBLISHED_TABLE2_ZERO_DIV_COLUMN,
                "difference": int(table2.loc["Sum", "0"]) - PUBLISHED_TABLE2_ZERO_DIV_COLUMN,
            },
        ]
    )
    for gid, published_count in PUBLISHED_GROUP_COUNTS.items():
        current_count = int((firm_groups["group_id"] == gid).sum())
        table_comparison_rows.append(
            {
                "item": f"Group {gid} firms",
                "current": current_count,
                "published": published_count,
                "difference": current_count - published_count,
            }
        )
    pd.DataFrame(table_comparison_rows).to_csv(TABLE_DIR / "qa_published_count_comparison.csv", index=False)

    coverage = (
        df.groupby("fyear")
        .agg(
            rows=("gvkey", "size"),
            roa_nonmissing_rate=("roa", lambda x: x.notna().mean()),
            cash_nonmissing_rate=("cash", lambda x: x.notna().mean()),
            adjusted_price_nonmissing_rate=("adjusted_price", lambda x: x.notna().mean()),
            past_stock_return_nonmissing_rate=("past_stock_return", lambda x: x.notna().mean()),
            eso_dilution_nonmissing_rate=("eso_dilution", lambda x: x.notna().mean()),
            repurchase_dummy_nonmissing_rate=("repurchase_dummy", lambda x: x.notna().mean()),
        )
        .reset_index()
    )
    coverage.to_csv(TABLE_DIR / "qa_table3_variable_coverage_by_year.csv", index=False)

    denominator_checks = pd.DataFrame(
        [
            {
                "no_exact_fyear_minus_1_for_roa": int((~df["has_at_lag1_row"]).sum()),
                "no_exact_fyear_minus_3_for_past_return": int((~df["has_adjusted_price_lag3_row"]).sum()),
                "at_lag1_nonpositive": int(df["at_lag1"].le(0).sum()),
                "at_nonpositive": int(df["at"].le(0).sum()),
                "sale_nonpositive": int(df["sale"].le(0).sum()),
                "ajex_nonpositive": int(df["ajex"].le(0).sum()),
                "adjusted_price_lag3_nonpositive": int(df["adjusted_price_lag3"].le(0).sum()),
                "prcc_f_nonpositive": int(df["prcc_f"].le(0).sum()),
            }
        ]
    )
    denominator_checks.to_csv(TABLE_DIR / "qa_table3_denominator_and_lag_checks.csv", index=False)

    reg_sample_rows = []
    for panel, model_label, data, xvars, _display_terms in table3_model_specs(reg):
        required = ["repurchase_dummy"] + xvars
        complete = prepare_logit_sample(data, required)
        complete = complete[complete["repurchase_dummy"].isin([0, 1])]
        published_n = PUBLISHED_TABLE3_N[(panel, model_label)]
        reg_sample_rows.append(
            {
                "panel": panel,
                "model": model_label,
                "current_N": len(complete),
                "published_N": published_n,
                "difference": len(complete) - published_n,
                "required_columns": ", ".join(required),
            }
        )
    pd.DataFrame(reg_sample_rows).to_csv(TABLE_DIR / "qa_table3_regression_sample_counts.csv", index=False)


# ---------------------------------------------------------------------------
# Figure export
# ---------------------------------------------------------------------------


def save_fig(fig: plt.Figure, name: str) -> Path:
    png_path = FIG_DIR / f"{name}.png"
    pdf_path = FIG_DIR / f"{name}.pdf"
    try:
        fig.savefig(png_path, bbox_inches="tight")
    except PermissionError:
        for i in range(1, 20):
            alt_png = FIG_DIR / f"{name}_report_{i}.png"
            try:
                fig.savefig(alt_png, bbox_inches="tight")
                png_path = alt_png
                break
            except PermissionError:
                continue
        else:
            raise
    try:
        fig.savefig(pdf_path, bbox_inches="tight")
        return pdf_path
    except PermissionError:
        for i in range(1, 20):
            alt_pdf = FIG_DIR / f"{name}_report_{i}.pdf"
            try:
                fig.savefig(alt_pdf, bbox_inches="tight")
                return alt_pdf
            except PermissionError:
                continue
        return png_path


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------


def write_python_handoff_artifacts(
    clean: pd.DataFrame,
    firm_groups: pd.DataFrame,
    annual: pd.DataFrame,
    table1: dict[tuple[int, int], dict[str, pd.DataFrame]],
    table1_combined: pd.DataFrame,
    table1_panel_a: pd.DataFrame,
    table1_panel_b: pd.DataFrame,
    table2: pd.DataFrame,
    fig2a: pd.DataFrame,
    fig2b: pd.DataFrame,
    fig3: pd.DataFrame,
    reg: pd.DataFrame,
    sample_audit: pd.DataFrame,
    group_diagnostics: pd.DataFrame,
) -> None:
    analysis_cols = [
        "gvkey",
        "datadate",
        "fyear",
        "sic",
        "sich",
        "sic_use",
        "at",
        "ceq",
        "dvc",
        "dividend",
        "dividend_dummy",
        "repurchase",
        "repurchase_dummy",
        "repurchase_source",
        "total_payout",
        "ib",
        "special_items",
        "earnings",
        "adjusted_earnings",
        "loss",
        "group_id",
        "group_name",
        "roa",
        "cash",
        "past_stock_return",
        "eso_dilution",
    ]
    available_analysis_cols = [col for col in analysis_cols if col in clean.columns]
    analysis = clean.loc[clean["fyear"].between(1970, 2005), available_analysis_cols].copy()
    analysis.to_csv(OUTPUT_DIR / "clean_analysis_firm_years_1970_2005.csv", index=False)

    firm_groups.to_csv(OUTPUT_DIR / "firm_groups_1980_2005.csv", index=False)

    manifest_rows = [
        {"file": "clean_analysis_firm_years_1970_2005.csv", "purpose": "Clean firm-year analysis data for figures and checks."},
        {"file": "firm_groups_1980_2005.csv", "purpose": "Firm-level long-run payout classifications used by Figure 2, Figure 3, Table 2, and Table 3."},
        {"file": "tables/figure1_annual_aggregates.csv", "purpose": "Figure 1 plotting source data."},
        {"file": "tables/figure2_panel_a_earnings.csv", "purpose": "Figure 2 Panel A source data built from the CRSP/CCM-screened Compustat sample."},
        {"file": "tables/figure2_panel_b_earnings.csv", "purpose": "Figure 2 Panel B source data built from the CRSP/CCM-screened Compustat sample."},
        {"file": "tables/figure3_loss_fractions.csv", "purpose": "Figure 3 plotting source data."},
        {"file": "figures/figure1.png", "purpose": "Figure 1 rendered image for downstream assembly."},
        {"file": "figures/figure1.pdf", "purpose": "Figure 1 vector figure for downstream assembly."},
        {"file": "figures/figure2.png", "purpose": "Figure 2 rendered image for downstream assembly."},
        {"file": "figures/figure2.pdf", "purpose": "Figure 2 vector figure for downstream assembly."},
        {"file": "figures/figure3.png", "purpose": "Figure 3 rendered image for downstream assembly."},
        {"file": "figures/figure3.pdf", "purpose": "Figure 3 vector figure for downstream assembly."},
        {"file": "tables/table1_*", "purpose": "Table 1 counts, payouts, and display source panels."},
        {"file": "tables/table2_counts_1980_2005.csv", "purpose": "Table 2 source counts."},
        {"file": "stata/table3_regression_data.csv", "purpose": "Table 3 Stata regression input data."},
        {"file": "stata/table3_regression_data.dta", "purpose": "Table 3 Stata regression input data in Stata format."},
        {"file": "stata/table3_replication.do", "purpose": "Stata script for downstream Table 3 estimation."},
        {"file": "python_stage_artifacts.xlsx", "purpose": "Compact workbook of Python-stage CSV source artifacts."},
    ]
    pd.DataFrame(manifest_rows).to_csv(OUTPUT_DIR / "manifest.csv", index=False)

    workbook_path = OUTPUT_DIR / "python_stage_artifacts.xlsx"
    sheets: list[tuple[str, pd.DataFrame]] = [
        ("manifest", pd.DataFrame(manifest_rows)),
        ("figure1", annual),
        ("figure2_panel_a", fig2a),
        ("figure2_panel_b", fig2b),
        ("figure3", fig3),
        ("table1_combined", table1_combined.reset_index()),
        ("table1_panel_a", table1_panel_a.reset_index()),
        ("table1_panel_b", table1_panel_b.reset_index()),
        ("table2", table2.reset_index()),
        ("sample_audit", sample_audit.reset_index()),
        ("group_diagnostics", group_diagnostics.reset_index()),
        ("table3_data_preview", reg.head(5000)),
    ]
    for (start, end), data in table1.items():
        sheets.append((f"t1_counts_{start}_{end}", data["count_raw"].reset_index()))
        sheets.append((f"t1_payouts_{start}_{end}", data["payout_raw"].reset_index()))

    try:
        with pd.ExcelWriter(workbook_path) as writer:
            for sheet_name, frame in sheets:
                frame.to_excel(writer, sheet_name=sheet_name[:31], index=False)
    except Exception as exc:
        print(f"Warning: could not export Excel workbook {workbook_path}: {exc}")


def write_summary_file(
    summary: dict[str, float],
    df: pd.DataFrame,
    firm_groups: pd.DataFrame,
    table3_estimable: bool,
) -> None:
    lines = [
        "Skinner (2008) replication run summary",
        "====================================",
        f"Raw rows: {summary['raw_rows']:,.0f}",
        f"Raw firms: {summary['raw_firms']:,.0f}",
        f"ajex match rate: {summary['ajex_match_rate'] * 100:.2f}%",
        f"Rows after WRDS format screen: {summary['wrds_rows']:,.0f}",
        f"Firms after WRDS format screen: {summary['wrds_firms']:,.0f}",
        f"Rows after USA screen: {summary['usa_rows']:,.0f}",
        f"Firms after USA screen: {summary['usa_firms']:,.0f}",
        f"Rows using sich for sic_use before industry screen: {summary['sic_use_from_sich_rows']:,.0f}",
        f"Rows using sic fallback for sic_use before industry screen: {summary['sic_use_from_sic_rows']:,.0f}",
        f"Rows excluded by sic_use industry screen: {summary['industry_excluded_rows']:,.0f}",
        f"  Financial rows excluded: {summary['industry_excluded_financial_rows']:,.0f}",
        f"  Utility rows excluded: {summary['industry_excluded_utility_rows']:,.0f}",
        f"Firms excluded by sic_use industry screen: {summary['industry_excluded_firms']:,.0f}",
        f"Rows with both sic and sich missing after USA screen: {summary['sic_sich_missing_rows']:,.0f}",
        f"Firms with both sic and sich missing after USA screen: {summary['sic_sich_missing_firms']:,.0f}",
        f"Rows after US industrial screen: {summary['clean_rows_before_year']:,.0f}",
        f"Firms after US industrial screen: {summary['clean_firms_before_year']:,.0f}",
        f"CCM link rows used: {summary['ccm_link_rows_used']:,.0f}",
        f"CRSP name-history rows used after SHRCD/EXCHCD screen: {summary['crsp_name_rows_used']:,.0f}",
        f"Rows after valid CCM link-date screen: {summary['crsp_ccm_linked_rows']:,.0f}",
        f"Firms after valid CCM link-date screen: {summary['crsp_ccm_linked_firms']:,.0f}",
        f"Rows after CRSP common-share exchange screen: {summary['crsp_ccm_screened_rows']:,.0f}",
        f"Firms after CRSP common-share exchange screen: {summary['crsp_ccm_screened_firms']:,.0f}",
        f"Past stock return price rows after format screen: {summary['past_return_price_format_rows']:,.0f}",
        f"Past stock return price rows after industry screen: {summary['past_return_price_industry_rows']:,.0f}",
        f"Past stock return price rows after final price-source screen: {summary['past_return_price_final_rows']:,.0f}",
        f"Past stock return nonmissing adjusted-price rows in price source: {summary['past_return_price_adjusted_price_nonmissing']:,.0f}",
        f"Rows 1970-2005: {len(df[(df['fyear'] >= 1970) & (df['fyear'] <= 2005)]):,.0f}",
        f"Rows 1980-2005: {len(df[(df['fyear'] >= 1980) & (df['fyear'] <= 2005)]):,.0f}",
        "",
        "Long-run group counts over 1980-2005:",
    ]
    for gid, name in GROUP_NAMES.items():
        n = int((firm_groups["group_id"] == gid).sum())
        lines.append(f"  {gid}. {name}: {n:,.0f}")
    lines.append("")
    lines.append(f"All Table 3 models estimable: {table3_estimable}")
    lines.append("Stata automatically run: False")
    lines.append(f"Python handoff output: {OUTPUT_DIR}")
    lines.append("Final PDF/report generation is intentionally outside this Python worktree.")
    (OUTPUT_DIR / "run_summary.txt").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ensure_dirs()
    main_df, ajex_df, ccm_link, crsp_names, past_stock_prices = read_inputs()
    clean, summary = clean_and_construct(main_df, ajex_df, ccm_link, crsp_names, past_stock_prices)
    clean, firm_groups = add_long_run_groups(clean)

    annual = build_figure1(clean)
    table1 = {
        (1980, 1989): table1_window(clean, 1980, 1989),
        (1985, 1994): table1_window(clean, 1985, 1994),
        (1990, 1999): table1_window(clean, 1990, 1999),
        (1995, 2004): table1_window(clean, 1995, 2004),
    }
    table1_combined = build_table1_combined(table1)
    table1_panel_a, table1_panel_b = build_table1_paper_panels(table1)
    table2 = build_table2(firm_groups)
    fig2a, fig2b = build_figure2(clean)
    fig3 = build_figure3(clean)
    figure1 = plot_figure1(annual)
    save_fig(figure1, "figure1")
    plt.close(figure1)
    figure2 = plot_figure2(fig2a, fig2b)
    save_fig(figure2, "figure2")
    plt.close(figure2)
    figure3 = plot_figure3(fig3)
    save_fig(figure3, "figure3")
    plt.close(figure3)
    sample_audit = build_sample_audit_table(summary, clean)
    group_diagnostics = build_group_diagnostics(clean, firm_groups)

    reg = build_table3_data(clean)
    (STATA_DIR / "table3_replication.do").write_text(stata_do_code(), encoding="utf-8")
    write_cleaning_qa_outputs(clean, firm_groups, table1, table2, reg)
    table3_estimable = table3_all_models_estimable(reg)
    write_python_handoff_artifacts(
        clean,
        firm_groups,
        annual,
        table1,
        table1_combined,
        table1_panel_a,
        table1_panel_b,
        table2,
        fig2a,
        fig2b,
        fig3,
        reg,
        sample_audit,
        group_diagnostics,
    )
    write_summary_file(summary, clean, firm_groups, table3_estimable)
    print(f"Created Python-stage handoff artifacts under {OUTPUT_DIR}")
    print(f"Stata do-file exported to {STATA_DIR / 'table3_replication.do'}")
    if not table3_estimable:
        print("At least one Table 3 model has no estimable sample or one dependent-variable class.")
        print(f"See {TABLE_DIR / 'qa_table3_regression_sample_counts.csv'} for model-level sample counts.")


if __name__ == "__main__":
    main()
