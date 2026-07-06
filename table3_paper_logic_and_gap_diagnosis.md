# Table 3 原论文口径与样本量差异诊断

本文档整理 Skinner (2008) 原论文中 Table 3 的相关口径，并与当前 Python 生成的 Stata 输入数据进行对照。论文来源为 `The evolving relation between earnings, dividends, and stock repurchases.pdf`。

## 1. 原文中 Table 3 的位置和目的

Table 3 用 logit 回归检验 firm-year 层面“公司是否回购股票”的概率。原文说明，作者估计这些公司在某一 firm-year 回购股票的可能性，并使用 ROA、过去股票收益、现金和 1995 年后的 ESO dilution 作为解释变量。

论文将 Table 3 分为两个 panel：

- Panel A：Group II，即经常支付股利且经常回购的公司。
- Panel B：Group III 和 Group IV，即不支付股利但偶尔回购或经常回购的公司。

论文把估计期分为：

- 1980-1994
- 1995-2005
- 1995-2005 且加入 ESO dilution

## 2. 原论文变量定义

### 因变量

论文 Table 3 注释说明，因变量在有净回购的 firm-year 取 1，否则取 0。净回购定义沿用 Table 1。

Table 1 的净回购口径为：

1. 若公司使用库存股法，使用普通库存股增加额 Compustat #226。
2. 若推断为 retirement method，即当前年和上一年库存股都为 0，使用股票购买 #115 减股票发行 #108。
3. 若净回购计算结果为负，设为 0。

### ROA

论文定义：

```text
ROA = Compustat #13 / lagged Compustat #6
```

即 operating income before depreciation 除以上一年 total assets。

### Past stock return

论文定义：

```text
raw stock return for three-year period ending at current period year-end
```

并说明使用拆股调整价格：

```text
Compustat #199 / Compustat #27
```

这意味着回报率应以当前财年末为终点，向前约三年计算。

### Cash

论文定义：

```text
Cash = Compustat #1 / Compustat #6
```

即现金除以总资产。

### ESO dilution

论文正文脚注说明，1995 年后美国公司披露 pro-forma ESO expense，该数值由 Compustat #399 报告。作者用其代理 ESO-driven dilution，并将该项目按 sales 缩放后乘以 past stock return。

当前变量翻译表确认：

| Compustat old item | 当前变量 | 标签 |
|---|---|---|
| DATA399 | XINTOPT | Implied Option Expense |

因此，`xintopt` 是论文所需的 Compustat #399。当前未发现可以替代 `xintopt` 的直接字段。

## 3. 原论文样本组别

Table 3 的分组来自 Table 2 的 1980-2005 长窗口分类。

| Panel | 论文组别 | 公司数 |
|---|---|---:|
| Panel A | 至少 16 年支付股利，至少 11 年回购 | 345 |
| Panel B regular | 不支付股利，至少 6 年回购 | 351 |
| Panel B occasional | 不支付股利，回购不超过 5 年 | 2,518 |

Panel B 中 `Regular dummy` 对经常回购组取 1，对偶尔回购组取 0。

## 4. 原论文 Table 3 样本量

| 模型 | 原论文 Obs. |
|---|---:|
| Panel A 1980-1994 | 4,801 |
| Panel A 1995-2005 | 3,510 |
| Panel A 1995-2005 ESO | 3,173 |
| Panel B 1980-1994 | 11,581 |
| Panel B 1995-2005 | 15,279 |
| Panel B 1995-2005 ESO | 12,965 |

## 5. 当前 Python 口径与论文口径对照

| 项目 | 原论文口径 | 当前 Python 口径 | 判断 |
|---|---|---|---|
| 因变量 | 有净回购取 1，否则 0 | `repurchase > 0` 取 1，`repurchase == 0` 取 0 | 一致 |
| 净回购 | #226；retirement method 用 #115 - #108；负值设 0 | `tstkc` 变化；`tstkc` 当前和上一年均为 0 时用 `prstkc - sstk`；负值设 0 | 一致 |
| ROA | #13 / lagged #6 | `oibdp / at_lag1` | 一致 |
| Past stock return | 当前财年末结束的三年 raw return，价格 #199/#27 | `prcc_f/ajex`，优先精确 `fyear - 3`，缺失时用三年前日期附近 183 天内价格补充 | 基本一致 |
| Cash | #1 / #6 | `che / at` | 一致 |
| ESO dilution | #399 按 sales 缩放，再乘以 past stock return | `(xintopt / sale) * past_stock_return` | 一致 |
| Regular dummy | Group IV 为 1，Group III 为 0 | `group_id == 4` 为 1，`group_id == 3` 为 0 | 一致 |
| 样本期 | 1980-1994、1995-2005 | 同样分期 | 一致 |

