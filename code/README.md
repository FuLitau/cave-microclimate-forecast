# 石窟微气候风险预测 —— 风险对齐的可微物理代理训练

第八届全球校园人工智能算法精英大赛 · 算法主题赛（智慧气象）· 方向二

代码仓库：<https://github.com/FuLitau/cave-microclimate-forecast>

> **一句话**：在窟内微环境**无实测标签**、且损伤判据是"**阈值超越 + 持续时间**"的条件下，
> 用一个**闭式解、可微、可解释**的延迟嵌入输运算子把室外气象轨迹映射为窟内湿度风险代理，
> 并以此驱动**风险对齐**的训练目标，而不是均方误差。

---

## 核心结果（24 h 时效，62% 业务阈值）

| 模型 | AUC | F1 | 预警检出率 | 平均提前量 | 可部署 |
|---|---|---|---|---|---|
| [oracle] Persistence | 0.836 | 0.092 | — | — | ❌ 需窟内实测 |
| **Operator-direct（本作品）** | **0.818** | **0.099** | **34.0%** | **42.6 h** | ✅ |
| Climatology | 0.734 | 0.002 | — | — | ✅ |
| **FirstOrderTransfer（初稿方案）** | **0.499** | **0.000** | **0.0%** | **从不预警** | ✅ |

- 算子在 **48 h / 72 h 时效上 AUC 反超 oracle**（0.783 / 0.767 vs 0.749 / 0.709）。
- 初稿的"文献标定一阶传递函数" **AUC 与随机无异**，且递归 72 步数值发散。
- 在 MSE 训练下窟内 RH 的 R² 可达 0.42，但**超阈事件 F1 = 0.000**——
  模型从不预报任何一次超阈。这是**目标函数错配**的直接实证。

---

## 快速开始

```bash
pip install -r requirements.txt

# 1) 抓取外场数据（NASA POWER 逐小时，2001-2025，约 220k 行）
python src/data/power.py

# 2) 窟内物理模型标定核对（对照文献实测传递比）
python experiments/calib_verify.py

# 3) 多时效预报对比 + 消融（24/48/72 h）
python experiments/derisk_02_multihorizon.py

# 4) 风险对齐训练 A/B/C 消融
python experiments/exp03_risk_aligned.py

# 5) 外部效度：跨窟留一 + 同窟同期 + ICCP 真实洞穴
python experiments/validate_crosscave.py
python experiments/validate_iccp.py        # 需要先下载 ICCP（见下）

# 6) 演示看板（本地离线，无 CDN 依赖）
python src/web/app.py                      # http://127.0.0.1:5000
```

ICCP 真实观测数据的获取（Zenodo 会拦截缺少浏览器特征的请求）：

```bash
python tools/fetch_iccp.py                 # 已内置请求头与指数退避重试
```

全部结果写入 `results/`。**纯 CPU 可运行**（算子层为闭式解，无 BPTT）。

---

## 目录结构

```
├── src/
│   ├── data/power.py            NASA POWER 抓取（含 6 个实测坑的注释）
│   ├── physics/cave_model.py    窟内热湿耦合物理模型（矩阵指数精确离散化）
│   ├── operator/transport.py    延迟嵌入 EDMD/Koopman 输运算子（闭式解）
│   └── losses/twcrps.py         twCRPS 阈值加权评分 + 内生权重 + 三级决策
├── experiments/
│   ├── calib_cave_params.py     参数标定（对文献实测传递比）
│   ├── calib_verify.py          标定核对
│   ├── derisk_01_transport.py   解风险实验 01：同时刻重建
│   ├── derisk_02_multihorizon.py 解风险实验 02：24/48/72h 多步预报 + 消融
│   ├── derisk_03_quantile_readout.py 分位数读出
│   ├── exp03_risk_aligned.py    实验 03：A/B/C 风险对齐消融
│   ├── test_nonlinear_readout.py 线性 vs 非线性读出（GBDT）
│   ├── validate_crosscave.py    跨窟留一外部效度
│   ├── calib_cave71_compare.py  同窟同期实测对照
│   └── validate_iccp.py         ICCP 真实洞穴外部效度
├── src/web/                     Flask 演示看板（本地 ECharts，断网可用）
├── data/{raw,interim}/          原始缓存与合并数据集（未纳入版本控制）
└── results/                     全部实验输出（CSV/JSON/日志）
```

