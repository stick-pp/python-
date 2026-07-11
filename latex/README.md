# LaTeX report builder

This directory contains the LaTeX-only report generation assets for the Skinner (2008) replication project.

## Contents

- `build_replication_report.py`: builds `build_report/replication_report.tex` from shared Python outputs.
- `elegantpaper.cls`: local ElegantPaper class used by the generated report.
- `elegantpaper-cn-template.tex`: reference template retained for local LaTeX style compatibility.

## Inputs

The builder reads only shared outputs under:

- `shared_artifacts/python_out`

It does not modify Python or Stata worktrees.

## Outputs

The script writes intermediate LaTeX files to the worktree-local `build_report/` directory. That directory is ignored and should not be committed.

The final deliverables should continue to be placed under:

- `shared_artifacts/latex_out/复现报告.pdf`
- `shared_artifacts/latex_out/复现报告.tex`

## Basic Usage

From the `worktrees/latex` directory:

```powershell
python .\latex\build_replication_report.py
```

If XeLaTeX is available, compile from `build_report/`:

```powershell
xelatex -interaction=nonstopmode -halt-on-error replication_report.tex
xelatex -interaction=nonstopmode -halt-on-error replication_report.tex
```