## 6. 当前样本量差异

| 模型 | 当前 Python 标记样本量 | 原论文 Obs. | 差异 |
|---|---:|---:|---:|
| Panel A 1980-1994 | 3,448 | 4,801 | -1,353 |
| Panel A 1995-2005 | 3,011 | 3,510 | -499 |
| Panel A 1995-2005 ESO | 2,366 | 3,173 | -807 |
| Panel B 1980-1994 | 9,493 | 11,581 | -2,088 |
| Panel B 1995-2005 | 12,616 | 15,279 | -2,663 |
| Panel B 1995-2005 ESO | 7,692 | 12,965 | -5,273 |

## 7. 当前数据量差异明显的原因

### 7.1 分组公司数已经不同

| Group | 当前公司数 | 论文公司数 | 差异 |
|---|---:|---:|---:|
| Group II | 302 | 345 | -43 |
| Group III | 3,115 | 2,518 | +597 |
| Group IV | 387 | 351 | +36 |

Panel A 的 Group II 公司数少于论文，因此 Panel A 样本量天然偏低。

Panel B 的 Group III/IV 公司数合计并不低于论文，但 firm-year 有效样本仍偏低，说明主要损失发生在变量可得性和因变量可判定性上。

### 7.2 `repurchase_dummy` 缺失较多

当前 1980-2005 清洗样本中，`repurchase_dummy` 缺失率约为 24.7%。来源包括：

| 来源 | 1980-2005 行数 |
|---|---:|
| `missing_tstkc_pair_cashflow_available_not_used` | 20,306 |
| `missing_cashflow_inputs` | 5,303 |
| `missing_tstkc_pair_and_cashflow_inputs` | 1,952 |

其中 `missing_tstkc_pair_cashflow_available_not_used` 表示 `tstkc` 当前年或上一年不可观察，但 `prstkc/sstk` 完整。严格论文口径下，这些行不能自动使用现金流量表替代，因为论文只在 retirement method 下使用 #115 - #108。

敏感性测试显示，如果扩展使用现金流 fallback，1980-1994 的 Table 3 样本量会明显增加；但该处理不属于论文明确口径，因此不建议作为正式复现口径。

### 7.3 Past stock return 不是主要差异来源

放宽为财年末日期附近匹配后，仅新增 53 个 `past_stock_return` 可用观测。

| 来源 | 观测数 |
|---|---:|
| 精确 `fyear - 3` | 101,352 |
| 日期附近补充 | 53 |
| 无法构造 | 41,687 |

因此 Table 3 样本量偏低不能主要归因于三年股票收益匹配过严。

### 7.4 ESO 模型主要受 `xintopt` 覆盖限制

1995-2005 期间，在基础变量已经完整的样本中，`xintopt` 缺失导致 ESO 模型大量减少。

| Group | 基础变量完整样本 | 因 `xintopt` 缺失不能进入 ESO 模型 | ESO 可用样本 |
|---|---:|---:|---:|
| Group II | 3,011 | 645 | 2,366 |
| Group III | 9,657 | 3,825 | 5,791 |
| Group IV | 2,959 | 1,056 | 1,901 |

这解释了 Panel B 1995-2005 ESO 样本量明显低于论文的主要原因。

### 7.5 数据版本和字段覆盖问题

当前变量公式与论文大体一致，但当前 WRDS/Compustat 数据的字段覆盖与 Skinner (2008) 使用的数据版本可能不同，特别是：

- `tstkc` 和上一年 `tstkc` 的可得性；
- `xintopt` 从 1995 后的历史覆盖；
- CRSP/CCM 股票层筛选后 firm-year 是否仍保留足够历史价格和上一年库存股记录。

## 8. 结论

当前 Table 3 的变量构造口径总体贴合论文。样本量差异明显的主要原因不是 Python 回归变量公式错误，而是：

1. Group II 公司数低于论文；
2. 严格论文口径下 `repurchase_dummy` 缺失较多；
3. `xintopt` 覆盖不足导致 ESO 模型样本量大幅偏低；
4. 当前数据版本和股票层筛选后的历史字段覆盖与论文使用数据不完全一致。

若后续要继续压缩 Table 3 样本量差异，优先应核查数据源字段覆盖和下载口径，而不是先改变量公式。

