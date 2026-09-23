# 审计脚本与记录（audit）

本目录保存**一次性审计脚本**及其落盘证据。它们不是算法流水线的一部分，
但每一个都对应一条**写进了参赛材料的结论**，保留在这里是为了让结论可被逐条复核。

> **目录改名说明**：本目录原为三个未命名的临时目录
> `_audit_tmp/`、`_audit_tmp2/`、`_audit_tmp3/`（未纳入 git，无说明），
> 2026-09-23 统一收拢到 `code/experiments/audit/` 并补上本说明。
> 其中 `m1_cave71_spinup.py` 是早期的一次性脚本，其功能已被正式的
> `code/experiments/diag_spinup_cave71.py` 取代并**带落盘**（`code/results/diag_spinup_cave71.csv`），
> 但原件仍保留以备溯源。

## 文件清单

| 文件 | 作用 | 对应结论与正式落盘 |
|---|---|---|
| `audit_M1_M6_report.md` | 六项整改（M1–M6）的审计报告：逐项列出问题、证据与处置 | 是 §M2（PS vs PSC）、§M5（一阶传递函数重新锚定）的原始记录 |
| `m2_ps_vs_psc.py` | 实测 POWER API 的 `PS` 与 `PSC` 两列差异 | **驱动变量必须用 `PSC`**（订正到窟址高程 1140 m）。`tools/` 的 `render` 与 `docs/06_佐证材料.md` 引用此结论 |
| `m2_ps_psc_impact.csv` | 上脚本的落盘结果（两列对照 + 与标准大气公式的偏差） | 同上 |
| `m5_firstorder_reanchor.py` | 把初稿的一阶传递函数**重新锚定**到同一测试段，区分「递归推演」与「无自回归」两种实现 | `docs/01_技术路线.md` §4.5、`docs/03_作品方案.md` §5.3 的「抓到了形状、丢掉了量级」结论 |
| `m5_protocols.csv` | 上脚本的落盘结果（各实现口径下的 AUC / F1 / 召回 / 校准阈值） | 同上；正式版见 `code/results/derisk01_exceedance.csv` 与 `derisk02_events.csv` |
| `m1_cave71_spinup.py` | 第 71 窟标定自旋期敏感性（一次性版本） | **已被 `code/experiments/diag_spinup_cave71.py` 取代**（后者落盘 `code/results/diag_spinup_cave71.csv` 与 `.json`，含 94.67%→82.50% 两行） |
| `inspect_iccp_stages.py` | 逐阶段检查 ICCP 数据筛选（12 洞 → 9 洞 → 8 洞）每一步淘汰了哪些洞 | `docs/01_技术路线.md` §7.3、`docs/03_作品方案.md` 附录 1 的筛选链条 |
| `verify_cols.py` | 核对 `validate_crosscave.csv` 的列与 `pass` 口径 | `docs/01_技术路线.md` 的「6 项验收指标中 5 项落在文献区间内」 |

## 引用纪律

参赛材料里的数字**必须能指到 `code/results/*.csv` 或本目录的落盘文件**。
若本目录的结论与 `code/results/` 冲突，**以 `code/results/` 为准**——
本目录的脚本多数运行在整改前，其数值可能对应旧口径（例如 PS 驱动、旧 β 网格）。
