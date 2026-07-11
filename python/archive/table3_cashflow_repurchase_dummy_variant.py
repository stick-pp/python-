from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

import replicate_skinner_2008 as base


VARIANT_DIR = base.OUTPUT_DIR / "table3_cashflow_repurchase_dummy"
VARIANT_DIR.mkdir(parents=True, exist_ok=True)

PUBLISHED_TABLE3_N = base.PUBLISHED_TABLE3_N


def build_table3_variant_data(clean: pd.DataFrame) -> pd.DataFrame:
    df = clean.copy()
    cashflow_available_not_used = df["repurchase_source"].eq("missing_tstkc_pair_cashflow_available_not_used")
    cashflow_complete = df["prstkc"].notna() & df["sstk"].notna()
    cashflow_variant = cashflow_available_not_used & cashflow_complete

    df["repurchase_strict"] = df["repurchase"]
    df["repurchase_dummy_strict"] = df["repurchase_dummy"]
    df["repurchase_table3_cashflow"] = df["repurchase"]
    df.loc[cashflow_variant, "repurchase_table3_cashflow"] = (
        df.loc[cashflow_variant, "prstkc"] - df.loc[cashflow_variant, "sstk"]
    )
    df["repurchase_table3_cashflow"] = (
        df["repurchase_table3_cashflow"].replace([np.inf, -np.inf], np.nan).clip(lower=0)
    )
    df["repurchase_dummy_table3_cashflow"] = np.select(
        [df["repurchase_table3_cashflow"].gt(0), df["repurchase_table3_cashflow"].eq(0)],
        [1.0, 0.0],
        default=np.nan,
    )
    df["repurchase_source_table3"] = df["repurchase_source"]
    df.loc[cashflow_variant, "repurchase_source_table3"] = "cashflow_method_for_table3_y_only"

    sample = df[(df["fyear"] >= 1980) & (df["fyear"] <= 2005) & (df["group_id"].isin([2, 3, 4]))].copy()
    cols = [
        "gvkey",
        "fyear",
        "group_id",
        "repurchase_dummy_table3_cashflow",
        "repurchase_dummy_strict",
        "repurchase_table3_cashflow",
        "repurchase_strict",
        "repurchase_source_table3",
        "regular_dummy",
        "roa",
        "roa_regular",
        "past_stock_return",
        "cash",
        "eso_dilution",
    ]
    reg = sample[cols].replace([np.inf, -np.inf], np.nan).copy()
    reg = reg.rename(columns={"repurchase_dummy_table3_cashflow": "repurchase_dummy"})
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
    return reg


def table3_model_specs(reg: pd.DataFrame):
    return [
        ("Panel A", "1980-1994", reg[reg["sample_A_1980_1994"].eq(1)], ["roa", "past_stock_return", "cash"]),
        ("Panel A", "1995-2005", reg[reg["sample_A_1995_2005"].eq(1)], ["roa", "past_stock_return", "cash"]),
        (
            "Panel A",
            "1995-2005 ESO",
            reg[reg["sample_A_1995_2005_eso"].eq(1)],
            ["roa", "past_stock_return", "cash", "eso_dilution"],
        ),
        (
            "Panel B",
            "1980-1994",
            reg[reg["sample_B_1980_1994"].eq(1)],
            ["regular_dummy", "roa", "roa_regular", "past_stock_return", "cash"],
        ),
        (
            "Panel B",
            "1995-2005",
            reg[reg["sample_B_1995_2005"].eq(1)],
            ["regular_dummy", "roa", "roa_regular", "past_stock_return", "cash"],
        ),
        (
            "Panel B",
            "1995-2005 ESO",
            reg[reg["sample_B_1995_2005_eso"].eq(1)],
            ["regular_dummy", "roa", "roa_regular", "past_stock_return", "cash", "eso_dilution"],
        ),
    ]


