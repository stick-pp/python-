# Skinner (2008) 复现规范差异修订：样本进入窗口与三项数据清洗调整

> 本文件是对既有 `Skinner_2008_Table1_2_3_cleaning_for_codex.md` 的**差异补丁**。  
> 仅列出需要替换、删除或新增的内容；未在本文件中出现的既有规则保持不变。  
> Codex 应以“既有规范 + 本差异补丁”为统一实施依据；如两者冲突，以本文件为准。

---

## 1. 删除原“完整支付历史才可进入窗口”的限制

删除既有规范中的以下进入条件：

```text
div_valid_years = firm_years
rep_valid_years = firm_years
```

同时删除由该条件派生的规则：

- 公司只要有一个实际存在年度的股利或回购状态缺失，就整体标记为 `Unclassifiable`；
- Table 1、Table 2 只保留支付状态在所有实际存在年度中均完整的公司；
- 只有完整支付历史公司才能定义 Group I–V。

这些规则不再作为主复现口径，也不再作为 Table 1、Table 2、Figure 2、Figure 3 和 Table 3 的样本进入条件。

---

## 2. 样本进入窗口改为论文近似口径（口径 C）

### 2.1 Table 1

四个窗口保持不变：

```text
1980–1989
1985–1994
1990–1999
1995–2004
```

公司进入某一窗口的条件改为：

```text
该公司在该窗口内至少有 1 个非缺失的公司年度观测。
```

公司不要求：

- 在完整十年中持续存在；
- 在其实际存在的所有年度中股利与回购状态全部可判定；
- 具有完整连续的十年支付历史。

操作口径：

1. 在窗口内保留所有满足基础样本筛选的公司年度；
2. 对每家公司，使用窗口内**可观察到的支付记录**统计：
   - `div_years = dividend_dummy == 1` 的年份数；
   - `rep_years = repurchase_dummy == 1` 的年份数；
3. 某一年度的支付状态缺失时：
   - 不将该年度计为支付年份；
   - 不将缺失的公司年度改写为 0；
   - 不因该年度缺失而排除整家公司；
4. 根据上述可观察支付年份数进入 Table 1 的 `3 × 4` 分组。

需要在 QA 和报告中明确：

> 该口径遵循论文“窗口内至少有一年非缺失数据、公司不必完整存续十年”的进入逻辑。支付年份数根据可观察记录累计，因此“0 年支付”表示样本期内未观察到正支付，而不等同于证明所有缺失年度均无支付。

### 2.2 Table 2

Table 2 的期间保持：

```text
1980–2005
```

公司进入 Table 2 的条件改为：

```text
该公司在 1980–2005 年期间至少有 1 个非缺失的公司年度观测。
```

不再要求：

```text
div_valid_years = firm_years
rep_valid_years = firm_years
```

按 1980–2005 年中可观察到的支付记录累计：

```text
div_years
rep_years
```

并继续使用论文原有分组：

```text
0
1–5
6–10
11–15
16–20
>20
```

### 2.3 Group I–V

Group I–V 改为直接依据 Table 2 的论文近似支付年份数进行固定分类。

不再要求公司拥有完整支付历史，也不再因为部分年度支付状态缺失而自动标记为 `Unclassifiable`。

仍沿用既有 Group I–V 数量阈值，不在本补丁中重复。

### 2.4 不得引入的替代方案

本次修订明确取消以下此前建议：

- 支付年份上下界区间分类；
- “只有上下界位于同一分组才可分类”；
- 完整历史口径作为主样本进入标准。

如保留完整历史结果，只能作为额外 QA 或敏感性输出，不得替代论文近似口径的主表、主图和主回归。

---

## 3. 净回购：增加现金流数据作为“可观察的替代测量”

既有的库存股法和注销法优先顺序保留，但增加以下替代路径。

### 3.1 主优先级

净回购应按以下顺序构造：

#### 第一优先：库存股变动

当同一公司准确的 `fyear - 1` 与本年 `TSTKC` 均可观察，且两年不同时为 0 时：

```text
repurchase = TSTKC_t - TSTKC_t-1
repurchase_source = treasury_stock_change
```

#### 第二优先：明确识别的注销法

当连续两年真实观察到：

```text
TSTKC_t = 0
TSTKC_t-1 = 0
```

且 `PRSTKC`、`SSTK` 均非缺失时：

```text
repurchase = PRSTKC - SSTK
repurchase_source = retirement_method
```

#### 第三优先：现金流替代测量

当无法获得可用的连续两年 `TSTKC`，但：

```text
PRSTKC 非缺失
SSTK 非缺失
```

时，允许使用：

```text
repurchase = PRSTKC - SSTK
repurchase_source = cashflow_fallback
```

