from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent.parent
MAIN_CSV = BASE_DIR / "2.csv"
CURRENT_OUT_DIR = PROJECT_DIR / "shared_artifacts" / "python_out"
OUTPUT_DIR = PROJECT_DIR / "shared_artifacts" / "python_out_figure123_revision"
TABLE_DIR = OUTPUT_DIR / "tables"
FIGURE_DIR = OUTPUT_DIR / "figures"

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


def ensure_dirs() -> None:
    for path in [OUTPUT_DIR, TABLE_DIR, FIGURE_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def safe_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def sum_observed(series: pd.Series) -> float:
    return series.sum(min_count=1)


def fmt_millions_axis(value: float, _pos: int) -> str:
    if abs(value) >= 1000:
        return f"{value:,.0f}"
    return f"{value:.0f}"


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
    examples = df.loc[dup_mask, ["gvkey", "fyear", "datadate"]].head(10).to_dict(orient="records")
    raise ValueError(f"{context} has duplicated gvkey-fyear rows. Examples: {examples}")


def read_main() -> pd.DataFrame:
    if not MAIN_CSV.exists():
        raise FileNotFoundError(f"Missing main WRDS file: {MAIN_CSV}")

    main = pd.read_csv(MAIN_CSV, low_memory=False)
    required = {
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
        "tstkc",
        "dvc",
        "ib",
        "spi",
        "prstkc",
        "sstk",
    }
    missing = sorted(required - set(main.columns))
    if missing:
        raise ValueError(f"Main CSV is missing variables: {missing}")
    if main.duplicated(["gvkey", "datadate"]).any():
        raise ValueError("Main CSV has duplicated gvkey-datadate rows.")
    return main


def clean_compustat_for_figures(main: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float]]:
    df = main.copy()
    numeric_cols = [
        "gvkey",
        "fyear",
        "sic",
        "sich",
        "tstkc",
        "dvc",
        "ib",
        "spi",
        "prstkc",
        "sstk",
    ]
    for col in numeric_cols:
        df[col] = safe_numeric(df[col])

    raw_rows = len(df)
    raw_firms = int(df["gvkey"].nunique())
    curcd_usd_rows = int(df["curcd"].eq("USD").sum())
    curcd_non_usd_rows = int(df["curcd"].notna().sum() - curcd_usd_rows)

    format_mask = (df["consol"] == "C") & (df["indfmt"] == "INDL") & (df["datafmt"] == "STD")
    df = df[format_mask].copy()
    format_rows = len(df)
    format_firms = int(df["gvkey"].nunique())

    df = df[df["fic"] == "USA"].copy()
    usa_rows = len(df)
    usa_firms = int(df["gvkey"].nunique())

    df["sic_use"] = df["sich"].where(df["sich"].notna(), df["sic"])
    df["is_financial"] = df["sic_use"].between(6000, 6999, inclusive="both")
    df["is_utility"] = df["sic_use"].between(4900, 4999, inclusive="both")
    industry_excluded = df["is_financial"] | df["is_utility"]
    industry_excluded_rows = int(industry_excluded.sum())
    industry_excluded_firms = int(df.loc[industry_excluded, "gvkey"].nunique())
    df = df[~industry_excluded].copy()

    df = df.sort_values(["gvkey", "fyear", "datadate"]).reset_index(drop=True)
    assert_unique_firm_year(df, "Figure-only pure Compustat sample")

    df["dividend"] = df["dvc"]
    df["dividend_dummy"] = np.select(
        [df["dvc"].gt(0), df["dvc"].eq(0)],
        [1.0, 0.0],
        default=np.nan,
    )
    df["earnings_raw"] = df["ib"]
    df["adjusted_earnings"] = np.where(
        df["ib"].notna(),
        df["ib"] - 0.6 * df["spi"].fillna(0),
        np.nan,
    )
    df["special_items_figure1"] = df["spi"]

    lag_tstkc = df[["gvkey", "fyear", "tstkc"]].copy()
    lag_tstkc["fyear"] = lag_tstkc["fyear"] + 1
    lag_tstkc = lag_tstkc.rename(columns={"tstkc": "tstkc_lag1"})
    df = df.merge(lag_tstkc, on=["gvkey", "fyear"], how="left", validate="one_to_one")

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
    df["loss"] = np.select(
        [
            df["adjusted_earnings"].lt(0),
            df["adjusted_earnings"].ge(0),
        ],
        [
            1.0,
            0.0,
        ],
        default=np.nan,
    )

    summary = {
        "raw_rows": raw_rows,
        "raw_firms": raw_firms,
        "raw_curcd_usd_rows": curcd_usd_rows,
        "raw_curcd_non_usd_rows": curcd_non_usd_rows,
        "format_rows_without_curcd_filter": format_rows,
        "format_firms_without_curcd_filter": format_firms,
        "usa_rows": usa_rows,
        "usa_firms": usa_firms,
        "industry_excluded_rows": industry_excluded_rows,
        "industry_excluded_firms": industry_excluded_firms,
        "figure_clean_rows": len(df),
        "figure_clean_firms": int(df["gvkey"].nunique()),
    }
    return df, summary


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
        )
        .reset_index()
    )
    firm["main_sample_entry"] = firm["div_valid_years"].ge(1) & firm["rep_valid_years"].ge(1)
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
    firm["group_id"] = pd.Series(pd.NA, index=firm.index, dtype="Int64")
    for condition, choice in zip(conditions, [1, 2, 3, 4, 5]):
        firm.loc[condition, "group_id"] = choice
    firm.loc[entrant & firm["group_id"].isna(), "group_id"] = 0
    firm["group_name"] = firm["group_id"].map(GROUP_NAMES)
    firm.loc[firm["group_id"].eq(0).fillna(False), "group_name"] = "Other"
    firm["group_name"] = firm["group_name"].fillna("No 1980-2005 observation")

    out = df.merge(firm[["gvkey", "group_id", "group_name"]], on="gvkey", how="left")
    return out, firm