---

## 方法要点

**三层链路**

```
外场公开数据 ─► L1 多时效概率预报 ─► L2 延迟嵌入输运算子 ─► L3 风险对齐训练 ─► 三级决策
```

**L2 输运算子**：Takens 嵌入 + EDMD，`Ψ(u_{t+1}) ≈ K·Ψ(u_t)`、`ĥ_t = wᵀ·Ψ(u_t)`，
`K, w` 均为**岭回归闭式解**。
特征由三族构成，每族对应明确物理量：快变延迟坐标 / 多尺度滑动均值（慢热状态）/
Magnus 比值项（温湿耦合非线性）。

**L3 风险对齐**：把训练目标从 MSE 换成阈值加权评分规则（twCRPS，
Gneiting & Ranjan 2011），使模型在"超阈时长"这一业务量上最优。

---

## 数据与诚信声明

- **窟内温湿度无公开实测数据集。** 窟内序列为**文献参数化物理模型生成的合成标签**
  （`physics-derived synthetic`），**不是实测**。详见 [数据集方案](../docs/02_数据集方案.md)。
- POWER 为 **reanalysis**（MERRA-2 + 偏差订正），**不是站点观测**。
- 敦煌国家气象站（ISD 52418）**2023-04-28 之后停止上报**，2023-05 起无免费实测真值。
- 合成标签闭环**仅用于算法开发**；泛化性由三条独立链路检验（见下）。

## 外部效度：三条独立链路

### 链路一：跨窟留一（第 71 窟标定 → 第 87 窟检验）

6 项传递结构指标中 **5 项通过**（含年周期温度相位滞后 1.0 月 vs 实测 1 个月）。
但两个洞窟用的都是**本项目物理模型的输出**，仍有"用模型验证模型"的循环嫌疑。

### 链路二：同窟同期实测对照（第 71 窟 2019–2021，Gong et al. 2025）

标定目标（日较差比、年极差比、RH 年均、游客抬升）与检验量**分开**：
**温度统计量从未参与标定**，因此这是一次独立检验。结果见下节表格：
窟内年均气温差 **0.45 K**、气温最高差 0.22 K，但**冷端极值低估 5.35 K**——
最差的一项也如实报告，根因是未建模夜间长波辐射冷却。

复现：`python code/experiments/calib_cave71_compare.py`

### 链路三：ICCP 真实洞穴观测（**完全不含合成标签**）

数据：以色列洞穴气候计划，Zenodo `10.5281/zenodo.17505739`，CC-BY-4.0，
12 个岩溶洞穴 / 42 台记录仪 / 2019-09-19 → 2021-07-04 逐小时。
任务构造与"室外 → 窟内"同构：`Lighting_Zone = Light` 受光区逐时 RH 驱动 → `Dark` 深处逐时 RH 目标。

| 模型 | R² 中位数 | R²>0 洞数 | RMSE 中位数 (RH 百分点) |
|---|---|---|---|
| Persistence（洞口 RH 当深处，oracle） | **−2.282** | — | — |
| FirstOrderTransfer（初稿方案） | −0.255 | 3/8 | 7.18 |
| **Operator-Full（本作品）** | **+0.641** | **5/8** | **3.56** |

**算子优于一阶传递函数 7/8 洞，RMSE 减半。**
oracle Persistence 的 R² 中位数为 −2.28 ——「把洞口 RH 当作深处 RH」**比永远预测均值还差**，
说明**洞口与深处湿度强解耦**。这正是初稿查表式传递函数失效的物理原因。

