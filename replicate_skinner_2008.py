from __future__ import annotations

import math
import os
import shutil
import subprocess
import tempfile
import textwrap
import time
from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

import statsmodels.api as sm


# ---------------------------------------------------------------------------
# User-facing configuration
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
MAIN_CSV = BASE_DIR / "2.csv"
AJEX_CSV = BASE_DIR / "ajex.csv"
REPORT_PDF = BASE_DIR / "report_skinner_2008.pdf"
OUTPUT_DIR = BASE_DIR / "skinner_2008_outputs"
REPORT_TEX = OUTPUT_DIR / "report_skinner_2008.tex"
ELEGANT_CLASS = BASE_DIR / "elegantpaper.cls"

# If Stata is installed but not on PATH, paste the executable path here, e.g.
# STATA_EXE = r"C:\Program Files\Stata18\StataMP-64.exe"
STATA_EXE = r"E:\downloading\stata\stata18\StataMP-64.exe"

RUN_STATA_IF_AVAILABLE = True


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
    1: "Group I: 不支付股利且不回购",
    2: "Group II: 经常支付股利且经常回购",
    3: "Group III: 仅偶尔回购",
    4: "Group IV: 仅经常回购",
    5: "Group V: 仅经常支付股利",
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


def sig_marker(p_value: float) -> str:
    if pd.isna(p_value):
        return ""
    if p_value < 0.01:
        return "*"
    if p_value < 0.05:
        return "^"
    return ""


def fmt_coef(coef: float, se: float, p_value: float) -> str:
    if pd.isna(coef):
        return ""
    return f"{coef:.2f}{sig_marker(p_value)}\n({se:.2f})"


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


def wrap_text(text: str, width: int = 105) -> str:
    return "\n".join(textwrap.wrap(text, width=width))


def sum_observed(series: pd.Series) -> float:
    return series.sum(min_count=1)


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


def read_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not MAIN_CSV.exists():
        raise FileNotFoundError(f"Missing main WRDS file: {MAIN_CSV}")
    if not AJEX_CSV.exists():
        raise FileNotFoundError(f"Missing adjustment-factor file: {AJEX_CSV}")

    main = pd.read_csv(MAIN_CSV, low_memory=False)
    ajex = pd.read_csv(AJEX_CSV, low_memory=False)

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
    missing_main = sorted(required_main - set(main.columns))
    missing_ajex = sorted(required_ajex - set(ajex.columns))
    if missing_main:
        raise ValueError(f"Main CSV is missing variables: {missing_main}")
    if missing_ajex:
        raise ValueError(f"ajex CSV is missing variables: {missing_ajex}")

    if main.duplicated(["gvkey", "datadate"]).any():
        raise ValueError("Main CSV has duplicated gvkey-datadate rows.")
    if ajex.duplicated(["gvkey", "datadate"]).any():
        raise ValueError("ajex CSV has duplicated gvkey-datadate rows.")
    return main, ajex


def clean_and_construct(main: pd.DataFrame, ajex: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float]]:
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

    df = df.sort_values(["gvkey", "fyear", "datadate"]).reset_index(drop=True)
    assert_unique_firm_year(df, "Clean Compustat sample")

    df["dividend"] = df["dvc"]
    df["dividend_dummy"] = np.select(
        [df["dvc"].gt(0), df["dvc"].eq(0)],
        [1.0, 0.0],
        default=np.nan,
    )
    df["special_items"] = df["spi"].fillna(0)
    df["earnings"] = df["ib"] - 0.6 * df["special_items"]

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
    cashflow_fallback = ~tstkc_pair_observed & cashflow_complete

    df["repurchase"] = np.nan
    df["repurchase_source"] = pd.Series(pd.NA, index=df.index, dtype="object")
    df.loc[treasury_method, "repurchase"] = df.loc[treasury_method, "tstkc"] - df.loc[treasury_method, "tstkc_lag1"]
    df.loc[treasury_method, "repurchase_source"] = "treasury_stock_change"
    df.loc[retirement_complete, "repurchase"] = (
        df.loc[retirement_complete, "prstkc"] - df.loc[retirement_complete, "sstk"]
    )
    df.loc[retirement_complete, "repurchase_source"] = "retirement_method"
    df.loc[cashflow_fallback, "repurchase"] = (
        df.loc[cashflow_fallback, "prstkc"] - df.loc[cashflow_fallback, "sstk"]
    )
    df.loc[cashflow_fallback, "repurchase_source"] = "cashflow_fallback"
    df.loc[retirement_method & ~cashflow_complete, "repurchase_source"] = "missing_cashflow_inputs"
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
    df["adjusted_price"] = np.where(
        df["prcc_f"].notna() & df["prcc_f"].gt(0) & df["ajex"].notna() & df["ajex"].gt(0),
        df["prcc_f"] / df["ajex"],
        np.nan,
    )
    price_lag = df[["gvkey", "fyear", "adjusted_price"]].copy()
    price_lag["fyear"] = price_lag["fyear"] + 3
    price_lag["has_adjusted_price_lag3_row"] = True
    price_lag = price_lag.rename(columns={"adjusted_price": "adjusted_price_lag3"})
    df = df.merge(price_lag, on=["gvkey", "fyear"], how="left", validate="one_to_one")
    df["has_adjusted_price_lag3_row"] = df["has_adjusted_price_lag3_row"].eq(True)
    df["past_stock_return"] = np.where(
        df["adjusted_price"].notna() & df["adjusted_price_lag3"].notna() & df["adjusted_price_lag3"].gt(0),
        df["adjusted_price"] / df["adjusted_price_lag3"] - 1,
        np.nan,
    )
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
        "clean_firms_before_year": int(df["gvkey"].nunique()),
        "firm_year_duplicate_rows_after_clean": 0,
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
    firm["main_sample_entry"] = firm["firm_years"].ge(1)
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
    ax.plot(annual["fyear"], annual["earnings"], color=COLOR_EARNINGS, lw=2.2, label="调整后收益")
    ax.plot(
        annual["fyear"],
        annual["special_items"],
        color=COLOR_SPECIAL,
        lw=1.8,
        ls=(0, (5, 2, 1, 2)),
        label="特殊项目",
    )
    ax.plot(annual["fyear"], annual["dividends"], color=COLOR_DIVIDENDS, lw=1.9, ls="--", label="股利")
    ax.plot(
        annual["fyear"],
        annual["net_repurchases"],
        color=COLOR_REPURCHASES,
        lw=1.9,
        ls=(0, (8, 3)),
        label="净回购",
    )
    ax.axhline(0, color="black", lw=0.8)
    ax.set_title("Figure 1  Compustat收益、特殊项目、股利和净回购总额，1970-2005")
    ax.set_xlabel("财政年度")
    ax.set_ylabel("$ millions")
    ax.yaxis.set_major_formatter(FuncFormatter(fmt_millions_axis))
    ax.grid(axis="y", color=GRID_COLOR, lw=0.6)
    ax.legend(loc="upper left", frameon=False, ncol=2)
    fig.text(
        0.09,
        0.03,
        "注：金额单位为Compustat百万美元。样本剔除非美国注册公司、金融公司和公用事业公司。",
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
            "原始合并数据",
            summary["raw_rows"],
            summary["raw_firms"],
            "2.csv与ajex.csv按gvkey和datadate合并后的观测。",
        ),
        (
            "WRDS格式筛选后",
            summary["wrds_rows"],
            summary["wrds_firms"],
            "保留consol=C、indfmt=INDL、datafmt=STD、curcd=USD。",
        ),
        (
            "美国注册公司",
            summary["usa_rows"],
            summary["usa_firms"],
            "保留fic=USA。",
        ),
        (
            "行业筛选后",
            summary["clean_rows_before_year"],
            summary["clean_firms_before_year"],
            "先构造sic_use：sich非缺失时使用历史行业代码，sich缺失时用sic补充；仅按sic_use剔除金融6000-6999和公用事业4900-4999。",
        ),
        (
            "sic_use来自sich",
            summary["sic_use_from_sich_rows"],
            np.nan,
            "行业筛选诊断项；表示使用历史行业代码sich判断行业的公司年数。",
        ),
        (
            "sic_use来自sic",
            summary["sic_use_from_sic_rows"],
            np.nan,
            "行业筛选诊断项；表示sich缺失时使用sic补充判断行业的公司年数。",
        ),
        (
            "按sic_use剔除金融/公用事业",
            summary["industry_excluded_rows"],
            summary["industry_excluded_firms"],
            f"金融公司年{summary['industry_excluded_financial_rows']:,.0f}；公用事业公司年{summary['industry_excluded_utility_rows']:,.0f}。",
        ),
        (
            "sic和sich均缺失",
            summary["sic_sich_missing_rows"],
            summary["sic_sich_missing_firms"],
            "诊断项；两个行业字段均缺失的公司保留，但报告中单独披露。",
        ),
        (
            "1970-2005样本",
            len(sample_1970),
            sample_1970["gvkey"].nunique(),
            "用于Figure 1。",
        ),
        (
            "1980-2005样本",
            len(sample_1980),
            sample_1980["gvkey"].nunique(),
            "用于Table 2、Figure 2、Figure 3与Table 3分组。",
        ),
    ]
    out = pd.DataFrame(rows, columns=["阶段", "公司年", "公司数", "说明"]).set_index("阶段")
    out["公司年"] = out["公司年"].map(fmt_int)
    out["公司数"] = out["公司数"].map(fmt_int)
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
                "组别": GROUP_NAMES_CN[gid],
                "原文公司数": published_firms,
                "当前公司数": current_firms,
                "差异": current_firms - published_firms,
                "公司年": len(g),
                "收益合计": sum_observed(g["earnings"]),
                "股利合计": sum_observed(g["dividend"]),
                "净回购合计": sum_observed(g["repurchase"]),
                "亏损比例": g["loss"].mean(),
                "ROA中位数": g["roa"].median(),
                "现金/资产中位数": g["cash"].median(),
                "三年收益中位数": g["past_stock_return"].median(),
                "ESO覆盖率": g_1995["eso_dilution"].notna().mean(),
            }
        )
    out = pd.DataFrame(rows).set_index("组别")
    display = out.copy()
    for col in ["原文公司数", "当前公司数", "差异", "公司年", "收益合计", "股利合计", "净回购合计"]:
        display[col] = display[col].map(fmt_int)
    for col in ["亏损比例", "ESO覆盖率"]:
        display[col] = display[col].map(fmt_pct)
    for col in ["ROA中位数", "现金/资产中位数", "三年收益中位数"]:
        display[col] = display[col].map(lambda x: "" if pd.isna(x) else f"{x:.3f}")
    out.to_csv(TABLE_DIR / "group_diagnostics_raw.csv")
    display.to_csv(TABLE_DIR / "group_diagnostics_display.csv")
    return display