def build_figure1(df: pd.DataFrame) -> pd.DataFrame:
    sample = df[(df["fyear"] >= 1970) & (df["fyear"] <= 2005)].copy()
    annual = (
        sample.groupby("fyear")
        .agg(
            earnings_raw=("earnings_raw", sum_observed),
            special_items=("special_items_figure1", sum_observed),
            dividends=("dividend", sum_observed),
            net_repurchases=("repurchase", sum_observed),
            firms=("gvkey", "nunique"),
        )
        .reset_index()
    )
    annual.to_csv(TABLE_DIR / "figure1_annual_aggregates_revision.csv", index=False)
    return annual


def plot_figure1(annual: pd.DataFrame) -> plt.Figure:
    fig, ax = plt.subplots(figsize=PAGE)
    ax.plot(annual["fyear"], annual["earnings_raw"], color=COLOR_EARNINGS, lw=2.2, label="Compustat earnings")
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
    ax.set_title("Figure 1 revision  Aggregate Compustat earnings, special items, dividends, and net repurchases")
    ax.set_xlabel("Fiscal year")
    ax.set_ylabel("$ millions")
    ax.yaxis.set_major_formatter(FuncFormatter(fmt_millions_axis))
    ax.grid(axis="y", color=GRID_COLOR, lw=0.6)
    ax.legend(loc="upper left", frameon=False, ncol=2)
    fig.text(
        0.09,
        0.03,
        "Notes: Figure-only pure Compustat sample; no CRSP/CCM stock screen and no curcd hard filter.",
        fontsize=8.5,
    )
    fig.tight_layout(rect=(0, 0.06, 1, 0.98))
    return fig