⚠️ **边界（必须与数字同时阅读）**：ICCP 洞穴为石灰岩/白云岩、地中海气候，
莫高窟为砾岩—砂岩、干旱大陆性 → 只支持**相对比较**，不支撑绝对精度。
且 8 个有效洞中 Sela'（−6.41）、Murabba'at 2（−0.70）、Har Sifsof（−0.65）三洞 R² 为负；
Te'omim 因目标近似常数（深处 RH 恒 100%）被 `SD_FLOOR = 0.5` 守卫剔除。

复现：`python tools/fetch_iccp.py && python code/experiments/validate_iccp.py`

## 已知局限

| 项 | 模型 | 文献实测 | 差值 |
|---|---|---|---|
| 窟内 RH 年均 | 32.5% | 30.8% | +1.7 pp |
| 日较差比 开门 / 闭窟 | 0.251 / 0.045 | 0.276 / 0.043 | 阻尼略偏强 |
| 年极差比 T | **0.468** | 0.559 | **阻尼明显偏强** |
| 年极差比 RH | 0.830 | 0.722 | 阻尼略偏弱 |
| 窟内年均气温（同窟同期） | 12.45 °C | 12.0 °C | **+0.45 K** |
| 窟内气温最高（同窟同期） | 25.58 °C | 25.8 °C | −0.22 K |
| 窟内气温最低（同窟同期） | −1.35 °C | −6.7 °C | **+5.35 K（冷端低估）** |
| 窟内 RH 最低 / 最高（同窟同期） | 8.59 / 82.50% | 8.7 / 80.0% | −0.11 / +2.50 pp |
| 游客 RH 峰值抬升 | +0.10 pp | +11 pp | 未复现（脉冲被小时步长平均掉） |

⚠️ **两处读法纪律**：① 上表「同窟同期」行是与 Gong et al. 2025 第 71 窟 2019–2021 实测的
**同窟同期**对照，**温度统计量从未参与标定**，因而是独立检验；② **不比「窟内外温差」**——
POWER 再分析窟外年均 10.32 °C 与现场站 11.7 °C 本身相差 1.38 K，该口径不可用。
模型未显式建模长波辐射冷却与游客短时脉冲，二者已用等效参数补偿并在文档中声明。
**标定流程有一处已修复的缺陷**：初版只用外场前 30 天作初值，而 5 m 岩体导热链时间常数是月–年量级，
导致 RH 最高虚高 14.7 pp；加 2 年自旋期后降至 2.50 pp（详见 `docs/06_佐证材料.md` §5.6）。

---

## 引用

- Gneiting & Ranjan (2011), *Comparing density forecasts using threshold- and quantile-weighted
  scoring rules*, JBES. DOI 10.1198/jbes.2010.08110
- Brunton, Brunton, Proctor & Kutz (2017), *Chaos as an intermittently forced linear system*,
  Nat Commun 8. DOI 10.1038/s41467-017-00030-8（HAVOK / 延迟嵌入）
- Gong et al. (2025), *Impact of open visits on the indoor climate of Mogao Caves*,
  npj Heritage Science 13:173. DOI 10.1038/s40494-025-01740-9
- Zhao et al. (2026), *Single-sided natural ventilation in deep caves*, npj Heritage Science.
  DOI 10.1038/s40494-026-02955-0
- Zhang & Wang (2023), *Maintenance schedule optimization ... Cave 87*, Heritage Science 11:158.
  DOI 10.1038/s40494-023-01005-3
- Demas et al. (2015), *Strategies for Sustainable Tourism at the Mogao Grottoes*,
  Springer. DOI 10.1007/978-3-319-09000-9
- 敦煌研究院官方业务阈值 62% RH / 1500 ppm CO₂（樊锦诗 2013、郭青林 2026、汪万福公开表述）

完整参考文献见 [技术路线](../docs/01_技术路线.md) 与 [数据集方案](../docs/02_数据集方案.md)。
