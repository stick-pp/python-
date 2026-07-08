# -*- coding: utf-8 -*-
from __future__ import annotations

"""
Skinner（2008）Task 3 复现脚本。

本脚本负责读取并清洗 Compustat、CRSP 和 CCM 数据，构造股利、净股票回购、
盈利、亏损、长期支付组别以及 Table 3 所需的解释变量，并导出正式使用的
Table 1-3、Figure 1-3 及 Python 侧 Logit 回归结果。

主要识别变量包括 Compustat 公司识别码 gvkey、CRSP 证券识别码 permno 和
Compustat 财政年度 fyear。Compustat 金额变量以百万美元为单位。除明确说明
的 SPI 调整外，股利、回购和会计变量的缺失值不自动解释为零。
"""

from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter


###############################################################################
# 第 1 部分：路径配置、输出目录和显示格式
###############################################################################


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent.parent
SHARED_PYTHON_OUT = PROJECT_DIR / "shared_artifacts" / "python_out"
MAIN_CSV = PROJECT_DIR / "maindata.csv"
CCM_LINK_CSV = BASE_DIR / "CCM Link Table.csv"
CRSP_DSE_NAMES_CSV = BASE_DIR / "crsp_dse_names.csv"
OUTPUT_DIR = SHARED_PYTHON_OUT



FIG_DIR = OUTPUT_DIR / "figures"
TABLE_DIR = OUTPUT_DIR / "tables"

PAGE = (11.0, 8.5)
COLOR_EARNINGS = "#1f4e79"
COLOR_SPECIAL = "#8c564b"
COLOR_DIVIDENDS = "#2ca02c"
COLOR_REPURCHASES = "#d62728"
GRID_COLOR = "#d9d9d9"
PDF_METADATA = {"CreationDate": None, "ModDate": None}

