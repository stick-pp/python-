# Skinner (2008) 复现样本清洗与进入口径说明：修订后严格 md 口径

本文档说明根据 `Skinner_2008_Table1_2_3_cleaning_for_codex (1).md` 和 `Table3_variable_cleaning_for_codex.md` 修改后的严格样本清洗、变量构建与进入口径。该口径的核心原则是：缺失值不自动解释为 0；只有支付状态完整可判定的公司才能进入支付年份分组、长期 Group I-V 以及依赖这些分组的 Figure 2、Figure 3 和 Table 3。

## 1. 数据来源

- 主数据：`2.csv`，来自 WRDS Compustat Fundamentals Annual。
- 调整因子：`ajex.csv`。
- 合并键：`gvkey + datadate`。
- 样本单位：公司-财政年度，即 firm-year。

## 2. 基础样本筛选

严格口径下保留：

```text
consol = C
indfmt = INDL
datafmt = STD
curcd = USD
fic = USA
```

行业筛选：

- 金融业：SIC 6000-6999。
- 公用事业：SIC 4900-4999。
- 同时使用 `sic` 与 `sich`。
- 只要 `sic` 或 `sich` 任一字段落入上述区间，即剔除该 firm-year。
- 若 `sic` 和 `sich` 均缺失，则保留，但在样本审计中单独披露。

当前运行结果：

```text
原始样本：302,231 firm-years，26,256 firms
WRDS 格式筛选后：302,231 firm-years，26,256 firms
fic = USA 后：286,030 firm-years，24,490 firms
行业筛选后：213,273 firm-years，18,391 firms
1970-2005 样本：209,714 firm-years
1980-2005 样本：165,422 firm-years
```

## 3. 公司-年度唯一性

严格口径使用：

```text
gvkey + fyear
```

作为公司-财政年度识别键。

脚本会检查清洗后的样本是否存在重复 `gvkey + fyear`。若存在重复，不允许直接静默保留第一条，而应先检查 `datadate`、格式字段和财政年度变化。

当前数据在基础筛选后未发现重复 `gvkey + fyear`。

## 4. 股利变量

原始字段：

```text
dvc
```

严格口径：

```text
dividend = dvc
```

缺失处理：

- `dvc > 0`：`dividend_dummy = 1`。
- `dvc = 0`：`dividend_dummy = 0`。
- `dvc` 缺失：`dividend_dummy = NaN`。

严格口径不再执行：

```python
df["dvc"] = df["dvc"].fillna(0)
```

经济含义：

- `0` 表示可观测到没有支付股利。
- `NaN` 表示无法判断是否支付股利。
- 两者不能混用。

## 5. 收益与特殊项目

严格口径仍按原论文定义：

```text
special_items = spi，缺失填 0
earnings = ib - 0.6 * spi
```

这里 `spi` 缺失填 0 是收益定义的一部分，与股利或回购缺失填 0 不同。

## 6. 净回购变量

原始字段：

```text
tstkc
prstkc
sstk
```

### 6.1 上一年库存股匹配

严格口径不使用简单 `shift(1)`。

当前使用精确匹配：

```text
同一 gvkey
当前 fyear 的上一年为 fyear - 1
```

即只允许 `gvkey + fyear - 1` 作为上一年库存股。

### 6.2 库存股法

若当前年和上一财政年度 `tstkc` 均非缺失，且不同时为 0，则使用库存股法：

```text
repurchase = tstkc_t - tstkc_t-1
```

### 6.3 退休法

只有当：

```text
tstkc_t 非缺失
tstkc_t-1 非缺失
tstkc_t = 0
tstkc_t-1 = 0
prstkc 非缺失
sstk 非缺失
```

同时满足时，才使用：

```text
repurchase = prstkc - sstk
```

### 6.4 缺失处理

若当前年或上一年 `tstkc` 缺失，或不存在精确上一财政年度，则主口径下：

```text
repurchase = NaN
repurchase_dummy = NaN
```

若退休法下 `prstkc` 或 `sstk` 任一缺失，也保持：

```text
repurchase = NaN
repurchase_dummy = NaN
```

只有已经成功构造出的回购值为负时，才执行：

```text
repurchase = 0
```

严格口径不再执行：

```python
df["tstkc"] = df["tstkc"].fillna(0)
df["prstkc"] = df["prstkc"].fillna(0)
df["sstk"] = df["sstk"].fillna(0)
df["repurchase"] = df["repurchase"].fillna(0)
```

## 7. 总支付

严格口径：

```text
total_payout = dividend + repurchase
```

只要 `dividend` 或 `repurchase` 任一缺失，`total_payout` 保持缺失。

聚合时使用 `sum(min_count=1)`，避免整组全缺失时被自动算成 0。

## 8. Table 1 进入口径

窗口：

```text
1980-1989
1985-1994
1990-1999
1995-2004
```

每个窗口内先按公司统计：

```text
div_years
rep_years
div_valid_years
rep_valid_years
firm_years
div_missing_years
rep_missing_years
```

进入 Table 1 的条件：

```text
div_valid_years = firm_years
rep_valid_years = firm_years
```

也就是说，公司在该窗口内实际存在的所有 firm-year 中，股利状态和回购状态都必须完整可判定。

若任一年度股利或回购状态缺失，则该公司不能进入 Table 1 的 0 年组，也不能进入任何支付年份组。

当前严格口径下 Table 1 可分类公司数：