def fit_python_logit(reg: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for panel, model, data, xvars in table3_model_specs(reg):
        work = data[["repurchase_dummy"] + xvars].replace([np.inf, -np.inf], np.nan).dropna().copy()
        work = work[work["repurchase_dummy"].isin([0, 1])]
        y = work["repurchase_dummy"].astype(float)
        x = sm.add_constant(work[xvars].astype(float), has_constant="add")
        result = sm.Logit(y, x).fit(disp=False, maxiter=200)
        rows.append(
            {
                "panel": panel,
                "model": model,
                "N": int(result.nobs),
                "y1": int(y.sum()),
                "y0": int(len(y) - y.sum()),
                "pseudo_r2": result.prsquared,
                **{f"coef_{name}": result.params.get(name, np.nan) for name in x.columns},
                **{f"se_{name}": result.bse.get(name, np.nan) for name in x.columns},
                "published_N": PUBLISHED_TABLE3_N[(panel, model)],
                "N_minus_published": int(result.nobs) - PUBLISHED_TABLE3_N[(panel, model)],
            }
        )
    return pd.DataFrame(rows)


def write_stata_do() -> Path:
    dta_path = (VARIANT_DIR / "table3_regression_data_cashflow_y.dta").as_posix()
    results_path = (VARIANT_DIR / "table3_stata_results_cashflow_y.dta").as_posix()
    csv_path = (VARIANT_DIR / "table3_stata_results_cashflow_y.csv").as_posix()
    log_path = (VARIANT_DIR / "table3_stata_cashflow_y.log").as_posix()
    do_path = VARIANT_DIR / "table3_cashflow_y.do"
    do_path.write_text(
        f"""
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
""".strip(),
        encoding="utf-8",
    )
    return do_path


def main() -> None:
    main_df, ajex_df, ccm_link, crsp_names, past_stock_prices = base.read_inputs()
    clean, _summary = base.clean_and_construct(main_df, ajex_df, ccm_link, crsp_names, past_stock_prices)
    clean, firm_groups = base.add_long_run_groups(clean)
    reg = build_table3_variant_data(clean)

    reg.to_csv(VARIANT_DIR / "table3_regression_data_cashflow_y.csv", index=False)
    reg.to_stata(VARIANT_DIR / "table3_regression_data_cashflow_y.dta", write_index=False, version=118)

    sample_counts = []
    for panel, model, data, xvars in table3_model_specs(reg):
        work = data[["repurchase_dummy"] + xvars].replace([np.inf, -np.inf], np.nan).dropna()
        work = work[work["repurchase_dummy"].isin([0, 1])]
        published_n = PUBLISHED_TABLE3_N[(panel, model)]
        sample_counts.append(
            {
                "panel": panel,
                "model": model,
                "current_N": len(work),
                "published_N": published_n,
                "difference": len(work) - published_n,
                "pct_gap_vs_published": (len(work) - published_n) / published_n * 100,
                "y1": int(work["repurchase_dummy"].sum()) if len(work) else 0,
                "y0": int(len(work) - work["repurchase_dummy"].sum()) if len(work) else 0,
            }
        )
    pd.DataFrame(sample_counts).to_csv(VARIANT_DIR / "table3_sample_counts_cashflow_y.csv", index=False)

    source_counts = (
        reg["repurchase_source_table3"].fillna("unassigned").value_counts().rename_axis("repurchase_source_table3").reset_index(name="rows")
    )
    source_counts.to_csv(VARIANT_DIR / "table3_repurchase_source_cashflow_y_counts.csv", index=False)

    python_results = fit_python_logit(reg)
    python_results.to_csv(VARIANT_DIR / "table3_python_logit_results_cashflow_y.csv", index=False)
    write_stata_do()

    print(f"Created isolated Table 3 cashflow-y variant under {VARIANT_DIR}")
    print((VARIANT_DIR / "table3_sample_counts_cashflow_y.csv").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