GROUP_NAMES = {
    1: "Non-payers",
    2: "Regular div. + regular rep.",
    3: "Occasional rep. only",
    4: "Regular rep. only",
    5: "Dividend-only regular",
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
    for folder in [OUTPUT_DIR, FIG_DIR, TABLE_DIR]:
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


def winsorize_series(series: pd.Series, upper: float = 0.99) -> pd.Series:
    """仅对 Table 3 连续解释变量做 99% 上尾缩尾。"""
    observed = series.dropna()
    if observed.empty:
        return series
    return series.clip(upper=observed.quantile(upper))


def place_xaxis_at_zero(ax: plt.Axes) -> None:
    ax.spines["bottom"].set_position(("data", 0))
    ax.spines["bottom"].set_visible(True)
    ax.spines["top"].set_visible(False)
    ax.xaxis.set_ticks_position("bottom")
    ax.xaxis.set_label_position("bottom")




###############################################################################
# 第 2 部分：读取原始数据并检查输入变量
###############################################################################


def read_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    读取 Task 3 所需的原始 WRDS 文件并做最低限度的结构检查。

    本函数只确认文件存在、关键变量存在，并用 gvkey-datadate 处理合并后主表的
    重复行。实际样本筛选和变量构造放在后续函数中完成，避免在读取阶段混入研究
    口径调整。
    """
    if not MAIN_CSV.exists():
        raise FileNotFoundError(f"Missing main WRDS file: {MAIN_CSV}")
    if not CCM_LINK_CSV.exists():
        raise FileNotFoundError(f"Missing CCM link table: {CCM_LINK_CSV}")
    if not CRSP_DSE_NAMES_CSV.exists():
        raise FileNotFoundError(f"Missing CRSP name history file: {CRSP_DSE_NAMES_CSV}")

    main = pd.read_csv(MAIN_CSV, low_memory=False)
    main = main.drop_duplicates(["gvkey", "datadate"]).copy()
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
        "spi",
        "xintopt",
        "prstkc",
        "sstk",
        "csho",
        "prcc_f",
        "ajex",
    }
    missing_main = sorted(required_main - set(main.columns))
    if missing_main:
        raise ValueError(f"Main CSV is missing variables: {missing_main}")

    if main.duplicated(["gvkey", "datadate"]).any():
        raise ValueError("Main CSV has duplicated gvkey-datadate rows.")
    return main, ccm_link, crsp_names


def parse_wrds_date(series: pd.Series, *, open_ended: bool = False) -> pd.Series:
    """将 WRDS 日期字段转换为 pandas 日期；开放结束日期 E 视为远期有效。"""
    values = series.astype("string").str.strip()
    values = values.mask(values.eq(""))
    if open_ended:
        values = values.replace({"E": "2099-12-31"})
    return pd.to_datetime(values, errors="coerce")


###############################################################################
# 第 3 部分：整理 CCM 链接和 CRSP 名称历史
###############################################################################


def prepare_ccm_link_table(ccm_link: pd.DataFrame) -> pd.DataFrame:
    """
    整理 CCM 链接表，保留可用于 Compustat-CRSP 历史匹配的链接。

    LINKTYPE 保留 LC、LU、LS，LINKPRIM 保留 P、C；这些条件用于减少
    公司到证券映射中的非主要或非标准链接。链接日期在后续匹配时还必须覆盖
    具体财政年度末。
    """
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
    """
    整理 CRSP 名称历史，限定为普通股和主要交易所样本。

    SHRCD 10/11 对应普通股，EXCHCD 1/2/3 对应 NYSE、AMEX 和 NASDAQ。
    名称历史的有效期也会在后续匹配中用于判断财政年度末是否属于该证券记录。
    """
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
) -> pd.DataFrame:
    """
    将 Compustat 公司年度样本限制到可映射的 CRSP 普通股证券。

    只有当 CCM 链接区间和 CRSP 名称历史区间同时覆盖财政年度末时，才保留该
    公司年度观测，避免使用不属于该历史时期的 PERMNO。该筛选用于主样本，
    当前 Figure 2 也沿用这一普通股证券层筛选。
    """
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
    return screened


def apply_table3_past_stock_return_price_only(df: pd.DataFrame) -> pd.DataFrame:
    """
    按原论文 Table 3 口径构造三年股票收益变量。

    仅使用经 AJEX 调整后的 Compustat 财政年度末价格，并要求同一 gvkey 存在
    精确 fyear-3 观测；无法形成价格配对时保持缺失。
    """
    out = df.copy()
    out["_adjusted_price_main"] = np.where(
        out["prcc_f"].notna() & out["prcc_f"].gt(0) & out["ajex"].notna() & out["ajex"].gt(0),
        out["prcc_f"] / out["ajex"],
        np.nan,
    )
    lag_price = out[["gvkey", "fyear", "_adjusted_price_main"]].copy()
    lag_price["fyear"] = lag_price["fyear"] + 3
    lag_price = lag_price.rename(columns={"_adjusted_price_main": "_adjusted_price_lag3_main"})
    out = out.merge(lag_price, on=["gvkey", "fyear"], how="left", validate="one_to_one")

    out["past_stock_return"] = np.where(
        out["_adjusted_price_main"].notna()
        & out["_adjusted_price_lag3_main"].notna()
        & out["_adjusted_price_lag3_main"].gt(0),
        out["_adjusted_price_main"] / out["_adjusted_price_lag3_main"] - 1,
        np.nan,
    )

    return out.drop(columns=["_adjusted_price_main", "_adjusted_price_lag3_main"], errors="ignore")


def add_table3_eso_dilution(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["eso_dilution"] = np.where(
        out["fyear"].ge(1995)
        & out["xintopt"].notna()
        & out["at"].notna()
        & out["at"].gt(0)
        & out["past_stock_return"].notna(),
        (out["xintopt"] / out["at"]) * out["past_stock_return"],
        np.nan,
    )
    return out




###############################################################################
# 第 4 部分：清洗 Compustat 样本并构造支付变量
###############################################################################


def clean_and_construct(
    main: pd.DataFrame,
    ccm_link: pd.DataFrame,
    crsp_names: pd.DataFrame,
    use_crsp_ccm_screen: bool = True,
    build_table3_returns: bool = True,
) -> pd.DataFrame:
    """
    构造公司年度主样本及主要支付变量。

    样本筛选包括 Compustat 合并口径、工业格式、标准数据格式、美元口径、
    美国注册地，以及剔除金融业和公用事业。use_crsp_ccm_screen 为 True 时，
    进一步保留具有有效 CRSP/CCM 普通股链接的公司年度。

    主要变量包括股利、净股票回购、调整后盈利、ROA、现金持有、三年股票收益
    和 ESO dilution。除 SPI 在调整后盈利中按 0 处理外，股利和回购缺失值保留
    为缺失，不自动视为零支付。
    """
    df = main.copy()

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

    format_mask = (
        (df["consol"] == "C")
        & (df["indfmt"] == "INDL")
        & (df["datafmt"] == "STD")
        & (df["curcd"] == "USD")
    )
    df = df[format_mask].copy()

    df = df[df["fic"] == "USA"].copy()

    # 优先使用历史行业代码 SICH；只有 SICH 缺失时才使用 SIC，避免用后期行业
    # 分类代表公司在具体财政年度的行业归属。
    df["sic_use"] = df["sich"].where(df["sich"].notna(), df["sic"])

    # 按 SIC 剔除金融业（6000-6999）和公用事业（4900-4999），保留工业企业
    # 样本以匹配支付政策研究的基本口径。
    df["is_financial"] = df["sic_use"].between(6000, 6999, inclusive="both")
    df["is_utility"] = df["sic_use"].between(4900, 4999, inclusive="both")
    industry_excluded = df["is_financial"] | df["is_utility"]
    df = df[~industry_excluded].copy()

    if use_crsp_ccm_screen:
        df = apply_crsp_ccm_stock_screen(df, ccm_link, crsp_names)

    df = df.sort_values(["gvkey", "fyear", "datadate"]).reset_index(drop=True)
    # DVC 表示普通股现金股利；DVC 缺失时股利状态保持缺失，不作为零股利年份。
    df["dividend"] = df["dvc"]
    df["dividend_dummy"] = np.select(
        [df["dvc"].gt(0), df["dvc"].eq(0)],
        [1.0, 0.0],
        default=np.nan,
    )
    # Figure 1 的特殊项目线保留原始 SPI 缺失；只有 Figure 2/3 使用的调整后盈利
    # 才把缺失 SPI 视为 0。
    df["special_items"] = df["spi"]
    df["spi_for_adjusted_earnings"] = df["spi"].fillna(0)
    df["earnings"] = df["ib"]
    df["adjusted_earnings"] = np.where(
        df["ib"].notna(),
        df["ib"] - 0.6 * df["spi_for_adjusted_earnings"],
        np.nan,
    )

    lag_tstkc = df[["gvkey", "fyear", "tstkc"]].copy()
    lag_tstkc["fyear"] = lag_tstkc["fyear"] + 1
    lag_tstkc = lag_tstkc.rename(columns={"tstkc": "tstkc_lag1"})
    df = df.merge(lag_tstkc, on=["gvkey", "fyear"], how="left", validate="one_to_one")

    # 净股票回购优先使用库存股年度变化。只有当当期和上一期 TSTKC 均可观测时，
    # 才判断公司适用库存股法还是注销法；若 TSTKC 配对缺失，主样本不直接改用
    # PRSTKC - SSTK，以免把无法识别方法的观测误作注销法公司。
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
    # 库存股减少或净发行股票可能使回购测量为负；负值不代表向股东支付的正向回购，
    # 因此按当前口径截断为 0。
    df["repurchase"] = df["repurchase"].replace([np.inf, -np.inf], np.nan).clip(lower=0)
    df["repurchase_dummy"] = np.select(
        [df["repurchase"].gt(0), df["repurchase"].eq(0)],
        [1.0, 0.0],
        default=np.nan,
    )

    # 总支付为现金股利与净股票回购之和；若任一组成变量缺失，保留 pandas 运算
    # 产生的缺失结果，不用填 0 强行构造总支付。
    df["total_payout"] = df["dividend"] + df["repurchase"]
    df["loss"] = np.where(df["earnings"].notna(), (df["earnings"] < 0).astype(float), np.nan)

    lag_at = df[["gvkey", "fyear", "at"]].copy()
    lag_at["fyear"] = lag_at["fyear"] + 1
    lag_at = lag_at.rename(columns={"at": "at_lag1"})
    df = df.merge(lag_at, on=["gvkey", "fyear"], how="left", validate="one_to_one")
    # ROA 使用 OIBDP 除以上一期总资产，现金持有使用 CHE 除以当期总资产。
    # 分母必须为正；资产缺失或非正时，该变量保持缺失。
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
    if build_table3_returns:
        df = apply_table3_past_stock_return_price_only(df)
    else:
        df["past_stock_return"] = np.nan
    # ESO dilution 按 XINTOPT / AT 乘以三年股票收益构造。XINTOPT 主要在 1995
    # 年以后可得，因此 1995 年以前和相关变量缺失时均保留为缺失，不填 0。
    df = add_table3_eso_dilution(df)

    return df


###############################################################################
# 第 5 部分：构造长期支付组别
###############################################################################


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
    """
    在给定窗口内汇总公司层面的股利、回购年份数和支付总额。

    当前窗口进入规则要求：公司至少有 1 年股利状态可观测，且至少有 1 年回购
    状态可观测。其他缺失年份不自动视为零支付年份。
    """
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
    """
    按 1980-2005 年长期支付行为划分公司组别。

    Group I：股利 0 年、回购 0 年；Group II：股利至少 16 年、回购至少 11 年；
    Group III：股利 0 年、回购 1-5 年；Group IV：股利 0 年、回购至少 6 年；
    Group V：回购 0 年、股利至少 6 年。满足进入规则但不属于 I-V 的公司标为 Other。
    """
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




###############################################################################
# 第 6 部分：生成 Figure 1-3 和 Table 1-2
###############################################################################


def build_figure1(df: pd.DataFrame) -> pd.DataFrame:
    """
    生成 Figure 1 的年度汇总数据。

    Figure 1 使用 1970-2005 年主样本，汇总 Compustat IB、特殊项目、现金股利
    和净股票回购，用于展示总体支付和盈利序列。
    """
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
        "Notes: Amounts are in Compustat $ millions. The earnings line uses Compustat ib; special items preserve missing SPI.",
        fontsize=8.5,
    )
    fig.tight_layout(rect=(0, 0.06, 1, 0.98))
    return fig




def table1_window(df: pd.DataFrame, start: int, end: int) -> dict[str, pd.DataFrame]:
    """
    生成 Table 1 单个窗口的股利年份数与回购年份数交叉表。

    窗口进入规则沿用 firm_period_counts：至少有 1 年股利状态和 1 年回购状态
    可观测。输出同时保留计数矩阵、支付额矩阵和用于报告展示的格式化矩阵。
    """
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
    """
    生成 Table 2 的 1980-2005 年长期股利和回购年份数交叉表。

    Table 2 使用长期组别计算时形成的公司层面数据，并保留满足主样本进入规则
    的公司。分类区间与当前代码中的 bucket_table2 保持一致。
    """
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




def build_figure2(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    生成 Figure 2 的 Panel A 和 Panel B 源数据。

    Figure 2 使用与其他正式成果一致的 CRSP/CCM 普通股证券层筛选样本和主样本
    回购定义，按 1980-2005 年长期支付组别汇总调整后盈利 IB - 0.6 * SPI。
    """
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
    panel_b_min = panel_b["earnings"].min(skipna=True)
    panel_b_lower = -80000 if pd.isna(panel_b_min) else min(-80000, np.floor(panel_b_min / 10000) * 10000)
    ax.set_ylim(panel_b_lower, 40000)
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
        "Notes: Groups are based on long-run payout behavior over 1980-2005. Earnings are ib - 0.6 x spi, with missing spi set to zero.",
        fontsize=8.5,
    )
    fig.tight_layout(rect=(0, 0.06, 1, 0.94), h_pad=2.0)
    return fig


