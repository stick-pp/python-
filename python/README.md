# Skinner (2008) Python 复现入口

## 正式入口

正式脚本：

```bash
python python/replicate_skinner_2008.py
```

该脚本生成当前 Python 阶段的正式结果：

- Table 1-3 源数据与 Python 回归结果；
- Figure 1-3 源数据与图片；
- 输出目录：项目级 `shared_artifacts/python_out/`。

## 本地输入

运行前需在项目根目录、仓库根目录或 `data/` 目录放置以下本地数据：

- `maindata.csv`
- `CCM Link Table.csv`
- `crsp_dse_names.csv`

这些数据文件不提交到 Git。具体来源见 `data/README.md`。

## 诊断脚本

`python/diagnostics/` 中保留仍有复现诊断价值的脚本。它们不是正式入口，不应覆盖正式结果口径。

## 非正式旧口径

`python/archive/` 中保留旧版本或隔离变体，仅用于追溯，不作为报告或交接的正式口径。
