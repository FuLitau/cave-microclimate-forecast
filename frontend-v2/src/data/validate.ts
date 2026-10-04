// 可信度证据链：跨窟留一、ICCP 洞穴实测、ISD 观测对照
// 出处：code/results/iccp_transfer.csv、validate_crosscave.csv、isd_vs_power.csv
// ICCP 第 12 洞 Te'omim 目标序列标准差为 0（常数），按管线门限剔除，不计入统计。
// R² 极端负值已截断到 -1 并置 trunc=true，避免图表坐标轴被 -4e25 拉爆。
// 本文件由 tools/build_frontend_data_v2.py 自动生成，请勿手改。

export interface IccpRow {
  cave: number; name: string; nTest: number; targetSd: number
  /** 目标序列标准差是否达到门限（SD >= 0.5）；false 表示该洞不可用于评估 */
  valid: boolean
  /** 一阶传递基线 R²（原始值） */
  r2Fot: number
  /** 本作品 R²（原始值） */
  r2Op: number
  /** 绘图用：截断到 -1 的基线 R² */
  plotFot: number
  /** 绘图用：截断到 -1 的本作品 R² */
  plotOp: number
  /** 原始 R² 是否被截断过 */
  trunc: boolean
  /** 持续性参照 R² */
  r2Persist: number
}
export const iccp: IccpRow[] = [
  { cave: 1, name: "Skulls", nTest: 1935, targetSd: 8.416, valid: true, r2Fot: 0.7262, r2Op: 0.9206, plotFot: 0.7262, plotOp: 0.9206, trunc: false, r2Persist: 0.0771 },
  { cave: 2, name: "Pool", nTest: 2036, targetSd: 6.576, valid: true, r2Fot: 0.459, r2Op: 0.7228, plotFot: 0.459, plotOp: 0.7228, trunc: false, r2Persist: -0.1426 },
  { cave: 4, name: "Sela'", nTest: 1766, targetSd: 1.782, valid: true, r2Fot: -10.4935, r2Op: -6.4064, plotFot: -1.0, plotOp: -1.0, trunc: true, r2Persist: -164.8636 },
  { cave: 5, name: "Tzruya", nTest: 1766, targetSd: 4.897, valid: true, r2Fot: -2.3334, r2Op: 0.5716, plotFot: -1.0, plotOp: 0.5716, trunc: true, r2Persist: -2.4097 },
  { cave: 6, name: "Horror", nTest: 1897, targetSd: 6.802, valid: true, r2Fot: 0.3704, r2Op: 0.7101, plotFot: 0.3704, plotOp: 0.7101, trunc: false, r2Persist: -0.5772 },
  { cave: 7, name: "Ureideh", nTest: 1816, targetSd: 7.087, valid: true, r2Fot: -0.4908, r2Op: 0.773, plotFot: -0.4908, plotOp: 0.773, trunc: false, r2Persist: -2.1547 },
  { cave: 9, name: "Murabba'at 2", nTest: 1819, targetSd: 6.304, valid: true, r2Fot: -0.7403, r2Op: -0.7033, plotFot: -0.7403, plotOp: -0.7033, trunc: false, r2Persist: -5.4496 },
  { cave: 11, name: "Har Sifsof", nTest: 2272, targetSd: 8.68, valid: true, r2Fot: -0.0199, r2Op: -0.654, plotFot: -0.0199, plotOp: -0.654, trunc: false, r2Persist: -21.0738 },
  { cave: 12, name: "Te'omim", nTest: 1637, targetSd: 0.0, valid: false, r2Fot: -4.268798537110131e+25, r2Op: -1.27034332408284e+26, plotFot: -1.0, plotOp: -1.0, trunc: true, r2Persist: -3.938382815522068e+30 }
]

/** 有效洞（SD 达门限）的数量，以及本作品优于一阶传递基线的洞数 */
export const iccpValidCount = 8
export const iccpOpWins = 7

export interface CrossRow {
  metric: string; lo: number; hi: number; litLo: number; litHi: number; pass: boolean
}
export const crosscave: CrossRow[] = [
  { metric: "outdoor_monthly_T_range", lo: -6.22, hi: 25.65, litLo: -5.1, litHi: 26.9, pass: true },
  { metric: "indoor_monthly_T_range", lo: 2.08, hi: 22.34, litLo: 3.0, litHi: 20.3, pass: true },
  { metric: "indoor_monthly_RH_range", lo: 24.3, hi: 40.14, litLo: 22.7, litHi: 53.5, pass: true },
  { metric: "outdoor_monthly_RH_range", lo: 22.84, hi: 39.3, litLo: 16.3, litHi: 47.4, pass: false },
  { metric: "annual_T_lag_months", lo: 1.0, hi: 1.0, litLo: 1.0, litHi: 1.0, pass: true },
  { metric: "diurnal_T_lag_max_min", lo: 74.8, hi: 71.2, litLo: 20.0, litHi: 64.0, pass: true }
]

/** metric 的中文说明 */
export const metricNames: Record<string, string> = {
  'outdoor_monthly_T_range': '窟外月均气温年变幅（°C）',
  'indoor_monthly_T_range': '窟内月均气温年变幅（°C）',
  'indoor_monthly_RH_range': '窟内月均 RH 年变幅（%）',
  'outdoor_monthly_RH_range': '窟外月均 RH 年变幅（%）',
  'annual_T_lag_months': '窟内气温年相位滞后（月）',
  'diurnal_T_lag_max_min': '窟内外日温滞后极值（分钟）',
}

export interface IsdRow {
  variable: string; n: number; r: number; bias: number; rmse: number; mae: number
}
export const isd: IsdRow[] = [
  { variable: "T2M (°C)", n: 23915, r: 0.9546, bias: 0.6702, rmse: 4.0322, mae: 3.2922 },
  { variable: "RH2M (%)", n: 23884, r: 0.5765, bias: 9.1596, rmse: 19.5569, mae: 14.7207 },
  { variable: "站压 @1140 m (hPa)", n: 23869, r: 0.9395, bias: 0.8105, rmse: 2.7819, mae: 2.3686 }
]
