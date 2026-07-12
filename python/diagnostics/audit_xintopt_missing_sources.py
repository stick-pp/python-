# -*- coding: utf-8 -*-
from __future__ import annotations

"""
XINTOPT 缺失来源审计表。

本脚本独立于主复现脚本运行，只读取现有输入数据和 replicate_skinner_2008_V2.py
中的清洗/分组函数，生成 Table 3 的 1995-2005 ESO 样本逐步进入口径审计表。
"""

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd


DIAGNOSTICS_DIR = Path(__file__).resolve().parent
PYTHON_DIR = DIAGNOSTICS_DIR.parent
REPO_DIR = PYTHON_DIR.parent
PROJECT_DIR = REPO_DIR.parent.parent if REPO_DIR.parent.name.lower() == "worktrees" else REPO_DIR
TABLE_DIR = PYTHON_DIR / "diagnostics_outputs" / "xintopt_missing_audit"
MAIN_SCRIPT = PYTHON_DIR / "replicate_skinner_2008.py"


def load_main_module():
    spec = importlib.util.spec_from_file_location("skinner_main", MAIN_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["skinner_main"] = module
    spec.loader.exec_module(module)
    return module


def count_rows(mask: pd.Series) -> int:
    return int(mask.fillna(False).sum())


def make_step(step: int, name: str, count: int, previous: int | None) -> dict[str, object]:
    dropped = 0 if previous is None else previous - count
    retained_rate = np.nan if previous in (None, 0) else count / previous
    cumulative_rate = np.nan if make_step.base_count in (None, 0) else count / make_step.base_count
    return {
        "step": step,
        "condition": name,
        "firm_years": count,
        "dropped_from_previous": dropped,
        "retained_rate_from_previous": retained_rate,
        "cumulative_rate_from_first_step": cumulative_rate,
    }


make_step.base_count = None


def audit_chain(raw: pd.DataFrame, clean: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    work = clean.copy()

    raw_1995_2005 = raw[pd.to_numeric(raw["fyear"], errors="coerce").between(1995, 2005)].copy()
    raw_1995_2005["sic_use"] = pd.to_numeric(raw_1995_2005["sich"], errors="coerce").where(
        pd.to_numeric(raw_1995_2005["sich"], errors="coerce").notna(),
        pd.to_numeric(raw_1995_2005["sic"], errors="coerce"),
    )
    standard_industrial = (
        raw_1995_2005["consol"].eq("C")
        & raw_1995_2005["indfmt"].eq("INDL")
        & raw_1995_2005["datafmt"].eq("STD")
        & raw_1995_2005["curcd"].eq("USD")
        & raw_1995_2005["fic"].eq("USA")
        & ~raw_1995_2005["sic_use"].between(6000, 6999, inclusive="both")
        & ~raw_1995_2005["sic_use"].between(4900, 4999, inclusive="both")
    )

    in_1995_2005 = work["fyear"].between(1995, 2005)
    target_groups = work["group_id"].isin([2, 3, 4])
    rep_valid = work["repurchase_dummy"].isin([0, 1])
    roa_valid = work["roa"].notna()
    return_valid = work["past_stock_return"].notna()
    cash_valid = work["cash"].notna()
    at_positive = work["at"].notna() & work["at"].gt(0)
    xintopt_valid = work["xintopt"].notna()
    eso_valid = work["eso_dilution"].notna()

    steps = [
        ("1995-2005 所有 Compustat 公司年", len(raw_1995_2005)),
        ("满足 C/INDL/STD、USD、USA、非金融非公用事业", count_rows(standard_industrial)),
        ("Group II / III / IV（当前 CRSP/CCM 主样本分组后）", count_rows(in_1995_2005 & target_groups)),
        ("repurchase_dummy 有效", count_rows(in_1995_2005 & target_groups & rep_valid)),
        ("ROA 有效", count_rows(in_1995_2005 & target_groups & rep_valid & roa_valid)),
        (
            "past_stock_return 有效",
            count_rows(in_1995_2005 & target_groups & rep_valid & roa_valid & return_valid),
        ),
        (
            "cash 有效",
            count_rows(in_1995_2005 & target_groups & rep_valid & roa_valid & return_valid & cash_valid),
        ),
        (
            "at > 0",
            count_rows(
                in_1995_2005
                & target_groups
                & rep_valid
                & roa_valid
                & return_valid
                & cash_valid
                & at_positive
            ),
        ),
        (
            "xintopt 非缺失",
            count_rows(
                in_1995_2005
                & target_groups
                & rep_valid
                & roa_valid
                & return_valid
                & cash_valid
                & at_positive
                & xintopt_valid
            ),
        ),
        (
            "final ESO sample（含 at>0 审计口径）",
            count_rows(
                in_1995_2005
                & target_groups
                & rep_valid
                & roa_valid
                & return_valid
                & cash_valid
                & at_positive
                & xintopt_valid
                & eso_valid
            ),
        ),
    ]

    make_step.base_count = steps[0][1]
    previous = None
    total_rows = []
    for i, (name, count) in enumerate(steps, start=1):
        total_rows.append(make_step(i, name, count, previous))
        previous = count

    panel_rows = []
    panel_defs = [
        ("Panel A: Group II", work["group_id"].eq(2)),
        ("Panel B: Group III/IV", work["group_id"].isin([3, 4])),
    ]
    panel_conditions = [
        ("Group II / III / IV", in_1995_2005 & target_groups),
        ("repurchase_dummy 有效", in_1995_2005 & target_groups & rep_valid),
        ("ROA 有效", in_1995_2005 & target_groups & rep_valid & roa_valid),
        ("past_stock_return 有效", in_1995_2005 & target_groups & rep_valid & roa_valid & return_valid),
        ("cash 有效", in_1995_2005 & target_groups & rep_valid & roa_valid & return_valid & cash_valid),
        (
            "at > 0",
            in_1995_2005 & target_groups & rep_valid & roa_valid & return_valid & cash_valid & at_positive,
        ),
        (
            "xintopt 非缺失",
            in_1995_2005
            & target_groups
            & rep_valid
            & roa_valid
            & return_valid
            & cash_valid
            & at_positive
            & xintopt_valid,
        ),
        (
            "final ESO sample（含 at>0 审计口径）",
            in_1995_2005
            & target_groups
            & rep_valid
            & roa_valid
            & return_valid
            & cash_valid
            & at_positive
            & xintopt_valid
            & eso_valid,
        ),
    ]
    for panel, panel_mask in panel_defs:
        previous = None
        first = None
        for i, (name, mask) in enumerate(panel_conditions, start=1):
            count = count_rows(mask & panel_mask)
            if first is None:
                first = count
            panel_rows.append(
                {
                    "panel": panel,
                    "step": i,
                    "condition": name,
                    "firm_years": count,
                    "dropped_from_previous": 0 if previous is None else previous - count,
                    "retained_rate_from_previous": np.nan if previous in (None, 0) else count / previous,
                    "cumulative_rate_from_panel_first_step": np.nan if first in (None, 0) else count / first,
                }
            )
            previous = count

    return pd.DataFrame(total_rows), pd.DataFrame(panel_rows)


def write_markdown(total: pd.DataFrame, panel: pd.DataFrame, path: Path) -> None:
    text = [
        "# XINTOPT 缺失来源审计表",
        "",
        "本表用于审计 Table 3 的 1995-2005 ESO 样本从 Compustat 公司年到最终样本的逐步流失。",
        "脚本只做审计，不修改主复现脚本或正式回归结果。",
        "",
        "## 总样本逐步审计",
        "",
        total.to_markdown(index=False),
        "",
        "## Panel A / Panel B 分组审计",
        "",
        panel.to_markdown(index=False),
        "",
        "说明：`at > 0` 与 V2 当前正式 ESO dilution 计算口径一致，即 `xintopt / at * past_stock_return`。",
        "",
    ]
    path.write_text("\n".join(text), encoding="utf-8")


def main() -> None:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    main_module = load_main_module()
    raw, ccm_link, crsp_names = main_module.read_inputs()
    clean = main_module.clean_and_construct(raw, ccm_link, crsp_names)
    clean, _firm_groups = main_module.add_long_run_groups(clean)

    total, panel = audit_chain(raw, clean)
    total_path = TABLE_DIR / "xintopt_missing_source_audit_total.csv"
    panel_path = TABLE_DIR / "xintopt_missing_source_audit_by_panel.csv"
    md_path = TABLE_DIR / "xintopt_missing_source_audit.md"
    total.to_csv(total_path, index=False)
    panel.to_csv(panel_path, index=False)
    write_markdown(total, panel, md_path)

    print(f"Wrote {total_path}")
    print(f"Wrote {panel_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