def build_figure2(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    sample = df[(df["fyear"] >= 1980) & (df["fyear"] <= 2005)].copy()
    all_earnings = (
        sample.groupby("fyear")["adjusted_earnings"]
        .apply(sum_observed)
        .rename("All industrials")
        .reset_index()
    )
    group2 = (
        sample[sample["group_id"] == 2]
        .groupby("fyear")["adjusted_earnings"]
        .apply(sum_observed)
        .rename("Regular div. + regular rep.")
        .reset_index()
    )
    panel_a = all_earnings.merge(group2, on="fyear", how="left")
    panel_a["Regular div. + regular rep."] = panel_a["Regular div. + regular rep."].fillna(0)

    panel_b = (
        sample[sample["group_id"].isin([1, 3, 4, 5])]
        .groupby(["fyear", "group_name"])["adjusted_earnings"]
        .apply(sum_observed)
        .reset_index()
        .rename(columns={"adjusted_earnings": "earnings"})
    )
    panel_a.to_csv(TABLE_DIR / "figure2_panel_a_adjusted_earnings_revision.csv", index=False)
    panel_b.to_csv(TABLE_DIR / "figure2_panel_b_adjusted_earnings_revision.csv", index=False)
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
    for name, g in panel_b.groupby("group_name"):
        color, ls = styles.get(name, ("black", "-"))
        ax.plot(g["fyear"], g["earnings"], color=color, lw=1.9, ls=ls, label=legend_labels.get(name, name))
    place_xaxis_at_zero(ax)
    ax.set_xlim(1980, 2005)
    ax.set_ylim(-80000, 40000)
    ax.margins(x=0)
    ax.set_title("Panel B: Other long-run payout groups")
    ax.set_xlabel("Fiscal year")
    ax.set_ylabel("$ millions")
    ax.yaxis.set_major_formatter(FuncFormatter(fmt_millions_axis))
    ax.grid(axis="y", color=GRID_COLOR, lw=0.6)
    ax.legend(frameon=False, loc="best", fontsize=8)

    fig.suptitle("Figure 2 revision  Adjusted earnings by long-run payout group, 1980-2005", y=0.98, fontsize=13)
    fig.text(
        0.07,
        0.03,
        "Notes: Figure-only pure Compustat sample. Earnings are ib - 0.6 x spi, with missing spi set to zero only inside this adjusted-earnings formula.",
        fontsize=8.5,
    )
    fig.tight_layout(rect=(0, 0.06, 1, 0.94), h_pad=2.0)
    return fig


def build_figure3(df: pd.DataFrame) -> pd.DataFrame:
    sample = df[(df["fyear"] >= 1980) & (df["fyear"] <= 2005) & df["group_id"].isin([1, 2, 3, 4, 5])].copy()
    loss = (
        sample.groupby(["fyear", "group_name"])["loss"]
        .mean()
        .reset_index()
        .rename(columns={"loss": "loss_fraction"})
    )
    loss.to_csv(TABLE_DIR / "figure3_loss_fractions_revision.csv", index=False)
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
    for name in order:
        g = loss[loss["group_name"] == name]
        if g.empty:
            continue
        color, ls = styles[name]
        ax.plot(g["fyear"], g["loss_fraction"], lw=2.0, color=color, ls=ls, label=legend_labels.get(name, name))
    ax.set_xlim(1980, 2005)
    ax.set_ylim(0, 0.9)
    ax.margins(x=0)
    ax.set_title("Figure 3 revision  Fraction of firms reporting adjusted-earnings losses by payout group")
    ax.set_xlabel("Fiscal year")
    ax.set_ylabel("Fraction of firms with adjusted earnings below zero")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _pos: f"{x * 100:.0f}%"))
    ax.grid(axis="y", color=GRID_COLOR, lw=0.6)
    ax.legend(frameon=False, loc="upper left", ncol=2)
    fig.text(
        0.08,
        0.03,
        "Notes: Losses are based on adjusted_earnings = ib - 0.6 x spi.fillna(0).",
        fontsize=8.5,
    )
    fig.tight_layout(rect=(0, 0.06, 1, 0.98))
    return fig


def save_fig(fig: plt.Figure, name: str) -> None:
    fig.savefig(FIGURE_DIR / f"{name}.png", dpi=200)
    fig.savefig(FIGURE_DIR / f"{name}.pdf")


def current_panel_b_adjusted_comparison(after_panel_b: pd.DataFrame, after_groups: pd.DataFrame) -> None:
    current_clean = CURRENT_OUT_DIR / "clean_analysis_firm_years_1970_2005.csv"
    current_groups = CURRENT_OUT_DIR / "firm_groups_1980_2005.csv"
    current_panel_b_source = CURRENT_OUT_DIR / "tables" / "figure2_panel_b_earnings.csv"

    if current_panel_b_source.exists():
        pd.read_csv(current_panel_b_source).to_csv(TABLE_DIR / "figure2_panel_b_before_current_source_data.csv", index=False)

    if current_clean.exists():
        before = pd.read_csv(current_clean)
        before["adjusted_earnings"] = np.where(
            before["ib"].notna(),
            before["ib"] - 0.6 * before["special_items"].fillna(0),
            np.nan,
        )
        before_panel_b = (
            before[
                before["fyear"].between(1980, 2005)
                & before["group_id"].isin([1, 3, 4, 5])
            ]
            .groupby(["fyear", "group_name"])["adjusted_earnings"]
            .apply(sum_observed)
            .reset_index()
            .rename(columns={"adjusted_earnings": "before_adjusted_earnings"})
        )
        comparison = before_panel_b.merge(
            after_panel_b.rename(columns={"earnings": "after_adjusted_earnings"}),
            on=["fyear", "group_name"],
            how="outer",
        )
        comparison["difference_after_minus_before"] = (
            comparison["after_adjusted_earnings"] - comparison["before_adjusted_earnings"]
        )
        comparison.to_csv(TABLE_DIR / "figure2_panel_b_before_after_adjusted_earnings.csv", index=False)

    if current_groups.exists():
        before_groups = pd.read_csv(current_groups)
        before_counts = (
            before_groups[before_groups["group_id"].isin([1, 3, 4, 5])]
            .groupby(["group_id", "group_name"])
            .size()
            .rename("before_firms")
            .reset_index()
        )
        after_counts = (
            after_groups[after_groups["group_id"].isin([1, 3, 4, 5])]
            .groupby(["group_id", "group_name"])
            .size()
            .rename("after_firms")
            .reset_index()
        )
        group_comparison = before_counts.merge(after_counts, on=["group_id", "group_name"], how="outer")
        group_comparison["difference_after_minus_before"] = group_comparison["after_firms"] - group_comparison["before_firms"]
        group_comparison.to_csv(TABLE_DIR / "figure2_panel_b_group_counts_before_after.csv", index=False)