def build_figure2(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    sample = df[(df["fyear"] >= 1980) & (df["fyear"] <= 2005)].copy()
    all_earnings = sample.groupby("fyear")["earnings"].apply(sum_observed).rename("All industrials").reset_index()
    group2 = (
        sample[sample["group_id"] == 2]
        .groupby("fyear")["earnings"]
        .apply(sum_observed)
        .rename("Regular div. + regular rep.")
        .reset_index()
    )
    panel_a = all_earnings.merge(group2, on="fyear", how="left")
    panel_a["Regular div. + regular rep."] = panel_a["Regular div. + regular rep."].fillna(0)

    wanted = [1, 3, 4, 5]
    panel_b = (
        sample[sample["group_id"].isin(wanted)]
        .groupby(["fyear", "group_name"])["earnings"]
        .apply(sum_observed)
        .reset_index()
    )
    panel_a.to_csv(TABLE_DIR / "figure2_panel_a_earnings.csv", index=False)
    panel_b.to_csv(TABLE_DIR / "figure2_panel_b_earnings.csv", index=False)
    return panel_a, panel_b


def plot_figure2(panel_a: pd.DataFrame, panel_b: pd.DataFrame) -> plt.Figure:
    fig, axes = plt.subplots(1, 2, figsize=PAGE, gridspec_kw={"width_ratios": [1.05, 1.0]})
    ax = axes[0]
    ax.plot(panel_a["fyear"], panel_a["All industrials"], color=COLOR_EARNINGS, lw=2.2, ls="--", label="全部工业公司")
    ax.plot(
        panel_a["fyear"],
        panel_a["Regular div. + regular rep."],
        color=COLOR_REPURCHASES,
        lw=2.0,
        label="Group II",
    )
    ax.axhline(0, color="black", lw=0.8)
    ax.set_title("Panel A: 全部公司与Group II")
    ax.set_xlabel("财政年度")
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
            "当前分组口径下无可绘制的Group I、III、IV、V观测",
            transform=ax.transAxes,
            ha="center",
            va="center",
            fontsize=9,
            color="#555555",
        )
    ax.axhline(0, color="black", lw=0.8)
    ax.set_title("Panel B: 其他长期支付组")
    ax.set_xlabel("财政年度")
    ax.set_ylabel("$ millions")
    ax.yaxis.set_major_formatter(FuncFormatter(fmt_millions_axis))
    ax.grid(axis="y", color=GRID_COLOR, lw=0.6)
    if plotted:
        ax.legend(frameon=False, loc="best", fontsize=8)

    fig.suptitle("Figure 2  按长期支付组划分的总收益，1980-2005", y=0.98, fontsize=13)
    fig.text(
        0.07,
        0.03,
        "注：分组依据1980-2005年的长期支付行为。收益定义为 ib - 0.6 x spi。",
        fontsize=8.5,
    )
    fig.tight_layout(rect=(0, 0.06, 1, 0.94))
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
            "当前分组口径下无可绘制的Group I-V亏损比例",
            transform=ax.transAxes,
            ha="center",
            va="center",
            fontsize=10,
            color="#555555",
        )
    ax.set_ylim(0, 0.9)
    ax.set_title("Figure 3  各长期支付组报告亏损的公司比例，1980-2005")
    ax.set_xlabel("财政年度")
    ax.set_ylabel("调整后收益小于0的公司比例")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _pos: f"{x * 100:.0f}%"))
    ax.grid(axis="y", color=GRID_COLOR, lw=0.6)
    if plotted:
        ax.legend(frameon=False, loc="upper left", ncol=2)
    fig.text(
        0.08,
        0.03,
        "注：亏损基于调整后收益。分组依据1980-2005年的长期支付行为。",
        fontsize=8.5,
    )
    fig.tight_layout(rect=(0, 0.06, 1, 0.98))
    return fig


