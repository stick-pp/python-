# Codex 修改指示：Figure 1–3 共同样本逻辑与收益口径修订

> 本文件仅包含本次指定修改内容。  
> Codex 必须严格按照本文件执行，不得擅自加入其他理解、替代口径或额外处理。

---

## 1. 共同样本逻辑修改

### 1.1 为 Figure 1–3 单独建立纯 Compustat 样本

当前 Figure 1–3 中存在额外的 CRSP/CCM 股票层筛选。需要处理：

```text
CRSP/CCM 股票层筛选是额外加入的。
```

修改要求：

```text
为 Figure 1–3 单独建立纯 Compustat 样本。
```

即 Figure 1–3 的样本不得强制依赖：

```text
CCM Link Table
CRSP dse names
SHRCD
EXCHCD
LINKTYPE
LINKPRIM
PERMNO
CRSP name date interval
CCM link date interval
```

Figure 1–3 应使用单独的纯 Compustat 样本数据流程。

---

### 1.2 处理 `curcd == USD` 额外限制

当前 Figure 1–3 中存在：

```python
curcd == "USD"
```

该限制属于额外限制。

修改要求：

```text
对 curcd == USD 也是额外限制 进行处理。
```

Codex 需要将 Figure 1–3 的纯 Compustat 样本逻辑与当前带 `curcd == USD` 的逻辑区分开，不得让 `curcd == USD` 继续作为 Figure 1–3 主样本的强制限制。

---

## 2. 收益变量固定定义

Codex 必须在 Figure 1–3 使用的数据中构造以下两个变量：

```python
df["earnings_raw"] = df["ib"]

df["adjusted_earnings"] = np.where(
    df["ib"].notna(),
    df["ib"] - 0.6 * df["spi"].fillna(0),
    np.nan,
)
```

后续 Figure 1–3 的收益口径必须固定为：

```text
Figure 1 → earnings_raw
Figure 2 → adjusted_earnings
Figure 3 → adjusted_earnings
```

进一步固定为：

```text
Figure 1：earnings_raw
Figure 2：adjusted_earnings
Figure 3：adjusted_earnings < 0
```

---

## 3. Figure 1 修改要求

### 3.1 Figure 1 收益曲线

Figure 1 的 earnings 曲线必须使用：

```python
earnings_raw
```

即：

```python
df["earnings_raw"] = df["ib"]
```

### 3.2 Figure 1 Special items 缺失值

Figure 1 中 Special items 的缺失值处理必须修改为：

```text
Special items 的缺失值记为空值，不记为零。
```

因此不得继续使用：

```python
spi.fillna(0)
```

作为 Figure 1 Special items 曲线的主处理方式。

Figure 1 中 Special items 应保留缺失值为空值。

---

## 4. Figure 2 修改要求

### 4.1 Figure 2 收益变量

Figure 2 必须使用：

```python
adjusted_earnings
```

即：

```python
df["adjusted_earnings"] = np.where(
    df["ib"].notna(),
    df["ib"] - 0.6 * df["spi"].fillna(0),
    np.nan,
)
```

Figure 2 不得继续使用：

```python
ib
```

作为 earnings 曲线。

---

### 4.2 Figure 2 Panel B 单独重新校准

针对 Figure 2 Panel B，Codex 需要执行：

```text
尝试重新校准样本宇宙和分组。
```

限制条件：

```text
只针对 Figure 2 Panel B。
不要对其他已有成果造成影响。
推荐重新做一个脚本，而不是在原有 py 代码进行修改。
并作调整前后结果比对。
```

执行要求：

1. 为 Figure 2 Panel B 单独新建脚本。
2. 不在原有 `replicate_skinner_2008.py` 中直接修改 Figure 2 Panel B 主逻辑。
3. 新脚本仅用于 Figure 2 Panel B 的样本宇宙和分组重新校准。
4. 新脚本需要输出调整前后结果比对。
5. 新脚本不得改变 Figure 1、Figure 2 Panel A、Figure 3、Table 1、Table 2、Table 3 的已有成果。

---

## 5. Figure 3 修改要求

### 5.1 Figure 3 收益变量

Figure 3 必须使用：

```python
adjusted_earnings
```

### 5.2 Figure 3 亏损定义

Figure 3 必须严格按照以下代码修改亏损定义：

```python
df["adjusted_earnings"] = np.where(
    df["ib"].notna(),
    df["ib"] - 0.6 * df["spi"].fillna(0),
    np.nan,
)

df["loss"] = np.select(
    [
        df["adjusted_earnings"].lt(0),
        df["adjusted_earnings"].ge(0),
    ],
    [
        1.0,
        0.0,
    ],
    default=np.nan,
)
```

Figure 3 的亏损判断必须固定为：

```text
adjusted_earnings < 0
```

不得继续使用：

```python
ib < 0
```

---

## 6. 输出与比对要求

### 6.1 Figure 1–3 口径固定

最终输出中必须保证：

```text
Figure 1：earnings_raw
Figure 2：adjusted_earnings
Figure 3：adjusted_earnings < 0
```

### 6.2 Figure 2 Panel B 调整前后比对

新建 Figure 2 Panel B 校准脚本后，必须输出调整前后结果比对。

比对内容至少包括：

```text
调整前 Figure 2 Panel B 源数据
调整后 Figure 2 Panel B 源数据
调整前后 Group I、III、IV、V 公司数
调整前后各年度 adjusted_earnings 汇总值
调整前后图像文件
```

### 6.3 不影响其他已有成果

Codex 必须确保 Figure 2 Panel B 的单独校准不会改变：

```text
Figure 1
Figure 2 Panel A
Figure 3
Table 1
Table 2
Table 3
已有回归结果
已有输出文件
```

如需要输出新结果，应使用新的文件名或新目录，避免覆盖已有成果。

---

## 7. 验收标准

- [ ] Figure 1–3 已建立纯 Compustat 样本流程；
- [ ] Figure 1–3 不再强制使用 CRSP/CCM 股票层筛选；
- [ ] Figure 1–3 不再将 `curcd == USD` 作为主样本强制限制；
- [ ] 已构造 `earnings_raw = ib`；
- [ ] 已构造 `adjusted_earnings = ib - 0.6 * spi.fillna(0)`，且 `ib` 缺失时结果为缺失；
- [ ] Figure 1 使用 `earnings_raw`；
- [ ] Figure 1 中 Special items 缺失值为空值，不记为零；
- [ ] Figure 2 使用 `adjusted_earnings`；
- [ ] Figure 2 Panel B 已通过新脚本单独尝试重新校准样本宇宙和分组；
- [ ] Figure 2 Panel B 已输出调整前后结果比对；
- [ ] Figure 2 Panel B 的校准没有影响其他已有成果；
- [ ] Figure 3 使用 `adjusted_earnings`；
- [ ] Figure 3 的 `loss` 严格按 `adjusted_earnings < 0` 定义；
- [ ] 最终固定口径为：Figure 1 = `earnings_raw`，Figure 2 = `adjusted_earnings`，Figure 3 = `adjusted_earnings < 0`。
