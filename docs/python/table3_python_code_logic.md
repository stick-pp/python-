# Table 3 Python 代码逻辑说明

本文档只说明当前 Python 代码如何为 Stata 准备 Table 3 回归数据，不讨论 Stata 最终估计结果。对应代码文件为 `replicate_skinner_2008.py`。

## 1. Python 在 Table 3 中的职责

当前 Python 只做三件事：

1. 在统一清洗样本中构造 Table 3 所需变量。
2. 依据 Group II、III、IV 和模型期段生成 Stata 可用的样本标记变量。
3. 导出 `table3_regression_data.csv`、`table3_regression_data.dta` 和 `table3_replication.do`。

Python 不把 Table 3 回归结果作为最终学术表格，也不负责最终 Stata 回归估计。

## 2. 上游样本入口

Table 3 使用的基础数据来自 `clean_and_construct()` 和 `add_long_run_groups()`。

清洗顺序为：

1. 合并 Compustat 主数据和 `ajex` 调整因子。
2. 保留 `consol=C`、`indfmt=INDL`、`datafmt=STD`、`curcd=USD`。
3. 保留美国注册公司 `fic=USA`。
4. 用 `sic_use = sich` 优先、`sic` 补充，剔除金融业和公用事业。
5. 通过 CCM link table 与 CRSP names/history 进行股票层筛选。
6. 构造股利、净回购、收益、ROA、现金、三年股票收益、ESO dilution。
7. 用 1980-2005 长窗口的支付年份数划分 Group I-V。

当前 Table 3 只保留 `group_id in [2, 3, 4]`：

- Group II：至少 16 年支付股利且至少 11 年回购。
- Group III：不支付股利且回购 1-5 年。
- Group IV：不支付股利且回购至少 6 年。

当前导出的 Table 3 firm counts：

| Group | 当前公司数 | 论文公司数 | 差异 |
|---|---:|---:|---:|
| Group II | 302 | 345 | -43 |
| Group III | 3,115 | 2,518 | +597 |
| Group IV | 387 | 351 | +36 |

这意味着 Table 3 的 Stata 输入样本从公司分组开始就已经不同于论文。

## 3. 因变量构造

因变量是 `repurchase_dummy`。

代码逻辑：

1. 若净回购 `repurchase > 0`，`repurchase_dummy = 1`。
2. 若净回购 `repurchase == 0`，`repurchase_dummy = 0`。
3. 若净回购无法构造，`repurchase_dummy = NaN`，不进入对应模型样本。

净回购构造遵循严格论文口径：

1. 若当前年和上一年 `tstkc` 都可观察，且不同时为 0：使用 `tstkc - tstkc_lag1`。
2. 若当前年和上一年 `tstkc` 都可观察且都为 0，并且 `prstkc/sstk` 完整：使用 `prstkc - sstk`。
3. 若上述计算结果为负，设为 0。
4. 若 `tstkc` 当前年或上一年缺失，即使 `prstkc/sstk` 完整，也不自动使用现金流 fallback。

当前 1980-2005 清洗样本中，`repurchase_dummy` 缺失率约为 24.7%。主要来源是 `tstkc` 或上一年 `tstkc_lag1` 不可观察。

## 4. 自变量构造

### ROA

代码定义：

```text
roa = oibdp / at_lag1
```

其中 `at_lag1` 是同一 `gvkey` 精确上一财政年度 `fyear - 1` 的总资产。

### Past stock return

代码定义：

```text
adjusted_price = prcc_f / ajex
past_stock_return = adjusted_price_t / adjusted_price_lag3 - 1
```

当前代码优先使用同一 `gvkey` 精确 `fyear - 3` 的调整价格。如果精确年度价格缺失，再使用 `datadate - 3 years` 附近 183 天内最近的可得调整价格补充。

当前覆盖情况：