```text
1980-1989：1
1985-1994：3,941
1990-1999：4,139
1995-2004：4,717
```

这显著低于原论文，尤其是 1980-1989 窗口。

## 9. Table 2 进入口径

期间：

```text
1980-2005
```

进入条件：

```text
div_valid_years = firm_years
rep_valid_years = firm_years
```

公司不要求完整存在 1980-2005 的所有年份，但在其实际存在的年份内，股利状态和回购状态必须全部可判定。

分组：

```text
0
1-5
6-10
11-15
16-20
>20
```

当前严格口径下：

```text
Table 2 可分类公司数：1
Table 2 0 股利列：0
原论文 Table 2 公司数：10,675
原论文 0 股利列：6,852
```

## 10. Group I-V 进入口径

Group I-V 基于 1980-2005 长期支付历史，并且只对 Table 2 可分类公司定义。

定义：

- Group I：`DividendYears = 0` 且 `RepurchaseYears = 0`。
- Group II：`DividendYears >= 16` 且 `RepurchaseYears >= 11`。
- Group III：`DividendYears = 0` 且 `1 <= RepurchaseYears <= 5`。
- Group IV：`DividendYears = 0` 且 `RepurchaseYears >= 6`。
- Group V：`RepurchaseYears = 0` 且 `DividendYears >= 6`。

若支付状态不完整：

```text
group_id = missing
group_name = Unclassifiable
```

当前严格口径下：

```text
Group I：0
Group II：0
Group III：0
Group IV：0
Group V：0
```

原因是 1980-2005 长窗口内绝大多数公司至少有一年回购状态不可判定。

## 11. Figure 2 与 Figure 3 进入口径

Figure 2：

- Panel A：全部工业公司收益仍可绘制。
- Group II 线条依赖 Group II 公司。
- Panel B 依赖 Group I、III、IV、V。

严格口径下 Group I-V 为空，因此：

- Figure 2 右图显示空样本诊断。
- Figure 3 显示空样本诊断。

这不是绘图错误，而是严格进入口径导致的经济后果。

## 12. Table 3 回归变量

### 12.1 因变量

```text
repurchase_dummy = 1 if repurchase > 0
repurchase_dummy = 0 if repurchase = 0
repurchase_dummy = NaN if repurchase is missing
```

不再允许：

```python
(df["repurchase"] > 0).astype(int)
```

因为这会把缺失回购错误编码为 0。

### 12.2 ROA

```text
roa = oibdp_t / at_t-1
```

其中 `at_t-1` 必须来自同一公司精确 `fyear - 1`。

### 12.3 Cash

```text
cash = che / at
```

仅在 `che`、`at` 非缺失且 `at > 0` 时计算。

### 12.4 Past stock return

严格口径：

```text
adjusted_price = prcc_f / ajex
past_stock_return = adjusted_price_t / adjusted_price_t-3 - 1
```

要求：

- `prcc_f > 0`
- `ajex > 0`
- 三年前价格来自同一公司精确 `fyear - 3`

不再无条件使用：

```text
abs(prcc_f) / ajex
```

### 12.5 ESO dilution

```text
eso_dilution = xintopt / sale * past_stock_return
```

仅在以下条件同时满足时计算：

- `fyear >= 1995`
- `xintopt` 非缺失
- `sale > 0`
- `past_stock_return` 非缺失

## 13. Table 3 进入口径

Panel A：

- 样本为 Group II。
- 模型：`1980-1994`、`1995-2005`、`1995-2005 + ESO`。

Panel B：

- 样本为 Group III 和 Group IV。
- `regular_dummy = 1` 仅表示 Group IV。
- `regular_dummy = 0` 仅表示 Group III。
- 其他组别的 `regular_dummy` 保持缺失。

每个模型按自身变量集单独完整案例删除，不提前统一删除所有变量缺失。

当前严格口径下 Table 3 完整案例数：

```text
Panel A, 1980-1994：0
Panel A, 1995-2005：0
Panel A, 1995-2005 ESO：0
Panel B, 1980-1994：0
Panel B, 1995-2005：0
Panel B, 1995-2005 ESO：0
```

因此脚本会跳过 Stata，避免回归失败或误读旧结果。

## 14. 当前严格口径的核心解释

严格口径的核心优点是不会把：

```text
无法判断是否回购
```

错误写成：

```text
没有回购
```

但在当前 Compustat 数据中，很多早期 firm-year 缺少可用于精确连续年度匹配的 `tstkc`。同时 md 文档禁止在主口径下用现金流法替代这些缺失库存股信息。因此，在 1980-2005 长窗口内，大量公司被判定为支付历史不完整。

这导致：

- Table 1 早期窗口样本显著减少。
- Table 2 几乎为空。
- Group I-V 为空。
- Figure 2 右图、Figure 3 和 Table 3 无法得到与原文可比的结果。

## 15. 使用建议

该口径应称为：

```text
严格主口径 / strict missing-value specification
```

它适合用于说明最严谨的缺失值处理逻辑，但不适合作为唯一的 Skinner (2008) 数值复现口径。

若目标是恢复与原论文高度可比的 Figure 2、Figure 3 和 Table 3，应另设一个清楚标注的：

```text
宽松复现口径 / sensitivity口径 / paper-like replication口径
```

例如允许在 `tstkc` 连续年度信息不可用时，使用 `prstkc - sstk` 作为回购替代度量。但该口径必须在报告中明确说明，不能与严格主口径混用。
