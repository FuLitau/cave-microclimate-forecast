// 外部验证（出处 code/results/iccp_transfer.csv、validate_crosscave.csv、isd_vs_power.csv）
export interface IccpRow { cave: number; name: string; r2Fot: number; r2Op: number }
export const iccp: IccpRow[] = [
  { cave: 1, name: "Skulls", r2Fot: 0.7262, r2Op: 0.9206 },
  { cave: 2, name: "Pool", r2Fot: 0.4590, r2Op: 0.7228 },
  { cave: 4, name: "Sela'", r2Fot: -10.4935, r2Op: -6.4064 },
  { cave: 5, name: "Tzruya", r2Fot: -2.3334, r2Op: 0.5716 },
  { cave: 6, name: "Horror", r2Fot: 0.3704, r2Op: 0.7101 },
  { cave: 7, name: "Ureideh", r2Fot: -0.4908, r2Op: 0.7730 },
  { cave: 9, name: "Murabba'at 2", r2Fot: -0.7403, r2Op: -0.7033 },
  { cave: 11, name: "Har Sifsof", r2Fot: -0.0199, r2Op: -0.6540 },
  { cave: 12, name: "Te'omim", r2Fot: -42687985371101306655080448.0000, r2Op: -127034332408284008432009216.0000 }
]
export interface CrossRow { metric: string; lo: number; hi: number; litLo: number; litHi: number; pass: boolean }
export const crosscave: CrossRow[] = [
  { metric: "outdoor_monthly_T_range", lo: -6.22, hi: 25.65, litLo: -5.10, litHi: 26.90, pass: true },
  { metric: "indoor_monthly_T_range", lo: 2.08, hi: 22.34, litLo: 3.00, litHi: 20.30, pass: true },
  { metric: "indoor_monthly_RH_range", lo: 24.30, hi: 40.14, litLo: 22.70, litHi: 53.50, pass: true },
  { metric: "outdoor_monthly_RH_range", lo: 22.84, hi: 39.30, litLo: 16.30, litHi: 47.40, pass: false },
  { metric: "annual_T_lag_months", lo: 1.00, hi: 1.00, litLo: 1.00, litHi: 1.00, pass: true },
  { metric: "diurnal_T_lag_max_min", lo: 74.80, hi: 71.20, litLo: 20.00, litHi: 64.00, pass: true }
]
export interface IsdRow { variable: string; r: number }
export const isd: IsdRow[] = [
  { variable: "T2M (°C)", r: 0.9546 },
  { variable: "RH2M (%)", r: 0.5765 },
  { variable: "站压 @1140 m (hPa)", r: 0.9395 }
]
