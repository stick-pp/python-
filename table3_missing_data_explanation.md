# Table 3 样本量缺失说明

本文档用于解释 Skinner (2008) 复现中 Table 3 回归输入样本量低于原论文的原因。结论是：在当前复现中，Table 3 样本量缺口主要来自数据源字段覆盖和严格论文口径下变量不可判定，而不是 Python 复现逻辑对论文变量公式的错误理解。

## 1. 结论摘要

当前 Python 代码对 Table 3 变量的构造总体遵循论文口径：

- 因变量为 firm-year 是否发生净回购；
- ROA 使用 operating income before depreciation 除以滞后总资产；
- Past stock return 使用拆股调整价格计算截至当前财年末的前三年收益；
- Cash 使用现金除以总资产；
- ESO dilution 使用 Compustat #399 的 option expense，按 sales 缩放后乘以 past stock return；
- Panel A、Panel B 和 Regular dummy 的分组逻辑与论文 Table 2/3 一致。

Table 3 样本量低于论文，主要原因是：

1. 严格论文口径下，`tstkc` 当前年或上一年缺失会导致 `repurchase_dummy` 不可判定；
2. 当前数据中 `xintopt` 即 Compustat #399 的历史覆盖不足，导致 ESO 模型样本量明显偏低；
3. Group II 公司数少于论文，Panel A 可用 firm-year 基础样本天然偏小；
4. 当前 WRDS/Compustat/CRSP/CCM 数据版本和字段覆盖与 Skinner (2008) 使用的数据版本不完全一致。

因此，Table 3 的样本量缺失可以在报告中解释为数据源覆盖差异和严格复现口径共同导致，而不应简单解释为变量构造错误。

## 2. 论文 Table 3 的关键口径

Skinner (2008) Table 3 报告 repurchase logit regressions。论文说明：

- 因变量在 firm-year 有净回购时取 1，否则取 0；
- 净回购定义沿用 Table 1；
- ROA 为 Compustat #13 除以滞后 Compustat #6；
- Past stock return 为截至当前财年末的前三年 raw stock return，使用拆股调整价格 Compustat #199 / #27；
- Cash 为 Compustat #1 / #6；
- ESO dilution 为 ESO stock option expense 按 sales 缩放后乘以 past stock return；
- ESO stock option expense 来自 Compustat #399；
- Panel A 使用 Group II 公司；
- Panel B 使用 Group III 和 Group IV 公司，并对 Group IV 设置 Regular dummy。

论文没有明确说明以下处理：

- `tstkc` 当前年或上一年缺失时是否可以无条件使用 `prstkc - sstk`；
- 是否将 ESO expense 缺失值填 0；
- 是否使用其他 option-related 字段替代 Compustat #399；
- 是否对 ROA、cash、past return、ESO dilution 进行 winsorize；
- 对缺失解释变量是否存在额外填补规则。

因此，当前复现采用不填补缺失、只保留完整模型变量的处理，是保守且可解释的复现策略。

## 3. 当前 Python 的 Table 3 变量构造

当前 Python 只负责生成 Stata 回归输入数据，不负责最终回归估计。

### 3.1 因变量：`repurchase_dummy`

当前净回购构造为：

1. 若当前年和上一年 `tstkc` 均可观察，且不同时为 0，则使用 `tstkc - tstkc_lag1`；
2. 若当前年和上一年 `tstkc` 均可观察且都为 0，并且 `prstkc` 和 `sstk` 完整，则使用 `prstkc - sstk`；
3. 若计算出的净回购为负，设为 0；
4. 若 `tstkc` 当前年或上一年缺失，即使 `prstkc/sstk` 完整，也不在主口径中使用现金流 fallback。

上述处理严格对应论文 Table 1 对净回购的定义。现金流量表项目 `prstkc - sstk` 只在可以推断为 retirement method 时使用；论文没有明确允许在 `tstkc` 缺失时将其作为一般性 fallback。

### 3.2 解释变量

| 变量 | 当前代码口径 | 与论文关系 |
|---|---|---|
| ROA | `oibdp / at_lag1` | 对应 Compustat #13 / lagged #6 |
| Past stock return | `prcc_f / ajex` 形成拆股调整价格，优先精确 `fyear - 3`，缺失时用三年前日期附近价格补充 | 对应 #199 / #27 计算三年收益 |
| Cash | `che / at` | 对应 Compustat #1 / #6 |
| ESO dilution | `(xintopt / sale) * past_stock_return` | `xintopt` 已由变量翻译表确认对应 DATA399 |
| Regular dummy | Group IV 为 1，Group III 为 0 | 对应 Panel B 说明 |

## 4. 当前样本量与论文差异

| 模型 | 当前 Python 标记样本量 | 原论文 Obs. | 差异 |
|---|---:|---:|---:|
| Panel A 1980-1994 | 3,448 | 4,801 | -1,353 |
| Panel A 1995-2005 | 3,011 | 3,510 | -499 |
| Panel A 1995-2005 ESO | 2,366 | 3,173 | -807 |
| Panel B 1980-1994 | 9,493 | 11,581 | -2,088 |
| Panel B 1995-2005 | 12,616 | 15,279 | -2,663 |
| Panel B 1995-2005 ESO | 7,692 | 12,965 | -5,273 |

