from __future__ import annotations

import csv
import math
from pathlib import Path


LATEX_SRC_DIR = Path(__file__).resolve().parent
WORKTREE_DIR = LATEX_SRC_DIR.parent
ROOT = WORKTREE_DIR.parents[1] if WORKTREE_DIR.parent.name == "worktrees" else WORKTREE_DIR
PY_OUT = ROOT / "shared_artifacts" / "python_out"
LATEX_OUT = ROOT / "shared_artifacts" / "latex_out"
BUILD_DIR = WORKTREE_DIR / "build_report"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def read_table2(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    return ["Repurchase years"] + rows[0][1:], [[r[0]] + r[1:] for r in rows[1:]]


def esc(value: object) -> str:
    text = "" if value is None else str(value)
    repl = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(repl.get(ch, ch) for ch in text)


def cell(value: str) -> str:
    return r"\makecell{" + esc(value).replace("\r\n", "\n").replace("\r", "\n").replace("\n", r"\\") + "}"


def raw_cell(value: str) -> str:
    return r"\makecell{" + value.replace("\r\n", "\n").replace("\r", "\n").replace("\n", r"\\") + "}"


def note(text: str) -> str:
    return r"\vspace{2pt}\parbox{0.94\textwidth}{\footnotesize 注：" + text + "}"


def table1(rows: list[dict[str, str]], caption: str) -> str:
    cols = ["0", "1-4", "5-9", "10", "Sum"]
    out = [
        r"\begin{table}[H]",
        r"\centering",
        rf"\caption{{{caption}}}",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{4pt}",
        r"\renewcommand{\arraystretch}{1.10}",
        r"\begin{tabular}{lccccc}",
        r"\toprule",
        r"& \multicolumn{5}{c}{Dividend payment years} \\",
        r"\cmidrule(lr){2-6}",
        "Repurchase years & " + " & ".join(cols) + r" \\",
        r"\midrule",
    ]
    for row in rows:
        label = row["row_label"]
        if "\n" in label:
            window, label = label.split("\n", 1)
            out.append(r"\multicolumn{6}{l}{\textit{" + esc(window) + r"}} \\")
        out.append(" & ".join([esc(label)] + [cell(row[c]) for c in cols]) + r" \\")
        if label == "Sum":
            out.append(r"\addlinespace")
    out += [
        r"\bottomrule",
        r"\end{tabular}",
        note("单元格上方为公司数或支付总额，括号内为对应窗口占比。行表示回购年数，列表示股利支付年数。"),
        r"\end{table}",
    ]
    return "\n".join(out)


def table2(headers: list[str], rows: list[list[str]]) -> str:
    out = [
        r"\begin{table}[H]",
        r"\centering",
        r"\caption{Table 2. Number of firms by dividend and repurchase payment years, 1980--2005}",
        r"\small",
        r"\setlength{\tabcolsep}{5pt}",
        r"\begin{tabular}{lrrrrrrr}",
        r"\toprule",
        r"& \multicolumn{7}{c}{Dividend payment years} \\",
        r"\cmidrule(lr){2-8}",
        " & ".join(esc(h) for h in headers) + r" \\",
        r"\midrule",
    ]
    out += [" & ".join(esc(x) for x in row) + r" \\" for row in rows]
    out += [
        r"\bottomrule",
        r"\end{tabular}",
        note("行表示 1980--2005 年期间的回购年数，列表示股利支付年数。"),
        r"\end{table}",
    ]
    return "\n".join(out)


LABELS = {
    "_cons": "Constant",
    "regular_dummy": "Regular dummy",
    "roa": "ROA",
    "roa_regular": r"ROA $\times$ Regular",
    "past_stock_return": "Past stock return",
    "cash": "Cash",
    "eso_dilution": "ESO dilution",
}

PUBLISHED_N = {
    ("Panel A", "1980-1994"): 4801,
    ("Panel A", "1995-2005"): 3510,
    ("Panel A", "1995-2005 ESO"): 3173,
    ("Panel B", "1980-1994"): 11581,
    ("Panel B", "1995-2005"): 15279,
    ("Panel B", "1995-2005 ESO"): 12965,
}


def fmt(value: str) -> str:
    if value == "":
        return ""
    number = float(value)
    if math.isclose(number, 0.0, abs_tol=0.0005):
        number = 0.0
    return f"{number:.3f}"


def mark(p: str) -> str:
    if not p:
        return ""
    value = float(p)
    if value < 0.01:
        return r"\textsuperscript{*}"
    if value < 0.05:
        return r"\textsuperscript{\(\dagger\)}"
    return ""


def table3(rows: list[dict[str, str]], panel: str, caption: str, terms: list[str]) -> str:
    models = ["1980-1994", "1995-2005", "1995-2005 ESO"]
    keyed = {(r["model"], r["term"]): r for r in rows if r["panel"] == panel}
    first = {m: next(r for r in rows if r["panel"] == panel and r["model"] == m) for m in models}
    out = [
        r"\begin{table}[H]",
        r"\centering",
        rf"\caption{{{caption}}}",
        r"\small",
        r"\setlength{\tabcolsep}{7pt}",
        r"\renewcommand{\arraystretch}{1.10}",
        r"\begin{tabular}{lccc}",
        r"\toprule",
        " & ".join(["", *models]) + r" \\",
        r"\midrule",
    ]
    for term in terms:
        row_cells = [LABELS[term]]
        for model in models:
            row = keyed.get((model, term))
            if row is None or row["coef"] == "":
                row_cells.append("")
            else:
                row_cells.append(fmt(row["coef"]) + mark(row["p"]) + "\n" + f"({fmt(row['se'])})")
        out.append(" & ".join([row_cells[0]] + [raw_cell(c) if c else "" for c in row_cells[1:]]) + r" \\")
    out += [
        r"\midrule",
        "Observations & " + " & ".join(f'{int(float(first[m]["N"])):,}' for m in models) + r" \\",
        "Published N & " + " & ".join(f"{PUBLISHED_N[(panel, m)]:,}" for m in models) + r" \\",
        r"Pseudo $R^2$ & " + " & ".join(fmt(first[m]["pseudo_r2"]) for m in models) + r" \\",
        r"\bottomrule",
        r"\end{tabular}",
        note(r"括号内为 Python logit 标准误。* 表示 1\% 显著，\(\dagger\) 表示 5\% 显著。"),
        r"\end{table}",
    ]
    return "\n".join(out)


def pct(value: str) -> str:
    return f"{float(value) * 100:.1f}\\%"


def table3_robust_audit(rows: list[dict[str, str]]) -> str:
    out = [
        r"\begin{table}[H]",
        r"\centering",
        r"\caption{Table 3 robustness audit. XINTOPT coverage before and after 2000}",
        r"\small",
        r"\setlength{\tabcolsep}{5pt}",
        r"\renewcommand{\arraystretch}{1.10}",
        r"\begin{tabular}{llrrrr}",
        r"\toprule",
        r"Panel & Period & Base N & ESO N & Missing ESO & Retention \\",
        r"\midrule",
    ]
    for row in rows:
        out.append(
            " & ".join(
                [
                    esc(row["panel"]),
                    esc(row["period"]),
                    f'{int(float(row["base_N"])):,}',
                    f'{int(float(row["eso_N"])):,}',
                    f'{int(float(row["lost_due_to_missing_eso"])):,}',
                    pct(row["xintopt_eso_retention_rate"]),
                ]
            )
            + r" \\"
        )
    out += [
        r"\bottomrule",
        r"\end{tabular}",
        note("Retention 为加入 XINTOPT/ESO 变量后保留的样本比例。2000--2005 年覆盖率显著高于 1995--1999 年。"),
        r"\end{table}",
    ]
    return "\n".join(out)


def table3_robust_regression(rows: list[dict[str, str]]) -> str:
    terms = ["_cons", "regular_dummy", "roa", "roa_regular", "past_stock_return", "cash", "eso_dilution"]
    keyed = {(r["panel"], r["term"]): r for r in rows}
    first = {panel: next(r for r in rows if r["panel"] == panel) for panel in ["Panel A", "Panel B"]}
    out = [
        r"\begin{table}[H]",
        r"\centering",
        r"\caption{Table 3 robustness 2. ESO logit regressions in 2000--2005}",
        r"\small",
        r"\setlength{\tabcolsep}{7pt}",
        r"\renewcommand{\arraystretch}{1.10}",
        r"\begin{tabular}{lcc}",
        r"\toprule",
        r" & Panel A & Panel B \\",
        r"\midrule",
    ]
    for term in terms:
        cells = [LABELS[term]]
        for panel in ["Panel A", "Panel B"]:
            row = keyed.get((panel, term))
            if row is None or row["coef"] == "":
                cells.append("")
            else:
                cells.append(fmt(row["coef"]) + mark(row["p"]) + "\n" + f"({fmt(row['se'])})")
        out.append(" & ".join([cells[0]] + [raw_cell(c) if c else "" for c in cells[1:]]) + r" \\")
    out += [
        r"\midrule",
        "Observations & " + " & ".join(f'{int(float(first[p]["N"])):,}' for p in ["Panel A", "Panel B"]) + r" \\",
        r"Pseudo $R^2$ & " + " & ".join(fmt(first[p]["pseudo_r2"]) for p in ["Panel A", "Panel B"]) + r" \\",
        r"\bottomrule",
        r"\end{tabular}",
        note(r"括号内为 Python logit 标准误。* 表示 1\% 显著，\(\dagger\) 表示 5\% 显著。该稳健性检验仅使用 XINTOPT 覆盖较稳定的 2000--2005 年样本，不替代主回归。"),
        r"\end{table}",
    ]
    return "\n".join(out)


def build_tex() -> str:
    t1a = table1(read_csv(PY_OUT / "tables" / "table1_panel_a_counts_display.csv"), "Table 1, Panel A. Firm counts by dividend and repurchase payment years")
    t1b = table1(read_csv(PY_OUT / "tables" / "table1_panel_b_payouts_display.csv"), "Table 1, Panel B. Aggregate payout amounts by dividend and repurchase payment years")
    h2, r2 = read_table2(PY_OUT / "tables" / "table2_counts_1980_2005.csv")
    t2 = table2(h2, r2)
    srows = read_csv(PY_OUT / "tables" / "table3_python_logit_results.csv")
    t3a = table3(srows, "Panel A", "Table 3, Panel A. Logit regressions for regular dividend and regular repurchase firms", ["_cons", "roa", "past_stock_return", "cash", "eso_dilution"])
    t3b = table3(srows, "Panel B", "Table 3, Panel B. Logit regressions for repurchase-only firms", ["_cons", "regular_dummy", "roa", "roa_regular", "past_stock_return", "cash", "eso_dilution"])
    robust_audit = table3_robust_audit(read_csv(PY_OUT / "tables" / "table3_robustness_2000_2005_eso_sample_audit.csv"))
    robust_reg = table3_robust_regression(read_csv(PY_OUT / "tables" / "table3_robustness_2000_2005_eso_results.csv"))
    return rf"""\documentclass[lang=cn,a4paper]{{elegantpaper}}
\usepackage{{booktabs}}
\usepackage{{makecell}}
\usepackage{{graphicx}}
\usepackage{{float}}
\usepackage{{placeins}}
\usepackage{{caption}}
\captionsetup{{font=small,labelfont=bf}}

\title{{Skinner (2008) 企业支付政策论文复现报告}}
\author{{Python 课程期末项目}}
\institute{{Nankai University}}
\date{{2026 年 7 月}}

\begin{{document}}
\maketitle
\begin{{abstract}}
本文复现 Skinner (2008) 关于美国企业支付政策变化的核心图表与回归结果。复现使用 Compustat Annual 数据，并结合 CRSP/CCM 普通股层面筛选，构造现金股利、净股票回购、长期支付组别和 Table 3 回归变量。报告重点复现 Figure 1--3、Table 1--3，并比较当前结果与原论文之间的主要差异。
\keywords{{Skinner (2008), 支付政策, 现金股利, 股票回购, 论文复现}}
\end{{abstract}}

\section{{研究背景}}
Skinner (2008) 讨论了美国上市公司支付政策从现金股利向股票回购转变的经验事实。传统股利具有持续性和承诺性质，而股票回购更灵活，企业可以根据现金流、投资机会和市场环境调整回购强度。本文的复现目标是在相同研究问题和主要变量定义下，检验核心趋势、分类表和回归方向是否能够被当前可得数据重新支持。

\section{{数据与变量构造}}
样本来自 Compustat Annual，并使用 CRSP/CCM 筛选后的美国普通股公司。金融业和公用事业公司被剔除，行业筛选使用 \texttt{{sich}} 优先、\texttt{{sic}} 作为备选的 \texttt{{sic\_use}}。现金股利由 \texttt{{dvc}} 衡量；净回购优先使用库存股变化法，只有当当前和滞后 \texttt{{tstkc}} 均可观测且均为零时，才使用 \texttt{{prstkc - sstk}} 的现金流口径。负回购值被截断为零，但缺失的股利或回购状态不会被无条件填补为零。

Figure 1 直接使用补全后覆盖 1970--2005 年的 \texttt{{maindata.csv}} 清洗样本统一汇总，并使用 \texttt{{ib}} 衡量盈余；特殊项目线使用原始 \texttt{{spi}}，缺失值保留为缺失。Figure 2 使用调整后盈余 \texttt{{ib - 0.6 x spi}}，其中 \texttt{{spi}} 缺失按零处理；Figure 3 的亏损指标与 Figure 2 保持一致，由调整后盈余 \texttt{{ib - 0.6 x spi < 0}} 定义，\texttt{{spi}} 缺失同样按零处理。Table 3 的连续回归变量在 Python 导出的回归数据中仅做 99\% 上尾截断，不再做 1\% 下尾截断；ESO 稀释变量定义为 \texttt{{xintopt / at * past\_stock\_return}}。主回归的三年股票收益严格按原论文价格配对口径，由主表 \texttt{{PRCC\_F}} 合并 \texttt{{ajex.csv}} 后与精确 \texttt{{fyear-3}} 年份配对计算；无法形成精确价格配对时保持缺失。

\section{{图形复现结果}}
Figure 1 的源表覆盖 1970--2005 年共 36 个年度，特殊项目线按原始 \texttt{{spi}} 汇总，缺失值不填零。图形显示，现金股利仍然保持重要地位，但股票回购在 1980 年代以后快速上升，并在 1990 年代以后成为企业向股东分配现金的重要方式。这一趋势与 Skinner (2008) 的核心结论一致：企业并非简单减少支付，而是逐步改变支付渠道。

\begin{{figure}}[!htbp]
\centering
\includegraphics[width=0.92\textwidth]{{../../../shared_artifacts/python_out/figures/figure1.pdf}}
\caption{{Aggregate Compustat earnings, special items, dividends, and net repurchases, 1970--2005}}
\end{{figure}}

Figure 2 按长期支付组别展示调整后盈余变化，其中 \texttt{{spi}} 缺失按零处理。持续股利和持续回购企业的盈余水平更高，说明稳定支付政策主要集中在更成熟、更盈利的企业中。只回购或偶尔回购企业的盈余波动更明显，符合股票回购作为更灵活支付工具的解释。

\begin{{figure}}[!htbp]
\centering
\includegraphics[width=0.92\textwidth]{{../../../shared_artifacts/python_out/figures/figure2.pdf}}
\caption{{Aggregate earnings by long-run payout group, 1980--2005}}
\end{{figure}}

Figure 3 使用调整后盈余为负来定义亏损，源表覆盖 1980--2005 年共 130 个组别年度观测。图形显示，不支付或偶尔回购企业的亏损比例更高，而持续支付企业亏损比例较低。这支持原论文关于企业生命周期和支付政策选择的解释：成熟、盈利稳定的企业更可能形成持续支付政策。

\begin{{figure}}[!htbp]
\centering
\includegraphics[width=0.92\textwidth]{{../../../shared_artifacts/python_out/figures/figure3.pdf}}
\caption{{Fraction of firms reporting losses by long-run payout group, 1980--2005}}
\end{{figure}}

\FloatBarrier
\section{{表格复现结果}}
Table 1 按十年窗口统计公司在窗口内支付现金股利和进行股票回购的年数。Panel A 表明，零股利公司数量较大，同时越来越多公司进入回购相关类别。Panel B 进一步显示，支付金额越来越集中在持续股利和较多回购年数组别中，说明企业支付方式的变化主要体现为现金分配渠道的重组。

{t1a}

{t1b}

Table 2 使用 1980--2005 年长期窗口重新分类公司。结果显示，完全不支付和偶尔回购公司数量较多，而长期持续股利并伴随长期回购的公司数量较少。这一结构与原文关注的“少数成熟企业承担大额支付、多数企业支付较少或不稳定”的经验事实一致。

{t2}

Table 3 使用 Python 对导出的样本标记和变量进行普通二元 logit 回归。回归不重新清洗数据，也不重新定义样本。1980--1994 列不包含 ESO，1995--2005 基础列也不包含 ESO，只有 1995--2005 ESO 列加入 \texttt{{eso\_dilution}}。表中主结果采用严格的 \texttt{{PRCC\_F / ajex}} 价格配对口径计算 \texttt{{past\_stock\_return}}。

{t3a}

{t3b}

由于 1995--1999 年 \texttt{{xintopt}} 覆盖不足会扭曲 ESO 模型样本，Python 进一步在 \texttt{{xintopt}} 覆盖优秀的 2000--2005 年子样本中重估 ESO 模型。该检验不是为了简单让样本量接近原论文，也不作为主回归替代；它用于观察数据覆盖改善以后，ESO 相关系数和核心控制变量是否保持可解释的方向。

{robust_audit}

{robust_reg}

稳健性结果显示，Panel A 的 XINTOPT/ESO 保留率从 1995--1999 年的 60.7\% 提高到 2000--2005 年的 95.3\%，Panel B 从 23.1\% 提高到 95.3\%。在覆盖更稳定的 2000--2005 年子样本中，Panel A 的 ROA、Past stock return 和 ESO dilution 的方向与量级相对更贴近 Skinner (2008)；Panel B 的 ESO dilution 仍保持负向并在 5\% 水平显著。因此，这一结果更适合作为数据覆盖改善后的稳健性证据，而不是主回归的替代规格。

\section{{与原论文差异}}
复现结果在主要趋势和经济含义上与 Skinner (2008) 保持一致，但部分样本数量和系数大小不同。主要原因有三点。第一，当前 WRDS/Compustat 和 CRSP/CCM 数据版本与原论文使用的数据版本不同，历史覆盖和证券筛选可能发生变化。第二，本文采用严格的库存股优先回购构造规则，当 \texttt{{tstkc}} 当前年或滞后年缺失时，不用现金流口径无条件替代，因此部分公司年无法进入回购状态分类或回归样本。第三，Table 3 是公司年回归样本，样本差异不仅来自长期分组公司数量，也来自 \texttt{{roa}}、现金持有、三年股票收益和 ESO 变量的完整性。主表中的三年收益严格使用 Compustat 价格口径和精确年份配对，不能配对的公司年保持缺失。

\section{{结论}}
总体来看，复现结果支持 Skinner (2008) 的主要结论：美国企业支付政策在 1970--2005 年间发生明显转变，股票回购逐渐成为现金股利之外的重要支付方式。回归结果也显示，盈利能力、现金持有和过去股票收益等变量与回购行为存在系统关系。虽然复现无法与原论文在所有数值上完全一致，但核心趋势、表格结构和经济解释保持一致，说明原文关于企业支付政策演变的结论具有较强经验支持。
\end{{document}}
"""


def main() -> None:
    BUILD_DIR.mkdir(exist_ok=True)
    (BUILD_DIR / "elegantpaper.cls").write_text((LATEX_SRC_DIR / "elegantpaper.cls").read_text(encoding="utf-8"), encoding="utf-8")
    (BUILD_DIR / "replication_report.tex").write_text(build_tex(), encoding="utf-8")


if __name__ == "__main__":
    main()