def write_summary(summary: dict[str, float], firm_groups: pd.DataFrame) -> None:
    group_counts = (
        firm_groups.groupby(["group_id", "group_name"], dropna=False)
        .size()
        .rename("firms")
        .reset_index()
    )
    group_counts.to_csv(TABLE_DIR / "figure_revision_group_counts.csv", index=False)
    pd.DataFrame([summary]).to_csv(TABLE_DIR / "figure_revision_sample_audit.csv", index=False)

    lines = [
        "Figure 1-3 isolated revision run",
        "",
        "This script intentionally does not overwrite python_out Figure/Table/Stata artifacts.",
        f"Output directory: {OUTPUT_DIR}",
        "",
        "Core figure-only rules:",
        "- No CRSP/CCM stock screen.",
        "- No curcd == USD hard filter.",
        "- Figure 1 earnings = earnings_raw = ib.",
        "- Figure 1 special items keep spi missing as missing.",
        "- Figure 2 earnings = adjusted_earnings = ib - 0.6 * spi.fillna(0), missing if ib is missing.",
        "- Figure 3 loss = 1[adjusted_earnings < 0].",
        "",
        "Sample audit:",
    ]
    for key, value in summary.items():
        lines.append(f"- {key}: {value:,.0f}")
    lines.append("")
    lines.append("Group counts:")
    for row in group_counts.itertuples(index=False):
        lines.append(f"- {row.group_name}: {row.firms:,.0f}")
    (OUTPUT_DIR / "run_summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ensure_dirs()
    main_df = read_main()
    clean, summary = clean_compustat_for_figures(main_df)
    clean, firm_groups = add_long_run_groups(clean)

    clean_cols = [
        "gvkey",
        "datadate",
        "fyear",
        "sic",
        "sich",
        "sic_use",
        "curcd",
        "dvc",
        "dividend",
        "dividend_dummy",
        "ib",
        "spi",
        "earnings_raw",
        "adjusted_earnings",
        "special_items_figure1",
        "repurchase",
        "repurchase_dummy",
        "repurchase_source",
        "loss",
        "group_id",
        "group_name",
    ]
    clean.loc[clean["fyear"].between(1970, 2005), clean_cols].to_csv(
        OUTPUT_DIR / "figure_revision_clean_firm_years_1970_2005.csv",
        index=False,
    )
    firm_groups.to_csv(OUTPUT_DIR / "figure_revision_firm_groups_1980_2005.csv", index=False)

    fig1_data = build_figure1(clean)
    fig2a_data, fig2b_data = build_figure2(clean)
    fig3_data = build_figure3(clean)
    current_panel_b_adjusted_comparison(fig2b_data, firm_groups)

    fig1 = plot_figure1(fig1_data)
    save_fig(fig1, "figure1_revision")
    plt.close(fig1)

    fig2 = plot_figure2(fig2a_data, fig2b_data)
    save_fig(fig2, "figure2_revision")
    plt.close(fig2)

    fig3 = plot_figure3(fig3_data)
    save_fig(fig3, "figure3_revision")
    plt.close(fig3)

    write_summary(summary, firm_groups)
    print(f"Created isolated Figure 1-3 revision outputs under {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
