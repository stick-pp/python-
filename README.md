# Skinner (2008) Replication

本仓库复现 Skinner (2008) 在 1970--2005 年样本期内的 Figure 1--3、Table 1--3。

## Repository layout

```text
python/                 数据清洗、变量构建、图形和表格源数据
stata/                  Table 3 的 Stata 复现与核验脚本
latex/                  中文学术报告生成脚本与 ElegantPaper 模板
docs/                   口径说明、诊断记录和排版规范
data/README.md          本地数据文件清单；原始数据不进入 Git
shared_artifacts/       阶段间本地产物；不进入 Git
```

## Workflow

1. Python 阶段读取本地 WRDS/CRSP/CCM 数据，输出 Figure 1--3、Table 1--2 和回归输入或结果到 `shared_artifacts/python_out/`。
2. Stata 阶段用于 Table 3 的独立回归核验，读取 Python 已定义的样本和变量，输出到 `shared_artifacts/stata_out/`。
3. LaTeX 阶段读取共享产物，生成中文报告到 `shared_artifacts/latex_out/`。

各阶段不得自行重定义上游样本。当前正式入口、依赖和运行命令见对应目录中的 `README.md`。

## Data policy

Compustat、CRSP、CCM 下载文件以及课程材料、论文 PDF、日志和生成结果均不提交到 Git。复现者需按 `data/README.md` 准备本地输入。仓库只保留可审计的代码、口径说明和模板。

## Branches

- `task/python`: Python 数据阶段。
- `task/stata`: Stata 回归核验阶段。
- `task/latex`: LaTeX 报告阶段。
- `main`: 仅接收已经验证的阶段提交。