def build_figure3(df: pd.DataFrame) -> pd.DataFrame:
    """
    生成 Figure 3 的亏损公司比例源数据。

    Figure 3 使用主样本和 Group I-V 公司，亏损定义为 IB - 0.6 * SPI < 0；
    输出为各长期支付组别在每个财政年度的亏损公司占比。
    """
    sample = df[(df["fyear"] >= 1980) & (df["fyear"] <= 2005) & (df["group_id"].isin([1, 2, 3, 4, 5]))].copy()
    sample["figure3_loss"] = np.where(
        sample["adjusted_earnings"].notna(),
        sample["adjusted_earnings"].lt(0).astype(float),
        np.nan,
    )
    loss = (
        sample.groupby(["fyear", "group_name"])["figure3_loss"]
        .mean()
        .reset_index()
        .rename(columns={"figure3_loss": "loss_fraction"})
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
    ax.set_ylabel("Fraction of firms with negative adjusted earnings")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _pos: f"{x * 100:.0f}%"))
    ax.grid(axis="y", color=GRID_COLOR, lw=0.6)
    if plotted:
        ax.legend(frameon=False, loc="upper left", ncol=2)
    fig.text(
        0.08,
        0.03,
        "Notes: Losses are based on IB - 0.6 x SPI, with missing SPI set to zero. Groups are based on long-run payout behavior over 1980-2005.",
        fontsize=8.5,
    )
    fig.tight_layout(rect=(0, 0.06, 1, 0.98))
    return fig