该情况只表示：

> 库存股变动不可观察时，使用现金流量表中可观察到的股票购买减股票发行作为替代测量。

不得将 `cashflow_fallback` 错误标记为或解释为“已经确认企业采用注销法”。

### 3.2 仍然保持的限制

以下规则不变：

- `PRSTKC` 与 `SSTK` 任一缺失时，现金流净回购无法计算；
- 原始输入不完整且不存在可用替代测量时，`repurchase = NaN`；
- 只有已经成功计算的净回购为负时，才设为 0；
- 不得对 `TSTKC`、`PRSTKC`、`SSTK` 无条件 `fillna(0)`。

### 3.3 建议实现

```python
df["repurchase"] = np.nan
df["repurchase_source"] = pd.NA

tstkc_pair = (
    df["tstkc"].notna()
    & df["tstkc_lag1"].notna()
)

retirement_method = (
    tstkc_pair
    & df["tstkc"].eq(0)
    & df["tstkc_lag1"].eq(0)
)

treasury_method = (
    tstkc_pair
    & ~retirement_method
)

cashflow_complete = (
    df["prstkc"].notna()
    & df["sstk"].notna()
)

df.loc[treasury_method, "repurchase"] = (
    df.loc[treasury_method, "tstkc"]
    - df.loc[treasury_method, "tstkc_lag1"]
)
df.loc[treasury_method, "repurchase_source"] = (
    "treasury_stock_change"
)

retirement_complete = (
    retirement_method
    & cashflow_complete
)
df.loc[retirement_complete, "repurchase"] = (
    df.loc[retirement_complete, "prstkc"]
    - df.loc[retirement_complete, "sstk"]
)
df.loc[retirement_complete, "repurchase_source"] = (
    "retirement_method"
)

cashflow_fallback = (
    ~tstkc_pair
    & cashflow_complete
)
df.loc[cashflow_fallback, "repurchase"] = (
    df.loc[cashflow_fallback, "prstkc"]
    - df.loc[cashflow_fallback, "sstk"]
)
df.loc[cashflow_fallback, "repurchase_source"] = (
    "cashflow_fallback"
)

df["repurchase"] = df["repurchase"].clip(lower=0)
```

---

## 4. 行业筛选：历史行业代码优先于当前行业代码

删除既有规则：

```text
只要 sic 或 sich 任一字段落入金融业或公用事业区间，就剔除该公司年度。
```

改为先构造唯一行业代码：

```python
df["sic_use"] = df["sich"].where(
    df["sich"].notna(),
    df["sic"],
)
```

含义：

1. `sich` 非缺失时，使用公司该历史年度的行业代码；
2. `sich` 缺失时，才使用当前或表头行业代码 `sic`；
3. 行业排除仅依据 `sic_use`。

然后排除：

```text
金融业：6000–6999
公用事业：项目当前统一采用的既定区间
```

不得再使用：

```python
sic_in_excluded_range | sich_in_excluded_range
```

作为行业剔除条件。

QA 中应分别报告：

- 使用 `sich` 的公司年度数；
- 因 `sich` 缺失而使用 `sic` 的公司年度数；
- `sich`、`sic` 均缺失的公司年度数；
- 按 `sic_use` 排除的金融业和公用事业公司年度数。

---

## 5. 在截取正式窗口前准备所需滞后年度

所有滞后变量必须先在扩展年份数据中构造，再截取正式分析期间。

不得先截取：

```text
1970–2005
1980–2005
```

然后再生成滞后项。

最低年份需求：

| 正式分析起点 | 构造需要 | 最迟应从何年开始保留 |
|---|---|---:|
| Figure 1：1970 | `TSTKC_{t-1}` | 1969 |
| Table 1/Table 2：1980 | `TSTKC_{t-1}` | 1979 |
| Table 3：1980 | `AT_{t-1}` | 1979 |
| Table 3：1980 | `PRCC_F/AJEX` 的 `t-3` | 1977 |

因此，主数据清洗和变量构造阶段应至少保留：

```text
1977–2005
```

如 Figure 1 的回购系列需要从 1970 年开始准确计算，则还应额外保留 1969–1976 年用于 Figure 1 的回购构造。更稳妥的统一方案是：

```text
读取并清洗 1969–2005 年；
完成所有滞后变量匹配；
再分别截取各表和各图的正式年份。
```

必须区分：

- 数据库真正不存在历史年度；
- 因代码先截取分析期而人为丢失历史年度。

后者属于程序错误，不能作为缺失值处理。

---

## 6. Python 与 Stata 的前后一致性和目的统一性

### 6.1 统一研究目的

Python 和 Stata 的共同目的只有一个：