# ---------------------------------------------------------------------------
# Table 3: Stata artifacts and Python-equivalent fallback
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


def write_and_maybe_run_stata() -> bool:
    do_path = STATA_DIR / "table3_replication.do"
    do_path.write_text(stata_do_code(), encoding="utf-8")

    if not RUN_STATA_IF_AVAILABLE:
        return False

    exe_candidate = find_stata_executable()
    if not exe_candidate:
        print("Stata executable not found on PATH. Set STATA_EXE if needed.")
        return False

    exe = Path(exe_candidate)
    if not exe.exists() and shutil.which(exe_candidate) is None:
        print(f"Stata executable not found: {exe_candidate}")
        return False

    try:
        run_dir = Path(tempfile.mkdtemp(prefix="skinner_2008_stata_run_"))
        temp_dta = run_dir / "table3_regression_data.dta"
        temp_do = run_dir / "table3_replication.do"
        temp_csv = run_dir / "table3_stata_results.csv"
        temp_log = run_dir / "table3_stata.log"
        temp_results = run_dir / "table3_stata_results.dta"

        shutil.copy2(STATA_DIR / "table3_regression_data.dta", temp_dta)
        temp_do.write_text(stata_do_code(run_dir), encoding="utf-8")

        command = [str(exe), "/b", "do", str(temp_do)] if exe.exists() else [exe_candidate, "/b", "do", str(temp_do)]
        proc = subprocess.Popen(command, cwd=str(run_dir))
        deadline = time.time() + 300
        while time.time() < deadline:
            if temp_csv.exists():
                break
            if proc.poll() is not None:
                break
            time.sleep(1)

        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()

        if proc.returncode not in (0, None) and not temp_csv.exists():
            raise RuntimeError(f"Stata exited with code {proc.returncode}")
        if not temp_csv.exists():
            raise TimeoutError("Stata did not create table3_stata_results.csv within 300 seconds.")

        if temp_csv.exists():
            shutil.copy2(temp_csv, STATA_DIR / "table3_stata_results.csv")
        if temp_log.exists():
            shutil.copy2(temp_log, STATA_DIR / "table3_stata.log")
        if temp_results.exists():
            shutil.copy2(temp_results, STATA_DIR / "table3_stata_results.dta")
        return (STATA_DIR / "table3_stata_results.csv").exists()
    except Exception as exc:
        print(f"Warning: Stata could not be run automatically: {exc}")
        return False


def windows_registry_path_entries() -> list[str]:
    if os.name != "nt":
        return []
    try:
        import winreg
    except Exception:
        return []

    locations = [
        (winreg.HKEY_CURRENT_USER, r"Environment", "Path"),
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
            "Path",
        ),
    ]
    entries: list[str] = []
    for hive, key_path, value_name in locations:
        try:
            with winreg.OpenKey(hive, key_path) as key:
                value, _kind = winreg.QueryValueEx(key, value_name)
        except Exception:
            continue
        expanded = os.path.expandvars(str(value))
        entries.extend([part for part in expanded.split(os.pathsep) if part.strip()])
    return entries


def find_stata_executable() -> str:
    if STATA_EXE.strip():
        return STATA_EXE.strip()

    command_names = ["stata", "StataMP-64", "StataSE-64", "StataBE-64", "StataIC-64"]
    for command in command_names:
        found = shutil.which(command)
        if found:
            return found

    env_paths = [p for p in os.environ.get("PATH", "").split(os.pathsep) if p.strip()]
    search_dirs = env_paths + windows_registry_path_entries()
    executable_names = [
        "stata.exe",
        "StataMP-64.exe",
        "StataSE-64.exe",
        "StataBE-64.exe",
        "StataIC-64.exe",
        "StataMP.exe",
        "StataSE.exe",
        "StataBE.exe",
        "StataIC.exe",
    ]
    for directory in search_dirs:
        path_dir = Path(directory)
        for name in executable_names:
            candidate = path_dir / name
            if candidate.exists():
                return str(candidate)

    common_roots = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
        Path(r"C:\Stata18"),
        Path(r"C:\Stata17"),
        Path(r"C:\Stata16"),
    ]
    for root in common_roots:
        if not root.exists():
            continue
        candidate_dirs = [root]
        if root.name == "Program Files" or root.name == "Program Files (x86)":
            for version in range(20, 12, -1):
                candidate_dirs.append(root / f"Stata{version}")
        for directory in candidate_dirs:
            for name in executable_names:
                candidate = directory / name
                if candidate.exists():
                    return str(candidate)
    return ""


def prepare_logit_sample(data: pd.DataFrame, required_cols: list[str]) -> pd.DataFrame:
    return data[required_cols].replace([np.inf, -np.inf], np.nan).dropna().copy()


def run_logit_model(data: pd.DataFrame, y: str, xvars: list[str]) -> dict[str, object]:
    cols = [y] + xvars
    sub = prepare_logit_sample(data, cols)
    sub = sub[sub[y].isin([0, 1])]
    if sub[y].nunique() < 2:
        raise ValueError("Logit dependent variable has only one class.")
    x = sm.add_constant(sub[xvars], has_constant="add")
    model = sm.Logit(sub[y], x)
    result = model.fit(disp=0, maxiter=200)
    return {
        "result": result,
        "n": int(result.nobs),
        "y1": int(sub[y].sum()),
        "y0": int(len(sub) - sub[y].sum()),
        "pseudo_r2": float(result.prsquared),
        "terms": ["const"] + xvars,
    }


def collect_model_rows(
    model_info: dict[str, object], panel: str, model_label: str, display_terms: list[tuple[str, str]]
) -> list[dict[str, object]]:
    result = model_info["result"]
    rows = []
    for term, label in display_terms:
        if term in result.params.index:
            coef = float(result.params.loc[term])
            se = float(result.bse.loc[term])
            pval = float(result.pvalues.loc[term])
        else:
            coef = se = pval = np.nan
        rows.append(
            {
                "panel": panel,
                "model": model_label,
                "term": term,
                "label": label,
                "coef": coef,
                "se": se,
                "p": pval,
                "pseudo_r2": model_info["pseudo_r2"],
                "N": model_info["n"],
                "y1": model_info["y1"],
                "y0": model_info["y0"],
            }
        )
    return rows


def empty_model_rows(
    panel: str,
    model_label: str,
    display_terms: list[tuple[str, str]],
    nobs: int,
    y1: int = 0,
    y0: int = 0,
) -> list[dict[str, object]]:
    return [
        {
            "panel": panel,
            "model": model_label,
            "term": term,
            "label": label,
            "coef": np.nan,
            "se": np.nan,
            "p": np.nan,
            "pseudo_r2": np.nan,
            "N": nobs,
            "y1": y1,
            "y0": y0,
        }
        for term, label in display_terms
    ]


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