| 来源 | 观测数 |
|---|---:|
| 精确 `fyear - 3` | 101,352 |
| 日期附近补充 | 53 |
| 无法构造 | 41,687 |

日期附近补充仅恢复很少观测，说明 Table 3 样本量差异不是主要由精确年度匹配造成。

### Cash

代码定义：

```text
cash = che / at
```

要求 `che` 非缺失、`at` 非缺失且 `at > 0`。

### ESO dilution

代码定义：

```text
eso_dilution = (xintopt / sale) * past_stock_return
```

要求：

- `fyear >= 1995`
- `xintopt` 非缺失
- `sale` 非缺失且 `sale > 0`
- `past_stock_return` 非缺失

变量翻译表确认 `DATA399 -> XINTOPT -> Implied Option Expense`，因此 `xintopt` 对应论文的 Compustat #399。

### Regular dummy 与交互项

代码定义：

```text
regular_dummy = 1 if group_id == 4
regular_dummy = 0 if group_id == 3
roa_regular = roa * regular_dummy
```

该变量只在 Panel B 使用。

## 5. Table 3 模型样本标记

`build_table3_data()` 在 Stata 输入中生成六个样本标记：

| 标记变量 | 样本逻辑 |
|---|---|
| `sample_A_1980_1994` | Group II，1980-1994，因变量有效，`roa/past_stock_return/cash` 完整 |
| `sample_A_1995_2005` | Group II，1995-2005，因变量有效，`roa/past_stock_return/cash` 完整 |
| `sample_A_1995_2005_eso` | Group II，1995-2005，因变量有效，`roa/past_stock_return/cash/eso_dilution` 完整 |
| `sample_B_1980_1994` | Group III/IV，1980-1994，因变量有效，`regular_dummy/roa/roa_regular/past_stock_return/cash` 完整 |
| `sample_B_1995_2005` | Group III/IV，1995-2005，因变量有效，`regular_dummy/roa/roa_regular/past_stock_return/cash` 完整 |
| `sample_B_1995_2005_eso` | Group III/IV，1995-2005，因变量有效，`regular_dummy/roa/roa_regular/past_stock_return/cash/eso_dilution` 完整 |

## 6. 当前导出样本量

| 模型 | 当前 Python 标记样本量 | 论文 Obs. | 差异 |
|---|---:|---:|---:|
| Panel A 1980-1994 | 3,448 | 4,801 | -1,353 |
| Panel A 1995-2005 | 3,011 | 3,510 | -499 |
| Panel A 1995-2005 ESO | 2,366 | 3,173 | -807 |
| Panel B 1980-1994 | 9,493 | 11,581 | -2,088 |
| Panel B 1995-2005 | 12,616 | 15,279 | -2,663 |
| Panel B 1995-2005 ESO | 7,692 | 12,965 | -5,273 |

## 7. 从代码角度看样本量偏低的直接原因

当前 Table 3 样本量低于论文，主要来自四个层面：

1. Group II 公司数少于论文，Panel A 的可用 firm-year 天然偏少。
2. `repurchase_dummy` 严格按论文口径构造，`tstkc` 或 `tstkc_lag1` 不可观察时保持缺失，导致大量 firm-year 不能进入回归。
3. `past_stock_return` 即使加入日期附近补充，仍有大量缺失；但它不是最大差异来源。
4. ESO 模型要求 `xintopt/sale/past_stock_return` 全部非缺失，当前 `xintopt` 覆盖不足导致 ESO 列样本量显著低于论文。

## 8. 不建议由 Python 自行改动的事项

以下处理没有在论文中明确给出，当前代码未采用：

- 不把 `xintopt` 缺失填 0。
- 不用 `TXBCOF`、`CSHRSO` 等其他股票期权相关字段替代 `xintopt`。
- 不对 ROA、cash、past return、ESO dilution 做 winsorize。
- 不在 `tstkc` pair 缺失时无条件使用 `prstkc - sstk` 作为回购 fallback。

