# -*- coding: utf-8 -*-
from __future__ import annotations

"""
Table 3 稳健性检验 2：仅使用 XINTOPT 覆盖较稳定的 2000-2005 年重新估计 ESO 模型。

本脚本是隔离脚本，不修改 replicate_skinner_2008_V2.py，也不覆盖正式 Table 3 输出。
变量构造、长期组别和 Table 3 缩尾逻辑沿用 V2；这里只改变 ESO 回归的年份窗口。
"""

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm


DIAGNOSTICS_DIR = Path(__file__).resolve().parent
PYTHON_DIR = DIAGNOSTICS_DIR.parent
REPO_DIR = PYTHON_DIR.parent
PROJECT_DIR = REPO_DIR.parent.parent if REPO_DIR.parent.name.lower() == "worktrees" else REPO_DIR
MAIN_SCRIPT = PYTHON_DIR / "replicate_skinner_2008.py"
OUTPUT_DIR = PYTHON_DIR / "diagnostics_outputs" / "table3_robustness_2000_2005"


PANEL_SPECS = [
    {
        "panel": "Panel A",
        "model": "2000-2005 ESO",
        "groups": [2],
        "xvars": ["roa", "past_stock_return", "cash", "eso_dilution"],
    },
    {
        "panel": "Panel B",
        "model": "2000-2005 ESO",
        "groups": [3, 4],
        "xvars": ["regular_dummy", "roa", "roa_regular", "past_stock_return", "cash", "eso_dilution"],
    },
]