###############################################################################
# 第 7 部分：可选的 Table 3 Logit 回归
###############################################################################


def build_table3_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    构造 Table 3 Python Logit 回归样本。

    Table 3 仅使用 Group II、III、IV 且年份在 1980-2005 的观测。连续解释变量
    ROA、三年股票收益、现金持有和 ESO dilution 在 99% 分位数做上尾缩尾；
    因变量和组别虚拟变量不缩尾。各模型采用完整样本回归，只有因变量和该模型
    所需解释变量均可观测时才进入对应回归。
    """
    sample = df[(df["fyear"] >= 1980) & (df["fyear"] <= 2005) & (df["group_id"].isin([2, 3, 4]))].copy()
    cols = [
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
    for col in ["roa", "past_stock_return", "cash", "eso_dilution"]:
        reg[col] = winsorize_series(reg[col])
    reg["roa_regular"] = reg["roa"] * reg["regular_dummy"]
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
    return reg


def table3_python_model_specs() -> list[dict[str, object]]:
    """列出 Table 3 六个 Python Logit 模型的样本标记和解释变量。"""
    return [
        {
            "panel": "Panel A",
            "model": "1980-1994",
            "sample_flag": "sample_A_1980_1994",
            "xvars": ["roa", "past_stock_return", "cash"],
            "terms": ["_cons", "roa", "past_stock_return", "cash", "eso_dilution"],
        },
        {
            "panel": "Panel A",
            "model": "1995-2005",
            "sample_flag": "sample_A_1995_2005",
            "xvars": ["roa", "past_stock_return", "cash"],
            "terms": ["_cons", "roa", "past_stock_return", "cash", "eso_dilution"],
        },
        {
            "panel": "Panel A",
            "model": "1995-2005 ESO",
            "sample_flag": "sample_A_1995_2005_eso",
            "xvars": ["roa", "past_stock_return", "cash", "eso_dilution"],
            "terms": ["_cons", "roa", "past_stock_return", "cash", "eso_dilution"],
        },
        {
            "panel": "Panel B",
            "model": "1980-1994",
            "sample_flag": "sample_B_1980_1994",
            "xvars": ["regular_dummy", "roa", "roa_regular", "past_stock_return", "cash"],
            "terms": ["_cons", "regular_dummy", "roa", "roa_regular", "past_stock_return", "cash", "eso_dilution"],
        },
        {
            "panel": "Panel B",
            "model": "1995-2005",
            "sample_flag": "sample_B_1995_2005",
            "xvars": ["regular_dummy", "roa", "roa_regular", "past_stock_return", "cash"],
            "terms": ["_cons", "regular_dummy", "roa", "roa_regular", "past_stock_return", "cash", "eso_dilution"],
        },
        {
            "panel": "Panel B",
            "model": "1995-2005 ESO",
            "sample_flag": "sample_B_1995_2005_eso",
            "xvars": ["regular_dummy", "roa", "roa_regular", "past_stock_return", "cash", "eso_dilution"],
            "terms": ["_cons", "regular_dummy", "roa", "roa_regular", "past_stock_return", "cash", "eso_dilution"],
        },
    ]


def run_table3_python_logit_models(
    reg: pd.DataFrame,
    output_filename: str = "table3_python_logit_results.csv",
) -> pd.DataFrame:
    """
    估计 Table 3 的 Python Logit 模型并导出系数表。

    每个模型先按对应 sample_flag 选择完整样本，再检查因变量是否同时存在 0 和 1。
    若样本为空或只有单一因变量类别，结果中保留状态说明而不强行估计。
    """
    rows: list[dict[str, object]] = []
    for spec in table3_python_model_specs():
        panel = str(spec["panel"])
        model = str(spec["model"])
        sample_flag = str(spec["sample_flag"])
        xvars = list(spec["xvars"])
        terms = list(spec["terms"])

        data = reg.loc[reg[sample_flag].eq(1), ["repurchase_dummy", *xvars]].dropna().copy()
        n = int(len(data))
        y1 = int(data["repurchase_dummy"].sum()) if n else 0
        y0 = int(n - y1)
        result = None
        status = "not_estimated"
        error_message = ""

        if n > 0 and y1 > 0 and y0 > 0:
            try:
                x = sm.add_constant(data[xvars], has_constant="add")
                fitted = sm.Logit(data["repurchase_dummy"], x).fit(disp=False, maxiter=200)
                params = fitted.params.rename(index={"const": "_cons"})
                bse = fitted.bse.rename(index={"const": "_cons"})
                pvalues = fitted.pvalues.rename(index={"const": "_cons"})
                result = {
                    "params": params,
                    "bse": bse,
                    "pvalues": pvalues,
                    "pseudo_r2": float(fitted.prsquared),
                    "converged": bool(fitted.mle_retvals.get("converged", False)),
                }
                status = "estimated"
            except Exception as exc:
                status = "failed"
                error_message = str(exc)
        else:
            error_message = "empty sample or one dependent-variable class"

        for term in terms:
            in_model = term == "_cons" or term in xvars
            if result is not None and in_model:
                coef = result["params"].get(term, np.nan)
                se = result["bse"].get(term, np.nan)
                p = result["pvalues"].get(term, np.nan)
                pseudo_r2 = result["pseudo_r2"]
                converged = result["converged"]
                term_status = status
            else:
                coef = np.nan
                se = np.nan
                p = np.nan
                pseudo_r2 = result["pseudo_r2"] if result is not None else np.nan
                converged = result["converged"] if result is not None else False
                term_status = "not_in_model" if result is not None and not in_model else status

            rows.append(
                {
                    "panel": panel,
                    "model": model,
                    "sample_flag": sample_flag,
                    "term": term,
                    "coef": coef,
                    "se": se,
                    "p": p,
                    "pseudo_r2": pseudo_r2,
                    "N": n,
                    "y1": y1,
                    "y0": y0,
                    "converged": converged,
                    "status": term_status,
                    "error": error_message if term_status == "failed" else "",
                }
            )

    results = pd.DataFrame(rows)
    results.to_csv(TABLE_DIR / output_filename, index=False)
    return results




###############################################################################
# 第 8 部分：保存输出并执行主程序
###############################################################################


def save_fig(fig: plt.Figure, name: str) -> Path:
    """
    同时保存 PNG 和 PDF 图形。

    如果目标文件正在被占用，则尝试使用带编号的替代文件名，避免整个复现程序
    因单个图形文件无法覆盖而中断。
    """
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
        fig.savefig(pdf_path, bbox_inches="tight", metadata=PDF_METADATA)
        return pdf_path
    except PermissionError:
        for i in range(1, 20):
            alt_pdf = FIG_DIR / f"{name}_report_{i}.pdf"
            try:
                fig.savefig(alt_pdf, bbox_inches="tight", metadata=PDF_METADATA)
                return alt_pdf
            except PermissionError:
                continue
        return png_path


def main() -> None:
    """按 Task 3 的研究流程依次生成全部正式输出。"""
    # 第一步：建立输出目录并读取全部原始数据。
    ensure_dirs()

    main_df, ccm_link, crsp_names = read_inputs()
    # 第二步：构造经过 CRSP/CCM 股票层筛选的主样本。
    # 该样本用于 Figure 1、Figure 3、Table 1、Table 2 和 Table 3。
    clean = clean_and_construct(main_df, ccm_link, crsp_names)
    clean, firm_groups = add_long_run_groups(clean)

    # 第三步：生成 Table 1、Table 2 和 Figure 1-3 的正式源数据与图形文件。
    # Figure 2 此处沿用主样本，因而同时使用 CRSP/CCM 筛选和主样本回购 fallback 条件。
    annual = build_figure1(clean)
    table1 = {
        (1980, 1989): table1_window(clean, 1980, 1989),
        (1985, 1994): table1_window(clean, 1985, 1994),
        (1990, 1999): table1_window(clean, 1990, 1999),
        (1995, 2004): table1_window(clean, 1995, 2004),
    }
    build_table1_combined(table1)
    build_table1_paper_panels(table1)
    build_table2(firm_groups)

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

    # 第四步：估计主 Table 3 Python Logit 模型并导出回归结果。
    reg = build_table3_data(clean)
    table3_results = run_table3_python_logit_models(reg)
    print(f"Created core Python replication outputs under {OUTPUT_DIR}")
    print(f"Python Table 3 logit results exported to {TABLE_DIR / 'table3_python_logit_results.csv'}")
    print(f"Python Table 3 coefficient rows: {len(table3_results)}")


if __name__ == "__main__":
    main()
