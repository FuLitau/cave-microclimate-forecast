// 演示窟多年统计
// 出处：code/results/demo_stats.json
// frac_gt62/67/75 的单位已经是百分数（%），界面上直接加 % 即可，不要再乘 100。
// 本文件由 tools/build_frontend_data.py 自动生成，请勿手改。

export const demoStats = {
  "RH_in_mean": 32.34,
  "RH_in_min": 8.39,
  "RH_in_max": 89.02,
  "frac_gt62": 1.359,
  "frac_gt67": 0.456,
  "frac_gt75": 0.12,
  "n_hours": 35087,
  "period": "2021-12-31 01:00:00+00:00 ~ 2025-12-31 23:00:00+00:00",
  "readout": "分位数 τ=0.95",
  "calib_year": 2021,
  "tau_grid": [
    0.9,
    0.95
  ],
  "calib_f1_62": {
    "线性 MSE（对照）": 0.0201,
    "分位数 τ=0.9": 0.0201,
    "分位数 τ=0.95": 0.0241
  }
} as const