## 5. 样本量缺失的直接证据

### 5.1 Group 公司数差异

| Group | 当前公司数 | 原论文公司数 | 差异 |
|---|---:|---:|---:|
| Group II | 302 | 345 | -43 |
| Group III | 3,115 | 2,518 | +597 |
| Group IV | 387 | 351 | +36 |

Panel A 只使用 Group II，因此 Group II 公司数低于论文会直接导致 Panel A firm-year 样本量偏低。

Panel B 的 Group III/IV 公司数合计并不低，但回归有效样本仍偏低，说明缺口主要发生在 firm-year 变量可得性层面。

### 5.2 回购状态缺失

当前 1980-2005 清洗样本中，`repurchase_dummy` 缺失率约为 24.7%。

主要来源：

| 回购来源/缺失类型 | 行数 |
|---|---:|
| `retirement_method` | 44,491 |
| `treasury_stock_change` | 39,516 |
| `missing_tstkc_pair_cashflow_available_not_used` | 20,306 |
| `missing_cashflow_inputs` | 5,303 |
| `missing_tstkc_pair_and_cashflow_inputs` | 1,952 |

其中 `missing_tstkc_pair_cashflow_available_not_used` 表示 `tstkc` 当前年或上一年不可观察，但 `prstkc/sstk` 完整。严格论文口径下，这些观测不能直接用 `prstkc - sstk` 构造净回购，因为无法判断其是否属于 retirement method。

敏感性测试显示，如果超出论文明确口径，使用现金流 fallback，会恢复部分 Table 3 样本量：

| 模型 | 严格论文口径 | fallback 敏感性 | 增加 | 原论文 |
|---|---:|---:|---:|---:|
| Panel A 1980-1994 | 3,448 | 4,195 | +747 | 4,801 |
| Panel A 1995-2005 | 3,011 | 3,016 | +5 | 3,510 |
| Panel A 1995-2005 ESO | 2,366 | 2,368 | +2 | 3,173 |
| Panel B 1980-1994 | 9,493 | 10,299 | +806 | 11,581 |
| Panel B 1995-2005 | 12,616 | 12,637 | +21 | 15,279 |
| Panel B 1995-2005 ESO | 7,692 | 7,702 | +10 | 12,965 |

这说明回购状态缺失确实是样本量缺口的重要来源，但使用 fallback 属于扩展口径，不能作为主复现口径。

### 5.3 ESO 变量覆盖不足

变量翻译表确认：

| Compustat old item | 当前变量 | 标签 |
|---|---|---|
| DATA399 | XINTOPT | Implied Option Expense |

当前数据中没有发现可以直接替代 `xintopt` 的字段。`TXBCOF` 是 stock option tax benefit，`CSHRSO` 是 stock options reserved shares，均不是 ESO expense。

1995-2005 期间，在基础变量已经完整的样本中，`xintopt` 缺失导致 ESO 模型样本明显减少：

| Group | 基础变量完整样本 | 因 `xintopt` 缺失不能进入 ESO 模型 | ESO 可用样本 |
|---|---:|---:|---:|
| Group II | 3,011 | 645 | 2,366 |
| Group III | 9,657 | 3,825 | 5,791 |
| Group IV | 2,959 | 1,056 | 1,901 |

这解释了 Panel B 1995-2005 ESO 模型样本量显著低于论文的主要原因。

### 5.4 Past stock return 不是主要原因

当前代码已将 past stock return 从“精确 `fyear - 3`”放宽为：

1. 优先使用精确 `fyear - 3`；
2. 若缺失，再使用 `datadate - 3 years` 附近 183 天内最近的可得调整价格。

放宽后只新增 53 个可用 past stock return 观测，因此 Table 3 样本量缺口不能主要归因于三年收益匹配过严。

## 6. 报告中建议使用的说明文字

正式报告中可写为：

> Table 3 的回归输入数据由 Python 统一生成，并交由 Stata 进行最终 logit 估计。变量构造遵循 Skinner (2008) Table 3 注释：ROA 使用 Compustat #13 除以滞后 #6，现金使用 #1/#6，三年股票收益使用拆股调整价格 #199/#27，ESO dilution 使用 #399 按 sales 缩放后乘以三年股票收益。净回购变量沿用 Table 1 的定义，即优先使用普通库存股增加额 #226；仅在当前年和上一年库存股均为 0、可推断为 retirement method 时，使用 #115 - #108。当前复现未将 `tstkc` 缺失但现金流字段完整的观测无条件视作回购状态可判定，也未将 ESO expense 缺失填 0。

> 因此，Table 3 样本量低于原论文主要反映数据源字段覆盖差异，尤其是历史 `tstkc`/`tstkc_lag1` 的可得性和 Compustat #399 (`xintopt`) 的覆盖不足，而不是回归变量公式与论文不一致。若采用现金流 fallback 或对 ESO 缺失进行填补，可以机械提高样本量，但这超出论文明确说明的主口径，故仅适合作为敏感性分析而不作为正式复现口径。

## 7. 结论

Table 3 数据缺失问题可以合理归结为数据源覆盖问题和严格复现口径下的变量不可判定问题。当前 Python 逻辑在主要变量公式上与论文一致，不建议为了追齐样本量而在主口径中加入论文未明确说明的 fallback 或缺失值填补。

