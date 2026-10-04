# 石窟天盾 · 风险预警控制台（**备选版 v2**）

本目录是 `frontend/`（原版）的**独立副本 + 增量修订**，专供对比选择。

- **原版 `frontend/` 一字未改**，两版可同时构建、同时运行、互不干扰（端口分别 5180 / 5181）。
- Vue 3 + TypeScript + Vite + ECharts 的纯前端演示控制台，所有数据均为**实验落盘结果硬编码**
  （`src/data/*.ts`，由 `tools/build_frontend_data_v2.py` 从 `code/results/*.csv` 生成），
  无后端、无网络请求、不引用任何 CDN。
- 项目总说明见仓库根 `README.md`；口径红线见 `docs/03_作品方案.md`。

```bash
cd frontend-v2
npm install            # 若 frontend/node_modules 已装好，可用 junction 复用，见文末
npm run dev            # http://127.0.0.1:5181
npm run build          # 产物在 frontend-v2/dist，相对基址 './'，可直接双击 index.html
```

数据重生（改完 `code/results/*.csv` 后必须执行）：

```bash
python tools/build_frontend_data_v2.py                # -> frontend-v2/src/data/*.ts
python code/experiments/build_demo_alarm_window.py    # 只在需要重算「预警触发窗口」时跑，约 14 min
```

目视核验（无头 Chrome 逐路由截图 + 抓控制台报错）：

```bash
python -m http.server 4174 --directory frontend-v2/dist
node tools/shoot_frontend.mjs --base http://127.0.0.1:4174 --out _shots_v2
```

---

## v2 相对原版的四处差异

### 1. ★ 新增「预警触发窗口」演示场景（真阳性，带提前量）

**原版的问题**：三个演示窗口是**按未来 72 h 内真实窟内 RH 峰值的分位数**挑的
（`code/experiments/build_demo_forecast.py:195`，0.9999 / 0.98 / 0.50）。这个规则会优先挑中
「真实峰值高、但模型读出偏低」的窗口，结果三个窗口**全部 0 报警**——评委在首屏看到的永远是
「预报 → 风险 → 0 报警」，从未见过一次完整闭环。

**但模型是报得出来的**：测试段 24 h / 62% 档召回 14.8%，94 次起报事件命中 33 次。
命中的窗口就在数据里，只是原规则选不中。

**v2 的做法**：`code/experiments/build_demo_alarm_window.py` 在测试段上**逐起点扫描**，
用标定段选出的同一套主读出与同一套按基准率标定的门限求逐小时 `level`，挑选
**「模型确实报警 ∧ 真实值确实超阈」且提前量最大**的窗口，单独写出：

| 文件 | 说明 |
| --- | --- |
| `code/results/demo_alarm.csv` | 73 行，字段与 `demo_forecast.csv` **逐字段一致** |
| `code/results/demo_alarm_summary.json` | 起点、读出峰值、真值峰值、首次报警/超阈时刻、提前量 |
| `code/results/demo_alarm_candidates.csv` | 前 10 名候选，便于人工复核挑选是否合理 |
| `code/results/demo_alarm_log.txt` | 完整运行日志 |

**原版四个产物（`demo_forecast.csv` / `demo_calibration.csv` / `demo_history.csv` /
`demo_stats.json`）本脚本一律不写**，原三个窗口的数值与顺序完全不变。

界面上，新窗口排在情景切换的第一位，表格里以「真阳性 / 教学样例」徽标明示两类窗口的**挑选规则差异**，
并写明提前量与首次报警时刻——差别在挑窗口的规则，不在模型读数。

### 2. 模型显示名在**数据层**清洗（不再靠视图层正则）

原版在 6 个渲染点各自 `replace(/\(.*?\)/g, '')`，正则散落、新增表格忘套就会漏出 CSV 里的内部后缀。
v2 由 `tools/build_frontend_data_v2.py` 的 `model_label()` 直接产出 `label` 字段：

- `models24[]`、`leadtime[]`、`baselines[]` 均新增 `label: string`；
- `model` 字段保留 CSV 原始名，**可溯源**；视图只渲染 `label`。

### 3. 删掉一处自我标榜的句子

`ValidationView` 原写「……这正是演示窗口出现漏报的物理来源之一。**我们把它写进材料而不是隐藏。**」
后半句属于表态而非信息，v2 只删后半句，前半句的物理归因保留。

### 4. 页脚口径说明改为中性表述

原版 `DEMO_HONEST_NOTE` 写「本窗口读出峰值未触及判定线」——对新增的真阳性窗口不成立。
v2 改为说明**四窗挑选规则不同**，逐窗口口径在指挥台卡片内标注。

---

## 口径纪律（两版一致，不得违反）

1. **端到端口径**（真实预报驱动：AUC 0.862→0.903、F1 0.072→0.164）与
   **可部署性上界口径**（以真实未来再分析替代预报：检出率 35.1%）必须**分开呈现并标注**，
   两者不得混读。
2. 提前量 46.3 h 必须带「**事件前 72 h 窗口内滚动预报口径**」字样。
3. twCRPS 表述为「在 MSE 目标上**引入**阈值加权风险项」，**不能写「替代 / 换成 MSE」**。
4. 窟内序列必须标注「**文献标定物理模型生成的合成标签**」。
5. 决策输出标注「**辅助建议，供管理人员研判**」。
6. 不利数据保留但用过程性叙述（ISD 湿度相关 0.576、75% 档检出仅 9.1%、原三个演示窗口未触发限流），
   **别造假数据**。
7. `demo_stats.json` 的 `frac_gt62/67/75` 已是百分数，不得再乘 100。
8. ICCP 第 12 洞 Te'omim（`target_sd = 0.000`）按管线门限剔除；极端负 R² 截断到 −1 仅供绘图，
   **胜出计数必须用原始 R² 另算**。
9. `RH_pred` 是分位数回归的**上分位读出（τ=0.95）**，不是预测分布中位数，界面**禁止出现 P50**。

## 复用 `frontend/node_modules`（免联网安装）

```powershell
cmd /c mklink /J "F:\Desktop\ai气象大赛\frontend-v2\node_modules" "F:\Desktop\ai气象大赛\frontend\node_modules"
```

v2 目录已建好此 junction；`node_modules/` 在 `.gitignore` 内，不会入库。