def python_table3_results(reg: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    for panel, model_label, data, xvars, display_terms in table3_model_specs(reg):
        complete = prepare_logit_sample(data, ["repurchase_dummy"] + xvars)
        complete = complete[complete["repurchase_dummy"].isin([0, 1])]
        if len(complete) == 0 or complete["repurchase_dummy"].nunique() < 2:
            rows.extend(
                empty_model_rows(
                    panel,
                    model_label,
                    display_terms,
                    len(complete),
                    int(complete["repurchase_dummy"].sum()) if len(complete) else 0,
                    int(len(complete) - complete["repurchase_dummy"].sum()) if len(complete) else 0,
                )
            )
            continue
        info = run_logit_model(data, "repurchase_dummy", xvars)
        rows.extend(collect_model_rows(info, panel, model_label, display_terms))

    results = pd.DataFrame(rows)
    results.to_csv(TABLE_DIR / "table3_python_logit_results.csv", index=False)
    return results


def table3_all_models_estimable(reg: pd.DataFrame) -> bool:
    for _panel, _model_label, data, xvars, _display_terms in table3_model_specs(reg):
        complete = prepare_logit_sample(data, ["repurchase_dummy"] + xvars)
        complete = complete[complete["repurchase_dummy"].isin([0, 1])]
        if len(complete) == 0 or complete["repurchase_dummy"].nunique() < 2:
            return False
    return True


def stata_table3_results() -> pd.DataFrame:
    path = STATA_DIR / "table3_stata_results.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing Stata results file: {path}")

    results = pd.read_csv(path)
    term_map = {"_cons": "const"}
    label_map = {
        "const": "Intercept",
        "regular_dummy": "Regular dummy",
        "roa": "ROA",
        "roa_regular": "ROA x Regular",
        "past_stock_return": "Past stock return",
        "cash": "Cash",
        "eso_dilution": "ESO dilution",
    }
    results["term"] = results["term"].replace(term_map)
    results["label"] = results["term"].map(label_map).fillna(results["term"])
    for col in ["y1", "y0"]:
        if col not in results.columns:
            results[col] = np.nan
    results = results[["panel", "model", "term", "label", "coef", "se", "p", "pseudo_r2", "N", "y1", "y0"]]
    results.to_csv(TABLE_DIR / "table3_stata_logit_results.csv", index=False)
    return results


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


def validate_stata_sample_counts(reg: pd.DataFrame, stata_results: pd.DataFrame) -> None:
    python_audit = table3_python_sample_audit(reg)
    stata_audit = (
        stata_results.groupby(["panel", "model"], as_index=False)
        .agg(stata_N=("N", "first"), stata_y1=("y1", "first"), stata_y0=("y0", "first"))
    )
    merged = python_audit.merge(stata_audit, on=["panel", "model"], how="outer")
    for col in ["python_N", "python_y1", "python_y0", "stata_N", "stata_y1", "stata_y0"]:
        merged[col] = pd.to_numeric(merged[col], errors="coerce")
    merged["N_match"] = merged["python_N"].eq(merged["stata_N"])
    merged["y1_match"] = merged["python_y1"].eq(merged["stata_y1"])
    merged["y0_match"] = merged["python_y0"].eq(merged["stata_y0"])
    merged.to_csv(TABLE_DIR / "qa_table3_python_stata_sample_check.csv", index=False)
    bad = merged[~(merged["N_match"] & merged["y1_match"] & merged["y0_match"])]
    if not bad.empty:
        raise ValueError(
            "Python and Stata Table 3 samples differ. See "
            f"{TABLE_DIR / 'qa_table3_python_stata_sample_check.csv'}"
        )


def make_table3_display(results: pd.DataFrame, panel: str) -> pd.DataFrame:
    panel_data = results[results["panel"] == panel].copy()
    model_order = ["1980-1994", "1995-2005", "1995-2005 ESO"]
    term_order = list(dict.fromkeys(panel_data["label"].tolist()))
    out = pd.DataFrame(index=term_order, columns=model_order, dtype=object)
    for _, row in panel_data.iterrows():
        out.loc[row["label"], row["model"]] = fmt_coef(row["coef"], row["se"], row["p"])
    for model in model_order:
        model_rows = panel_data[panel_data["model"] == model]
        if not model_rows.empty:
            pseudo_r2 = model_rows["pseudo_r2"].iloc[0]
            out.loc["Pseudo R2", model] = "" if pd.isna(pseudo_r2) else f"{pseudo_r2 * 100:.1f}%"
            out.loc["Obs.", model] = fmt_int(model_rows["N"].iloc[0])
    return out.fillna("")


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
# PDF report
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


def add_text_page(pdf: PdfPages, title: str, sections: list[tuple[str, str]]) -> None:
    fig = plt.figure(figsize=PAGE)
    fig.patch.set_facecolor("white")
    y = 0.92
    fig.text(0.06, y, title, fontsize=18, weight="bold", ha="left", va="top")
    y -= 0.08
    for heading, body in sections:
        fig.text(0.06, y, heading, fontsize=12.5, weight="bold", ha="left", va="top")
        y -= 0.035
        for para in body.split("\n"):
            if not para.strip():
                y -= 0.018
                continue
            fig.text(0.075, y, wrap_text(para.strip(), 118), fontsize=9.5, ha="left", va="top", linespacing=1.25)
            y -= 0.038 + 0.017 * max(0, math.ceil(len(para) / 118) - 1)
        y -= 0.025
    pdf.savefig(fig, bbox_inches="tight")
    save_fig(fig, f"page_{title.lower().replace(' ', '_')[:45]}")
    plt.close(fig)


