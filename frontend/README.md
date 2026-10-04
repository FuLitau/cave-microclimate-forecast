# 石窟天盾 · 洞窟微气候风险预警系统（前端）

Vue 3 + TypeScript + Vite + ECharts 的纯前端演示控制台。所有数据均为
**实验落盘结果硬编码**（`src/data/*.ts`，由 `tools/build_frontend_data.py`
从 `code/results/*.csv` 生成），无后端、无网络请求、不引用任何 CDN。

## 运行

```bash
cd frontend
npm install        # 首次
npm run dev        # 开发模式，默认 http://localhost:5180
npm run build      # 产出 dist/（base 为相对路径）
```

演示时把 `dist/` 用任意静态服务器托管即可，例如：

```bash
python -m http.server 4173 --directory frontend/dist
# 浏览器打开 http://127.0.0.1:4173/
```

> 说明：路由用 hash 模式，所以除首页外都要带 `#`，例如 `http://127.0.0.1:4173/#/compare`。
> 用 `file://` 直接双击 `dist/index.html` 在现代浏览器里会被 ES module 的 CORS 策略拦住，
> 请用上面的静态服务器方式（同样完全离线）。

## 页面

| 路由 | 内容 | 主要数据出处 |
|---|---|---|
| `#/` 风险指挥台 | 三情景切换、72 h 读出曲线 + 三级阈值、决策时间轴、风险态势表盘、处置建议、四张 KPI 卡、四年背景态势 | `demo_forecast.csv`、`demo_calibration.csv`、`demo_history.csv`、`demo_stats.json`、`exp03_abc_ablation.csv`、`derisk02_leadtime.csv` |
| `#/compare` 效果对照 | A/B/C 六格消融、**R² 与 F1/AUC 的口径分歧**、94 事件命中点阵、分类指标、提前量、九个对照模型逐行说明、非线性读出对照 | `exp03_abc_ablation(_val).csv`、`exp03_verdict.csv`、`derisk02_events.csv`、`derisk02_leadtime.csv`、`derisk01_model_comparison.csv`、`derisk03_readout_compare.csv` |
| `#/validation` 可信度验证 | 三条外部证据链：物理一致性区间对照、ICCP 12 洞留窟迁移、ISD 实测驱动核对 | `validate_crosscave.csv`、`iccp_transfer.csv`、`isd_vs_power.csv` |
| `#/method` 方法说明 | 三层链路、twCRPS 定义与措辞澄清、258 维特征构成、读出权重、算子谱模态、特征族消融、复现命令 | `derisk02_readout.csv`、`derisk02_spectrum.csv`、`derisk01_model_comparison.csv` |

## 口径约定（与提交材料一致，改动前请先读这一节）

- **端到端**（AUC 0.862→0.903、F1 0.072→0.164）：含 L1 预报误差的完整链路；
- **可部署性上界**（检出率 35.1%、提前 46.3 h）：理想外场驱动，**事件前 72 h 窗口内滚动预报口径**，
  页面上必须带这句限定语，不能简写成「提前 46.3 小时」；
- twCRPS 的准确表述是「**在 MSE 目标上引入**阈值加权风险项」，不是「替代 / 换成 MSE」；
- 窟内序列是**文献标定物理模型生成的合成标签**，不是窟内实测；
- 主读出 `RH_pred` 是**分位数回归的 τ=0.95 上分位读出**，不是预测分布中位数——
  页面上不得出现 P50 字样；
- 决策输出一律标注「辅助建议，供文保管理人员研判，不构成自动控制指令」；
- 不利结果照实保留：ISD 湿度相关仅 r=0.576、75% 档检出率低、演示窗口内模型 0 报警、
  Har Sifsof 洞劣于初稿传递式、`ΔR²(部署读出)` 六格全负。

## 数据管线

```bash
python tools/build_frontend_data.py     # 重算 code/results/*.csv -> src/data/*.ts
```

`src/data/` 下的 9 个文件全部由该脚本生成，**不要手改**。
管线里的两个坑已经处理，改脚本时注意别改回去：

1. ICCP 第 12 洞 Te'omim 的 `target_sd = 0.000`（常数序列）必须按门限剔除，
   否则 `R² ≈ -1e26` 会污染统计；
2. ICCP 的**截断与胜出计数必须分离**：胜出与否按原始 R² 判定，绘图值才截断到 −1，
   否则 Sela' 这类两个模型都低于 −1 的洞会被误判成平局（会从 7/8 算成 6/8）。

## 目视核验（改完 UI 必跑）

构建通过不等于能渲染。用无头 Chrome 逐路由截图并抓取控制台报错：

```bash
python -m http.server 4173 --directory frontend/dist   # 另开一个终端
node tools/shoot_frontend.mjs --base http://127.0.0.1:4173 --out _shots
```

脚本会输出每个路由的截图路径与视口高度；一旦出现未捕获异常、`console.error`
或非 favicon 的 4xx/5xx，退出码为 1。截图落在 `_shots/`（已 gitignore）。