> 按同一论文复现口径构造样本、变量和公司分组，并复现 Table 1、Table 2、Table 3 及相关图形。

任何代码修改都不得以“尽可能增加样本量”为独立目标。样本量增加只能来自：

- 改正与论文不一致的进入条件；
- 使用真实可观察的现金流替代测量；
- 改正历史行业识别；
- 修复分析窗口前历史年度被提前截断的问题。

不得通过以下方式扩大样本：

- 将缺失支付值改为 0；
- 使用不连续年度作为滞后年度；
- 对回购、价格、资产或回归变量插值；
- 在 Python 与 Stata 中使用不同样本筛选条件。

### 6.2 Python 作为统一的数据构造入口

Python 应负责并固定以下内容：

- 基础样本筛选；
- `sic_use` 构造与行业排除；
- 精确 `fyear - 1`、`fyear - 3` 匹配；
- 净回购及 `repurchase_source`；
- Table 1、Table 2 的论文近似窗口进入；
- Group I–V 固定分类；
- Table 3 的所有解释变量和因变量；
- 每个回归规格所需的样本标记。

Python 导出给 Stata 的数据必须已经包含最终变量，不应要求 Stata 再次解释原始 Compustat 字段。

建议至少导出：

```text
gvkey
fyear
group_id
repurchase
repurchase_dummy
repurchase_source
regular_dummy
roa
roa_regular
past_stock_return
cash
eso_dilution
sample_A_1980_1994
sample_A_1995_2005
sample_A_1995_2005_eso
sample_B_1980_1994
sample_B_1995_2005
sample_B_1995_2005_eso
```

### 6.3 Stata 只负责按同一口径估计 Table 3

Stata `.do` 文件不得再次：

- 重建净回购；
- 填充原始缺失值；
- 重新定义 Group I–V；
- 重新筛选行业；
- 使用不同的窗口进入条件；
- 自行生成与 Python 不同的滞后变量。

Stata 应直接使用 Python 导出的最终数据和样本标记执行 Logit。

示例：

```stata
logit repurchase_dummy roa past_stock_return cash ///
    if sample_A_1980_1994 == 1

logit repurchase_dummy roa past_stock_return cash eso_dilution ///
    if sample_A_1995_2005_eso == 1
```

### 6.4 Python 回归与 Stata 回归必须使用同一行样本

如同时保留 Python `statsmodels` 和 Stata Logit：

1. 两者必须使用同一份 Python 清洗后数据；
2. 两者必须使用相同的因变量、自变量、常数项和年份区间；
3. 每个模型的样本量必须完全一致；
4. Python 与 Stata 的因变量中 0 和 1 的数量必须一致；
5. 若样本量不一致，应停止结果汇总并输出错误，不得继续把两套结果并列。

建议增加自动核验：

```text
Python N == Stata N
Python y=1 数量 == Stata y=1 数量
Python y=0 数量 == Stata y=0 数量
```

### 6.5 修改顺序必须一致

当本补丁中的任一数据规则发生修改时，必须依次执行：

```text
重新运行 Python 清洗
→ 重新生成 Table 1、Table 2 和 Group I–V
→ 重新生成 Table 3 回归数据 CSV/DTA
→ 重新运行 Stata
→ 核对 Python/Stata 样本量
→ 更新报告中的表、图和样本审计
```

禁止在 Python 数据未重新导出的情况下，仅修改 Stata `.do` 并沿用旧 `.dta`。

---

## 7. 本次修订后的验收项目

- [ ] 删除所有“支付状态必须在全部实际存在年度完整”的主样本进入条件；
- [ ] Table 1 按窗口内至少 1 年非缺失数据进入；
- [ ] Table 2 按 1980–2005 年至少 1 年非缺失数据进入；
- [ ] 支付年份数根据可观察到的正支付记录累计；
- [ ] 部分年度支付状态缺失不再导致整家公司退出；
- [ ] 不使用支付年份上下界分类；
- [ ] 库存股变化不可观察但现金流字段完整时，使用 `cashflow_fallback`；
- [ ] `cashflow_fallback` 不被标记为注销法；
- [ ] 行业筛选使用 `sich` 优先、`sic` 补充的 `sic_use`；
- [ ] 所有滞后变量在截取正式分析窗口前构造；
- [ ] 1970 年回购具有 1969 年历史数据支持；
- [ ] 1980 年回购和 ROA 具有 1979 年历史数据支持；
- [ ] 1980 年三年股票收益具有 1977 年历史数据支持；
- [ ] Python 是统一变量和样本构造入口；
- [ ] Stata 不重复清洗或重新定义样本；
- [ ] Python 与 Stata 的六个 Table 3 模型样本量完全一致；
- [ ] 所有表、图、回归和报告使用同一套修订后数据。