def add_table_page(
    pdf: PdfPages,
    title: str,
    subtitle: str,
    table: pd.DataFrame,
    note: str,
    filename: str,
    font_size: float = 8.0,
    scale_y: float = 1.25,
) -> None:
    fig = plt.figure(figsize=PAGE)
    fig.patch.set_facecolor("white")
    fig.text(0.05, 0.95, title, fontsize=14, weight="bold", ha="left", va="top")
    fig.text(0.05, 0.91, subtitle, fontsize=9.5, ha="left", va="top")
    ax = fig.add_axes([0.05, 0.14, 0.90, 0.70])
    ax.axis("off")

    display = table.copy()
    display.insert(0, "Rows", display.index)
    cell_text = display.values.tolist()
    col_labels = display.columns.tolist()
    tbl = ax.table(cellText=cell_text, colLabels=col_labels, cellLoc="center", loc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(font_size)
    tbl.scale(1.0, scale_y)

    nrows = len(cell_text)
    for (row, col), cell in tbl.get_celld().items():
        cell.set_edgecolor("black")
        cell.set_linewidth(0.65)
        if row == 0:
            cell.set_text_props(weight="bold")
            cell.set_facecolor("#f2f2f2")
            cell.visible_edges = "BT"
        elif row == nrows:
            cell.visible_edges = "B"
        else:
            cell.visible_edges = ""
        if col == 0 and row > 0:
            cell.set_text_props(weight="bold")

    fig.text(0.05, 0.07, wrap_text(note, 132), fontsize=8.0, ha="left", va="top")
    pdf.savefig(fig, bbox_inches="tight")
    save_fig(fig, filename)
    plt.close(fig)


def add_existing_figure_page(pdf: PdfPages, fig: plt.Figure, filename: str) -> None:
    pdf.savefig(fig, bbox_inches="tight")
    save_fig(fig, filename)
    plt.close(fig)


def build_report(
    df: pd.DataFrame,
    summary: dict[str, float],
    annual: pd.DataFrame,
    table1: dict[tuple[int, int], dict[str, pd.DataFrame]],
    table2: pd.DataFrame,
    fig2a: pd.DataFrame,
    fig2b: pd.DataFrame,
    fig3: pd.DataFrame,
    table3_results: pd.DataFrame,
    stata_ran: bool,
) -> None:
    sample_1970 = df[(df["fyear"] >= 1970) & (df["fyear"] <= 2005)]
    sample_1980 = df[(df["fyear"] >= 1980) & (df["fyear"] <= 2005)]
    group_counts = (
        sample_1980[["gvkey", "group_id"]]
        .drop_duplicates()
        .groupby("group_id")["gvkey"]
        .nunique()
        .rename("firms")
        .to_dict()
    )
    stata_note = (
        "Stata was run automatically from the configured executable path."
        if stata_ran
        else "The script exported the Stata data and do-file. Because STATA_EXE is not configured, Table 3 in this PDF uses the same logit specification estimated in Python; set STATA_EXE and rerun to refresh Stata output."
    )

    with PdfPages(REPORT_PDF) as pdf:
        add_text_page(
            pdf,
            "Replication of Skinner (2008): Earnings, Dividends, and Repurchases",
            [
                (
                    "Objective",
                    "This report replicates the required 1970-2005 empirical results from Skinner (2008): Figure 1, Figure 2, Figure 3, Table 1, Table 2, and the optional Table 3 logit regressions.",
                ),
                (
                    "Data",
                    f"The input data are WRDS Compustat Fundamentals Annual files. The raw main file contains {summary['raw_rows']:,.0f} firm-year rows; ajex matched {summary['ajex_match_rate'] * 100:.1f}% of rows. After applying the paper's US industrial-firm screen, the working dataset contains {summary['clean_rows_before_year']:,.0f} firm-year rows and {summary['clean_firms_before_year']:,.0f} firms before the final year restrictions.",
                ),
                (
                    "Sample Sizes",
                    f"For 1970-2005, the cleaned sample contains {len(sample_1970):,.0f} firm-years and {sample_1970['gvkey'].nunique():,.0f} firms. For 1980-2005, it contains {len(sample_1980):,.0f} firm-years and {sample_1980['gvkey'].nunique():,.0f} firms.",
                ),
                (
                    "Table 3 Status",
                    stata_note,
                ),
            ],
        )

        add_text_page(
            pdf,
            "Data Cleaning and Variable Definitions",
            [
                (
                    "Sample Screen",
                    "The replication keeps consolidated, industrial-format, standard-format, USD Compustat annual observations and retains both active and inactive firms. It then removes firms not incorporated in the United States, financial firms with SIC 6000-6999, and utilities with SIC 4900-4999. The industry screen uses both sic and sich, and excludes a firm-year if either field falls in the excluded ranges.",
                ),
                (
                    "Core Variables",
                    "Dividends equal dvc, with missing values retained as missing for payout classification. Adjusted earnings equal ib - 0.6 x spi, following the paper's assumption that special items have a 40% tax rate. Total payout is computed only when dividends and net repurchases are both observable.",
                ),
                (
                    "Net Repurchases",
                    "Net repurchases follow the Skinner/Fama-French definition. If treasury stock is used, repurchases equal the increase in common treasury stock using an exact gvkey plus fyear-1 match. If current and lagged treasury stock are both observed as zero, the firm is treated as using the retirement method and repurchases equal prstkc - sstk only when both cash-flow fields are observed. Negative computed values are set to zero; uncomputable values remain missing.",
                ),
                (
                    "Regression Variables",
                    "Table 3 uses roa = oibdp / lag(at) with an exact gvkey plus fyear-1 match, cash = che / at, split-adjusted price = prcc_f / ajex, past stock return over the exact prior three fiscal years, and ESO dilution = xintopt / sale x past stock return.",
                ),
            ],
        )

        add_existing_figure_page(pdf, plot_figure1(annual), "figure1")

        for window, data in table1.items():
            start, end = window
            add_table_page(
                pdf,
                f"Table 1, Panel A. Payout Policy Groups, {start}-{end}",
                "Cells report number of firms and fraction of firms. Rows are years with net repurchases; columns are years with common dividends.",
                data["count_display"],
                "Notes: Firms are included if they have at least one Compustat observation in the window. Dividends and net repurchases are classified annually using positive payout amounts.",
                f"table1_panel_a_{start}_{end}",
                font_size=8.6,
                scale_y=1.45,
            )
            add_table_page(
                pdf,
                f"Table 1, Panel B. Total Payout by Payout Policy Group, {start}-{end}",
                "Cells report aggregate total payout in Compustat $ millions and fraction of total payout. Rows are years with net repurchases; columns are years with common dividends.",
                data["payout_display"],
                "Notes: Total payout equals dividends plus net repurchases, summed across all firm-years in each cell.",
                f"table1_panel_b_{start}_{end}",
                font_size=8.6,
                scale_y=1.45,
            )

        add_table_page(
            pdf,
            "Table 2. Payout Policy Groups over 1980-2005",
            "Cells report the number of firms. Rows are years with net repurchases; columns are years with common dividends.",
            table2,
            "Notes: Group definitions used in Figure 2, Figure 3, and Table 3 are based on this long-run 1980-2005 classification.",
            "table2",
            font_size=8.2,
            scale_y=1.30,
        )

        add_text_page(
            pdf,
            "Long-Run Group Counts Used in Later Tests",
            [
                (
                    "Groups",
                    "\n".join(
                        [
                            f"Group I, Non-payers: {group_counts.get(1, 0):,.0f} firms.",
                            f"Group II, regular dividends and regular repurchases: {group_counts.get(2, 0):,.0f} firms.",
                            f"Group III, occasional repurchases only: {group_counts.get(3, 0):,.0f} firms.",
                            f"Group IV, regular repurchases only: {group_counts.get(4, 0):,.0f} firms.",
                            f"Group V, regular dividend-only firms: {group_counts.get(5, 0):,.0f} firms.",
                        ]
                    ),
                ),
                (
                    "Interpretation",
                    "These groups are not arbitrary year-by-year labels. They describe a firm's long-run payout behavior across 1980-2005, which is why the same grouping is reused in Figure 2, Figure 3, and the Table 3 regressions.",
                ),
            ],
        )

        add_existing_figure_page(pdf, plot_figure2(fig2a, fig2b), "figure2")
        add_existing_figure_page(pdf, plot_figure3(fig3), "figure3")

        table3_a = make_table3_display(table3_results, "Panel A")
        table3_b = make_table3_display(table3_results, "Panel B")
        add_table_page(
            pdf,
            "Table 3, Panel A. Repurchase Logit Regressions: Regular Dividend and Repurchase Firms",
            "Dependent variable equals one for firm-years with positive net repurchases.",
            table3_a,
            "Notes: Coefficients are reported with standard errors in parentheses. * and ^ denote significance at the 1% and 5% levels. The embedded Stata do-code uses the same sample and variables.",
            "table3_panel_a",
            font_size=8.0,
            scale_y=1.25,
        )
        add_table_page(
            pdf,
            "Table 3, Panel B. Repurchase Logit Regressions: Repurchase-Only Firms",
            "Dependent variable equals one for firm-years with positive net repurchases. Regular dummy equals one for regular repurchasers.",
            table3_b,
            "Notes: Coefficients are reported with standard errors in parentheses. * and ^ denote significance at the 1% and 5% levels. ESO dilution is available mainly after 1995.",
            "table3_panel_b",
            font_size=8.0,
            scale_y=1.18,
        )

        add_text_page(
            pdf,
            "Replication Notes and Economic Interpretation",
            [
                (
                    "Main Patterns",
                    "The replication is designed to verify the paper's central patterns rather than match every number exactly: dividends are smoother than earnings, repurchases become economically important after the early 1980s, and firms with both regular dividends and regular repurchases account for a large portion of aggregate earnings and payouts.",
                ),
                (
                    "Economic Meaning of Cleaning Choices",
                    "The financial, utility, and non-US exclusions align the sample with industrial operating firms whose payout policy is more comparable. Treating missing payout variables as zero follows the assignment requirement and is economically natural when a payout item is absent from the annual record.",
                ),
                (
                    "Expected Sources of Differences",
                    "Small numerical differences from the published paper can arise from WRDS historical database updates, field backfills, fiscal-year coverage, treatment of missing treasury stock data, and the availability of delisted or inactive firms in the current Compustat extract.",
                ),
            ],
        )


# ---------------------------------------------------------------------------
# ElegantPaper LaTeX report builder
# ---------------------------------------------------------------------------


def latex_escape(value: object) -> str:
    text = "" if pd.isna(value) else str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def latex_line_with_marker(line: str) -> str:
    if line.endswith("*"):
        return latex_escape(line[:-1]) + r"\textsuperscript{*}"
    if line.endswith("^"):
        return latex_escape(line[:-1]) + r"\textsuperscript{\(\dagger\)}"
    return latex_escape(line)


def latex_cell(value: object) -> str:
    text = "" if pd.isna(value) else str(value)
    parts = text.split("\n")
    if len(parts) == 1:
        return latex_line_with_marker(parts[0])
    return r"\makecell{" + r" \\ ".join(latex_line_with_marker(p) for p in parts) + "}"


def latex_table(
    table: pd.DataFrame,
    caption: str,
    label: str,
    note: str,
    font_size: str = r"\scriptsize",
    placement: str = "H",
    numbered: bool = True,
    landscape: bool = False,
) -> str:
    display = table.copy()
    display.insert(0, "", display.index)
    ncols = len(display.columns)
    colspec = "l" + "c" * (ncols - 1)
    header = " & ".join(latex_escape(c) for c in display.columns) + r" \\"
    rows = []
    for _, row in display.iterrows():
        rows.append(" & ".join(latex_cell(v) for v in row.tolist()) + r" \\")
    body = "\n".join(rows)
    caption_cmd = r"\caption" if numbered else r"\caption*"
    label_line = rf"\label{{{label}}}" if label else ""
    table_tex = rf"""
\begin{{table}}[{placement}]
\centering
{caption_cmd}{{{latex_escape(caption)}}}
{label_line}
{font_size}
\begin{{threeparttable}}
\renewcommand{{\arraystretch}}{{1.18}}
\begin{{adjustbox}}{{max width=\textwidth}}
\begin{{tabular}}{{{colspec}}}
\toprule
{header}
\midrule
{body}
\bottomrule
\end{{tabular}}
\end{{adjustbox}}
\begin{{tablenotes}}[flushleft]
\footnotesize
\item {latex_escape(note)}
\end{{tablenotes}}
\end{{threeparttable}}
\end{{table}}
"""
    if landscape:
        return "\n\\begin{landscape}\n" + table_tex + "\n\\end{landscape}\n"
    return table_tex


def latex_table1_panel(table: pd.DataFrame, panel_title: str, label: str, note: str, numbered: bool = True) -> str:
    display = table.copy()
    caption_cmd = r"\caption" if numbered else r"\caption*"
    caption_text = (
        "Table 1. Compustat工业公司按10年窗口支付政策分组，1980-2005"
        if numbered
        else "Table 1续"
    )
    label_line = rf"\label{{{label}}}" if label else ""
    header = " & ".join(latex_escape(c) for c in display.columns) + r" \\"
    rows = []
    for row_label, row in display.iterrows():
        rows.append(latex_cell(row_label) + " & " + " & ".join(latex_cell(v) for v in row.tolist()) + r" \\")
    body = "\n".join(rows)
    return rf"""
\begin{{table}}[p]
\centering
{caption_cmd}{{{latex_escape(caption_text)}}}
{label_line}
\scriptsize
\begin{{threeparttable}}
\renewcommand{{\arraystretch}}{{1.08}}
\begin{{tabular}}{{lccccc}}
\toprule
\multicolumn{{6}}{{l}}{{{latex_escape(panel_title)}}} \\
\midrule
Number of years of repurchases & \multicolumn{{5}}{{c}}{{Number of years of dividends}} \\
\cmidrule(lr){{2-6}}
 & {header}
\midrule
{body}
\bottomrule
\end{{tabular}}
\begin{{tablenotes}}[flushleft]
\footnotesize
\item {latex_escape(note)}
\end{{tablenotes}}
\end{{threeparttable}}
\end{{table}}
"""


def latex_figure(path: Path, caption: str, label: str, width: str = r"0.95\textwidth") -> str:
    rel = path.relative_to(OUTPUT_DIR).as_posix()
    return rf"""
\begin{{figure}}[H]
\centering
\includegraphics[width={width}]{{{rel}}}
\caption{{{latex_escape(caption)}}}
\label{{{label}}}
\end{{figure}}
"""


def latex_paragraph(text: str) -> str:
    return latex_escape(text).replace("\n", "\n\n")


def build_latex_source(
    df: pd.DataFrame,
    summary: dict[str, float],
    annual: pd.DataFrame,
    table1: dict[tuple[int, int], dict[str, pd.DataFrame]],
    table2: pd.DataFrame,
    fig2a: pd.DataFrame,
    fig2b: pd.DataFrame,
    fig3: pd.DataFrame,
    table3_results: pd.DataFrame,
    sample_audit: pd.DataFrame,
    group_diagnostics: pd.DataFrame,
    stata_ran: bool,
) -> str:
    if not ELEGANT_CLASS.exists():
        raise FileNotFoundError(
            "elegantpaper.cls is missing. Download it from https://github.com/ElegantLaTeX/ElegantPaper."
        )
    shutil.copy2(ELEGANT_CLASS, OUTPUT_DIR / "elegantpaper.cls")

    fig1_path = save_fig(plot_figure1(annual), "figure1")
    fig2_path = save_fig(plot_figure2(fig2a, fig2b), "figure2")
    fig3_path = save_fig(plot_figure3(fig3), "figure3")
    plt.close("all")

    sample_1970 = df[(df["fyear"] >= 1970) & (df["fyear"] <= 2005)]
    sample_1980 = df[(df["fyear"] >= 1980) & (df["fyear"] <= 2005)]
    table3_first_n = table3_results.groupby(["panel", "model"])["N"].first()
    table3_has_empty_model = bool((table3_first_n.fillna(0) == 0).any())
    if stata_ran:
        stata_note = "Table 3由Stata通过已配置的可执行文件路径估计，并由Python读取Stata导出的结果写入报告。"
    elif table3_has_empty_model:
        stata_note = (
            "至少一个Table 3模型没有可估计样本或因变量只有单一类别，因此脚本跳过Stata以避免失败或读取旧结果。"
            "表中保留同一模型结构；可估计模型由Python同口径logit生成，样本不足的模型系数留空并报告Obs.。"
        )
    else:
        stata_note = "Python已经导出Stata回归数据和do文件，但当前Python进程未发现可调用的Stata。因此Table 3暂以Python按同一logit设定估计的结果填入；若Stata路径可见，重新运行脚本即可刷新为Stata结果。"

    table1_panel_a, table1_panel_b = build_table1_paper_panels(table1)
    table2_display = table2.map(fmt_int)
    table3_a = make_table3_display(table3_results, "Panel A")
    table3_b = make_table3_display(table3_results, "Panel B")
    table2_total = int(table2.loc["Sum", "Sum"])
    table2_zero_div = int(table2.loc["Sum", "0"])

    return rf"""
% Based on the ElegantPaper template from https://github.com/ElegantLaTeX/ElegantPaper
\documentclass[lang=cn,a4paper,11pt]{{elegantpaper}}
\usepackage{{float}}
\usepackage{{makecell}}
\usepackage{{threeparttable}}
\usepackage{{pdflscape}}
\usepackage{{array}}
\usepackage{{adjustbox}}
\usepackage{{caption}}
\graphicspath{{{{figures/}}}}

\title{{Skinner (2008) 收益、股利与股票回购关系复现}}
\author{{Python编程基础期末项目}}
\institute{{Nankai University}}
\version{{修订版复现报告}}
\date{{2026年7月}}

\begin{{document}}
\maketitle

\begin{{abstract}}
本文复现Skinner (2008) 在1970-2005样本期内的核心结果，包括Figure 1、Figure 2、Figure 3以及Table 1、Table 2、Table 3。数据来自WRDS Compustat Fundamentals Annual。样本统一剔除非美国注册公司、金融公司和公用事业公司，并按照原文构造调整后收益、股利、净回购和长期支付政策分组。
\keywords{{Skinner (2008), 股利, 股票回购, Compustat, 支付政策, 论文复现}}
\end{{abstract}}

\section{{数据、样本与变量定义}}
主数据文件包含{summary['raw_rows']:,.0f}个Compustat公司年观测，\texttt{{ajex}}调整因子文件按\texttt{{gvkey}}和\texttt{{datadate}}的匹配率为{summary['ajex_match_rate'] * 100:.1f}\%。本文保留\texttt{{consol=C}}、\texttt{{indfmt=INDL}}、\texttt{{datafmt=STD}}、\texttt{{curcd=USD}}的年度数据，并保留美国注册公司。行业筛选先构造\texttt{{sic\_use}}：\texttt{{sich}}非缺失时使用历史行业代码，\texttt{{sich}}缺失时才用\texttt{{sic}}补充；随后按\texttt{{sic\_use}}剔除金融业6000-6999和公用事业4900-4999。active与inactive公司均保留，以避免幸存者偏差。最终1970-2005样本有{len(sample_1970):,.0f}个公司年和{sample_1970['gvkey'].nunique():,.0f}家公司；1980-2005样本有{len(sample_1980):,.0f}个公司年和{sample_1980['gvkey'].nunique():,.0f}家公司。

股利定义为\texttt{{dvc}}，原始缺失值保留为缺失；股利状态只有在\texttt{{dvc}}可观测时才判定为0或1。调整后收益定义为\texttt{{ib}}减去0.6倍\texttt{{spi}}，其中\texttt{{spi}}缺失填0。净回购按Skinner/Fama-French口径构造：第一优先使用同一公司精确上一财政年度\texttt{{tstkc}}的增加额；当本年和上一财政年度\texttt{{tstkc}}均真实观测为0且现金流字段完整时，使用\texttt{{prstkc}}减去\texttt{{sstk}}作为明确的退休法；当连续\texttt{{tstkc}}不可观测但\texttt{{prstkc}}和\texttt{{sstk}}均可观测时，使用\texttt{{cashflow\_fallback}}作为现金流替代测量。若不存在可用测量，净回购和回购状态保持缺失；已成功构造出的负回购值置0。总支付等于可观测股利加可观测净回购。

Table 3中，\texttt{{ROA}}为\texttt{{oibdp}}除以同一公司精确上一财政年度\texttt{{at}}，现金变量为当期\texttt{{che/at}}。拆股调整价格为\texttt{{prcc\_f/ajex}}，仅在价格和调整因子均有效时计算；三年股票收益按同一公司财政年度\texttt{{fyear-3}}的拆股调整价格精确匹配。ESO dilution定义为\texttt{{xintopt/sale}}乘以三年股票收益，且仅在1995年以后及所有输入有效时计算。

\section{{总量趋势}}
{latex_figure(fig1_path, "Compustat收益、特殊项目、股利和净回购总额，1970-2005。金额单位为百万美元。", "fig:figure1")}

\section{{支付政策分类}}
{latex_table1_panel(table1_panel_a, "Panel A: 各支付政策组中的Compustat公司数（括号内为比例）", "tab:table1", "行表示窗口内净回购发生年份数，列表示普通股股利支付年份数。括号内为该窗口内公司数占比。", numbered=True)}

{latex_table1_panel(table1_panel_b, "Panel B: 各支付政策组的总支付金额（括号内为比例，金额单位为百万美元）", "", "总支付金额等于股利加净回购。括号内为该窗口内总支付金额占比。", numbered=False)}

{latex_table(table2_display, "Table 2. 1980-2005长期支付政策分组", "tab:table2", "单元格报告公司数。行表示1980-2005年间发生净回购的年份数，列表示支付普通股股利的年份数。该长期分类用于Figure 2、Figure 3和Table 3。当前Table 2总公司数为" + fmt_int(table2_total) + "，0股利列为" + fmt_int(table2_zero_div) + "；原文对应数字为10,675和6,852。", font_size=r"\scriptsize")}

\section{{长期分组的收益与亏损}}
{latex_figure(fig2_path, "按长期支付组划分的总收益，1980-2005。金额单位为百万美元。", "fig:figure2")}
{latex_figure(fig3_path, "各长期支付组报告亏损的公司比例，1980-2005。", "fig:figure3")}

\section{{回购Logit回归}}
{latex_escape(stata_note)}

{latex_table(table3_a, "Table 3, Panel A. 经常支付股利且经常回购公司的回购Logit回归", "tab:table3a", "因变量在公司年净回购大于0时取1，净回购可观测且等于0时取0；净回购缺失的观测按各模型变量集删除。表中报告系数，括号内为标准误。*和dagger分别表示1%和5%显著性水平。", font_size=r"\scriptsize")}

{latex_table(table3_b, "Table 3, Panel B. 仅回购公司的回购Logit回归", "tab:table3b", "因变量在公司年净回购大于0时取1，净回购可观测且等于0时取0；净回购缺失的观测按各模型变量集删除。Regular dummy在Group IV经常回购公司中取1，在Group III偶尔回购公司中取0。表中报告系数，括号内为标准误。*和dagger分别表示1%和5%显著性水平。", font_size=r"\scriptsize")}

\section{{复现诊断}}
本次修订采用论文近似口径C：Table 1的每个十年窗口、Table 2的1980-2005长窗口以及Group I-V分组，均要求公司在对应窗口内至少有1个清洗后公司年观测即可进入。支付年份数只累计可观察到的正股利或正净回购；某一年度支付状态缺失时，不把该年度改写为0，也不因该年度缺失而排除整家公司。因此，表中“0年支付”应理解为窗口内未观察到正支付记录，而不是证明所有缺失年份均无支付。

净回购构造仍以库存股变动为第一优先、明确退休法为第二优先；当连续\texttt{{tstkc}}不可观测但\texttt{{prstkc}}和\texttt{{sstk}}均可观测时，本次修订允许使用\texttt{{cashflow\_fallback}}。这一路径能够恢复一部分由于库存股历史字段缺失而无法进入回购分类和Table 3的观测，但不会把原始缺失无条件填0，也不会把现金流替代测量解释为已确认的退休法。

与原论文的差异主要来自三方面：第一，当前WRDS Compustat数据经过后续更新和历史回填，原始公司年宇宙与Skinner (2008)使用的数据版本不同；第二，本项目缺少CRSP/CCM层面的普通股、交易所和证券层筛选，因此公司数量可能偏大；第三，回购变量依赖\texttt{{tstkc}}、\texttt{{prstkc}}和\texttt{{sstk}}的历史可得性，现金流替代路径会改变0回购列、Group I-V和Table 3的有效样本量。附录诊断表用于说明这些差异，而不作为原论文编号表格。

{latex_table(sample_audit, "样本清洗审计", "", "该表用于说明复现样本从原始数据到最终分析样本的逐步变化，不属于原论文编号表格。", font_size=r"\scriptsize", numbered=False)}

{latex_table(group_diagnostics, "Group I-V样本诊断与描述性统计", "", "原文公司数来自Skinner (2008) Table 2及正文分组说明。当前统计基于清洗后的1980-2005样本；金额单位为百万美元。该表用于解释样本量、0股利列和回归结果差异，不属于原论文编号表格。", font_size=r"\tiny", placement="p", numbered=False, landscape=True)}

\end{{document}}
"""


def compile_latex_report() -> None:
    if not REPORT_TEX.exists():
        raise FileNotFoundError(f"Missing LaTeX report source: {REPORT_TEX}")

    latexmk = shutil.which("latexmk")
    xelatex = shutil.which("xelatex")
    if latexmk:
        command = [
            latexmk,
            "-xelatex",
            "-interaction=nonstopmode",
            "-halt-on-error",
            REPORT_TEX.name,
        ]
        subprocess.run(command, cwd=str(OUTPUT_DIR), check=True)
    elif xelatex:
        command = [xelatex, "-interaction=nonstopmode", "-halt-on-error", REPORT_TEX.name]
        subprocess.run(command, cwd=str(OUTPUT_DIR), check=True)
        subprocess.run(command, cwd=str(OUTPUT_DIR), check=True)
    else:
        raise RuntimeError("Neither latexmk nor xelatex was found on PATH.")

    compiled = OUTPUT_DIR / REPORT_PDF.name
    if not compiled.exists():
        raise FileNotFoundError(f"LaTeX did not create expected PDF: {compiled}")
    shutil.copy2(compiled, REPORT_PDF)


def build_report(
    df: pd.DataFrame,
    summary: dict[str, float],
    annual: pd.DataFrame,
    table1: dict[tuple[int, int], dict[str, pd.DataFrame]],
    table2: pd.DataFrame,
    fig2a: pd.DataFrame,
    fig2b: pd.DataFrame,
    fig3: pd.DataFrame,
    table3_results: pd.DataFrame,
    sample_audit: pd.DataFrame,
    group_diagnostics: pd.DataFrame,
    stata_ran: bool,
) -> None:
    source = build_latex_source(
        df,
        summary,
        annual,
        table1,
        table2,
        fig2a,
        fig2b,
        fig3,
        table3_results,
        sample_audit,
        group_diagnostics,
        stata_ran,
    )
    REPORT_TEX.write_text(source, encoding="utf-8")
    compile_latex_report()


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------


def write_summary_file(
    summary: dict[str, float],
    df: pd.DataFrame,
    firm_groups: pd.DataFrame,
    stata_ran: bool,
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
    lines.append(f"Stata automatically run: {stata_ran}")
    lines.append(f"Report: {REPORT_PDF}")
    (OUTPUT_DIR / "run_summary.txt").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ensure_dirs()
    main_df, ajex_df = read_inputs()
    clean, summary = clean_and_construct(main_df, ajex_df)
    clean, firm_groups = add_long_run_groups(clean)

    annual = build_figure1(clean)
    table1 = {
        (1980, 1989): table1_window(clean, 1980, 1989),
        (1985, 1994): table1_window(clean, 1985, 1994),
        (1990, 1999): table1_window(clean, 1990, 1999),
        (1995, 2004): table1_window(clean, 1995, 2004),
    }
    table2 = build_table2(firm_groups)
    fig2a, fig2b = build_figure2(clean)
    fig3 = build_figure3(clean)
    sample_audit = build_sample_audit_table(summary, clean)
    group_diagnostics = build_group_diagnostics(clean, firm_groups)

    reg = build_table3_data(clean)
    write_cleaning_qa_outputs(clean, firm_groups, table1, table2, reg)
    table3_estimable = table3_all_models_estimable(reg)
    if table3_estimable:
        stata_ran = write_and_maybe_run_stata()
    else:
        stata_ran = False
        print("At least one Table 3 model has no estimable sample or one dependent-variable class; skipping Stata.")
    python_results = python_table3_results(reg)
    if stata_ran:
        stata_results = stata_table3_results()
        validate_stata_sample_counts(reg, stata_results)
        table3_results = stata_results
    else:
        table3_results = python_results

    build_report(
        clean,
        summary,
        annual,
        table1,
        table2,
        fig2a,
        fig2b,
        fig3,
        table3_results,
        sample_audit,
        group_diagnostics,
        stata_ran,
    )
    write_summary_file(summary, clean, firm_groups, stata_ran, table3_estimable)
    print(f"Created {REPORT_PDF}")
    print(f"Created support outputs under {OUTPUT_DIR}")
    if not stata_ran:
        if table3_estimable:
            print(f"Stata do-file exported to {STATA_DIR / 'table3_replication.do'}")
            print("Set STATA_EXE in replicate_skinner_2008.py and rerun if you want automatic Stata execution.")
        else:
            print("Stata was skipped because at least one Table 3 model has no estimable sample or one dependent-variable class.")
            print(f"See {TABLE_DIR / 'qa_table3_regression_sample_counts.csv'} for model-level sample counts.")


if __name__ == "__main__":
    main()
