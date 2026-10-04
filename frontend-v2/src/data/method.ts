// 方法层：读出权重与算子谱
// 出处：code/results/derisk02_readout.csv、derisk02_spectrum.csv
// 权重为标准化特征上的岭回归系数，只反映「哪个特征对读出贡献大」，不是因果效应。
// 本文件由 tools/build_frontend_data_v2.py 自动生成，请勿手改。

export interface ReadoutWeight { feature: string; weight: number; absWeight: number; family: string; desc: string }
/** |权重| 最大的 18 个特征 */
export const readoutWeights: ReadoutWeight[] = [
  { feature: "q_ma24", weight: 8.371, absWeight: 8.371, family: "水汽通量", desc: "通风带走的绝对水汽量滑动均值" },
  { feature: "RHslow_ma24", weight: -6.5522, absWeight: 6.5522, family: "慢变背景", desc: "室外驱动的长窗滑动均值，刻画季节背景" },
  { feature: "T2M_lag23", weight: -5.3855, absWeight: 5.3855, family: "快变延迟", desc: "室外驱动的过去值，刻画窟体热惯性与水汽滞后" },
  { feature: "T2M_ma720", weight: 5.2861, absWeight: 5.2861, family: "慢变背景", desc: "室外驱动的长窗滑动均值，刻画季节背景" },
  { feature: "T2M_lag0", weight: -5.1352, absWeight: 5.1352, family: "瞬时外场", desc: "当前时刻的室外驱动值" },
  { feature: "T2M_ma2160", weight: -5.0787, absWeight: 5.0787, family: "慢变背景", desc: "室外驱动的长窗滑动均值，刻画季节背景" },
  { feature: "RH2M_lag0", weight: 4.6319, absWeight: 4.6319, family: "瞬时外场", desc: "当前时刻的室外驱动值" },
  { feature: "T2M_lag46", weight: -4.2965, absWeight: 4.2965, family: "快变延迟", desc: "室外驱动的过去值，刻画窟体热惯性与水汽滞后" },
  { feature: "T2M_lag47", weight: 3.7015, absWeight: 3.7015, family: "快变延迟", desc: "室外驱动的过去值，刻画窟体热惯性与水汽滞后" },
  { feature: "PSC_lag5", weight: -3.6784, absWeight: 3.6784, family: "快变延迟", desc: "室外驱动的过去值，刻画窟体热惯性与水汽滞后" },
  { feature: "PSC_lag29", weight: -3.5245, absWeight: 3.5245, family: "快变延迟", desc: "室外驱动的过去值，刻画窟体热惯性与水汽滞后" },
  { feature: "PSC_lag9", weight: 3.2434, absWeight: 3.2434, family: "快变延迟", desc: "室外驱动的过去值，刻画窟体热惯性与水汽滞后" },
  { feature: "q_ma720", weight: -3.1925, absWeight: 3.1925, family: "水汽通量", desc: "通风带走的绝对水汽量滑动均值" },
  { feature: "T2M_ma24", weight: 3.0613, absWeight: 3.0613, family: "慢变背景", desc: "室外驱动的长窗滑动均值，刻画季节背景" },
  { feature: "PSC_lag33", weight: 2.8886, absWeight: 2.8886, family: "快变延迟", desc: "室外驱动的过去值，刻画窟体热惯性与水汽滞后" },
  { feature: "T2M_lag24", weight: 2.8264, absWeight: 2.8264, family: "快变延迟", desc: "室外驱动的过去值，刻画窟体热惯性与水汽滞后" },
  { feature: "T2M_lag9", weight: 2.6708, absWeight: 2.6708, family: "快变延迟", desc: "室外驱动的过去值，刻画窟体热惯性与水汽滞后" },
  { feature: "PSC_lag42", weight: 2.6501, absWeight: 2.6501, family: "快变延迟", desc: "室外驱动的过去值，刻画窟体热惯性与水汽滞后" }
]

export interface SpectrumMode { absLambda: number; tauHours: number; periodHours: number; periodDays: number }
export const spectrum: SpectrumMode[] = [
  { absLambda: 0.9992, tauHours: 1206.6, periodHours: 12.0, periodDays: 0.5 },
  { absLambda: 0.9992, tauHours: 1206.6, periodHours: 12.0, periodDays: 0.5 },
  { absLambda: 0.9995, tauHours: 2153.18, periodHours: 24.0, periodDays: 1.0 },
  { absLambda: 0.9995, tauHours: 2153.18, periodHours: 24.0, periodDays: 1.0 },
  { absLambda: 0.9998, tauHours: 4206.08, periodHours: 6280.31, periodDays: 261.68 },
  { absLambda: 0.9998, tauHours: 4206.08, periodHours: 6280.31, periodDays: 261.68 },
  { absLambda: 1.0, tauHours: 22200.41, periodHours: 8749.91, periodDays: 364.58 },
  { absLambda: 1.0, tauHours: 22200.41, periodHours: 8749.91, periodDays: 364.58 },
  { absLambda: 0.9998, tauHours: 6260.32, periodHours: 71195.73, periodDays: 2966.49 },
  { absLambda: 0.9998, tauHours: 6260.32, periodHours: 71195.73, periodDays: 2966.49 }
]

export interface LayerDef {
  id: string; title: string; subtitle: string; detail: string; io: string
}
export const layers: LayerDef[] = [
  {
    id: 'L1',
    title: '室外气象驱动',
    subtitle: '公开观测与再分析',
    detail: 'NASA POWER 逐小时 2001–2025（219,144 行、零缺测）提供室外场；敦煌国家站 ISD 报文作为独立真实性对照。',
    io: 'T2M · RH2M · WS10M · PSC · ALLSKY_SFC_SW_DWN',
  },
  {
    id: 'L2',
    title: '风险对齐可微输运读出',
    subtitle: '本作品的核心算法创新',
    detail: '把窟内微气候看作室外轨迹经过窟体热湿惯性的可微输运结果：构造 258 维因果特征（240 快变延迟 + 12 慢变均值 + 6 Magnus 比值），学习作用在室外轨迹上的读出算子。',
    io: '258 维特征 → 窟内 RH 的 24/48/72 h 预报',
  },
  {
    id: 'L3',
    title: '阈值加权风险目标',
    subtitle: '把业务判据写进损失函数',
    detail: '在 MSE 目标上引入阈值加权连续排序概率分数（twCRPS），让训练直接惩罚「在 62 / 67 / 75% 阈值附近判错」，而不是只惩罚平均误差。',
    io: '分级预警 · 风险概率 · 限流建议',
  },
]
