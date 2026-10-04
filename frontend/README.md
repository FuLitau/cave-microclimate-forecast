# 石窟天盾 · 洞窟微气候风险预警系统（前端）

Vue 3 + TypeScript + Vite + ECharts 的纯前端演示控制台。所有数据均为
**实验落盘结果硬编码**（`src/data/*.ts`，由 `tools/build_frontend_data.py`
从 `code/results/*.csv` 生成），无后端、无网络请求，`npm run build`
后可离线部署到任意静态托管。

## 运行

```bash
cd frontend
npm install        # 首次
npm run dev        # 开发模式，默认 http://localhost:5180
npm run build      # 产出 dist/（相对路径 base，可直接双击或静态托管）
```

## 页面

| 路由 | 内容 | 数据出处 |
|---|---|---|
| `#/overview` 风险总览 | 四项 KPI、四年窟内湿度环境、阈值暴露统计、决策映射、三层管线 | `derisk02_leadtime.csv`、`exp03_abc_ablation.csv`、`demo_history.csv`、`demo_stats.json` |
| `#/forecast` 预报看板 | 单窟 72h 分位数轨迹 + 三级阈值 + 建议时段，三场景切换 | `demo_forecast.csv` |
| `#/compare` 模型对比 | A/B/C 消融、多模型 AUC/F1、ICCP 逐洞、ISD 核对、跨窟验证、点预测基线 | `exp03_abc_ablation.csv`、`derisk02_events.csv`、`iccp_transfer.csv`、`isd_vs_power.csv`、`validate_crosscave.csv`、`derisk01_model_comparison.csv` |
| `#/algorithm` 算法说明 | 三层管线、闭式解与损失公式、特征族、方案演进叙事 | — |

## 口径约定（与提交材料一致）

- **端到端**（AUC 0.862→0.903、F1 0.072→0.164）：含 L1 预报误差的完整链路；
- **可部署性上界**（检出率 35.1%、提前 46.3h）：理想外场驱动，事件前 72h 窗口内滚动预报口径；
- 窟内序列为文献标定物理模型的**合成标签**（已显式声明），ICCP / 跨窟 / 同窟对照为三层外部验证；
- 演示数据以"洞窟"为通用对象，莫高窟为实例。