def load_main_module():
    spec = importlib.util.spec_from_file_location("skinner_main", MAIN_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["skinner_main"] = module
    spec.loader.exec_module(module)
    return module


def stars(p_value: float) -> str:
    if pd.isna(p_value):
        return ""
    if p_value < 0.01:
        return "*"
    if p_value < 0.05:
        return "†"
    return ""


def run_logit(data: pd.DataFrame, xvars: list[str]) -> tuple[pd.DataFrame, dict[str, object]]:
    cols = ["repurchase_dummy"] + xvars
    sample = data[cols].replace([np.inf, -np.inf], np.nan).dropna().copy()
    sample = sample[sample["repurchase_dummy"].isin([0, 1])].copy()
    meta = {
        "nobs": int(len(sample)),
        "y1": int(sample["repurchase_dummy"].eq(1).sum()),
        "y0": int(sample["repurchase_dummy"].eq(0).sum()),
        "pseudo_r2": np.nan,
        "status": "not_estimated",
    }
    if sample.empty or sample["repurchase_dummy"].nunique() < 2:
        return pd.DataFrame(), meta

    x = sm.add_constant(sample[xvars], has_constant="add")
    result = sm.Logit(sample["repurchase_dummy"], x).fit(disp=False, maxiter=200)
    meta["pseudo_r2"] = float(result.prsquared)
    meta["status"] = "estimated"

    rows = []
    for term in ["const"] + xvars:
        p_value = result.pvalues.get(term, np.nan)
        rows.append(
            {
                "term": term,
                "coef": result.params.get(term, np.nan),
                "se": result.bse.get(term, np.nan),
                "z": result.tvalues.get(term, np.nan),
                "p": p_value,
                "stars": stars(p_value),
            }
        )
    return pd.DataFrame(rows), meta


def build_audit_rows(reg: pd.DataFrame) -> list[dict[str, object]]:
    rows = []
    for spec in PANEL_SPECS:
        panel_mask = reg["group_id"].isin(spec["groups"]) & reg["fyear"].between(2000, 2005)
        valid_y = reg["repurchase_dummy"].isin([0, 1])
        base_vars = ["roa", "past_stock_return", "cash"]
        if spec["panel"] == "Panel B":
            base_vars = ["regular_dummy", "roa", "roa_regular", "past_stock_return", "cash"]

        base_mask = panel_mask & valid_y & reg[base_vars].notna().all(axis=1)
        eso_mask = base_mask & reg["eso_dilution"].notna()
        rows.append(
            {
                "panel": spec["panel"],
                "model": spec["model"],
                "base_2000_2005_N": int(base_mask.sum()),
                "eso_2000_2005_N": int(eso_mask.sum()),
                "lost_due_to_missing_eso": int(base_mask.sum() - eso_mask.sum()),
                "eso_retention_rate": eso_mask.sum() / base_mask.sum() if base_mask.sum() else np.nan,
                "y1": int(reg.loc[eso_mask, "repurchase_dummy"].eq(1).sum()),
                "y0": int(reg.loc[eso_mask, "repurchase_dummy"].eq(0).sum()),
            }
        )
    return rows


def format_coef_table(results: pd.DataFrame) -> pd.DataFrame:
    order = ["const", "regular_dummy", "roa", "roa_regular", "past_stock_return", "cash", "eso_dilution"]
    labels = {
        "const": "Constant",
        "regular_dummy": "Regular dummy",
        "roa": "ROA",
        "roa_regular": "ROA × Regular",
        "past_stock_return": "Past stock return",
        "cash": "Cash",
        "eso_dilution": "ESO dilution",
    }
    out = results.copy()
    out["term_order"] = out["term"].map({term: i for i, term in enumerate(order)})
    out["variable"] = out["term"].map(labels).fillna(out["term"])
    out["coef_se"] = out.apply(
        lambda r: f"{r['coef']:.3f}{r['stars']} ({r['se']:.3f})" if pd.notna(r["coef"]) else "",
        axis=1,
    )
    return out.sort_values(["panel", "term_order"])[["panel", "model", "variable", "coef_se", "p"]]


def write_markdown(results: pd.DataFrame, audit: pd.DataFrame, path: Path) -> None:
    display = format_coef_table(results)
    text = [
        "# Table 3 稳健性检验 2：2000-2005 ESO 模型",
        "",
        "本稳健性检验仅使用 XINTOPT 覆盖较稳定的 2000-2005 年重新估计 ESO 模型。",
        "变量构造、长期支付组别和连续变量上尾缩尾逻辑沿用 `replicate_skinner_2008_V2.py`。",
        "",
        "## 样本覆盖",
        "",
        audit.to_markdown(index=False),
        "",
        "## 回归结果",
        "",
        display.to_markdown(index=False),
        "",
        "注：括号内为 Python logit 标准误。* 表示 1% 显著，† 表示 5% 显著。",
        "",
    ]
    path.write_text("\n".join(text), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    main_module = load_main_module()
    main_df, ccm_link, crsp_names = main_module.read_inputs()
    clean = main_module.clean_and_construct(main_df, ccm_link, crsp_names)
    clean, _firm_groups = main_module.add_long_run_groups(clean)
    reg = v2.build_table3_data(clean).reset_index(drop=False).rename(columns={"index": "row_id"})

    audit = pd.DataFrame(build_audit_rows(reg))
    result_rows = []
    for spec in PANEL_SPECS:
        panel_mask = reg["group_id"].isin(spec["groups"]) & reg["fyear"].between(2000, 2005)
        valid_y = reg["repurchase_dummy"].isin([0, 1])
        xvars = spec["xvars"]
        model_mask = panel_mask & valid_y & reg[xvars].notna().all(axis=1)
        estimates, meta = run_logit(reg[model_mask], xvars)
        if estimates.empty:
            result_rows.append(
                {
                    "panel": spec["panel"],
                    "model": spec["model"],
                    "term": "",
                    "coef": np.nan,
                    "se": np.nan,
                    "z": np.nan,
                    "p": np.nan,
                    "stars": "",
                    **meta,
                }
            )
        else:
            for _, row in estimates.iterrows():
                result_rows.append({"panel": spec["panel"], "model": spec["model"], **row.to_dict(), **meta})

    results = pd.DataFrame(result_rows)
    results_path = OUTPUT_DIR / "table3_robustness_2000_2005_eso_results.csv"
    audit_path = OUTPUT_DIR / "table3_robustness_2000_2005_eso_sample_audit.csv"
    md_path = OUTPUT_DIR / "table3_robustness_2000_2005_eso.md"
    results.to_csv(results_path, index=False)
    audit.to_csv(audit_path, index=False)
    write_markdown(results, audit, md_path)
    print(f"Wrote {results_path}")
    print(f"Wrote {audit_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
