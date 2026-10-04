// 消融实验：目标函数形式 A/B/C × 阈值 × 时效
// 出处：code/results/exp03_abc_ablation.csv、exp03_abc_ablation_val.csv、exp03_verdict.csv
// 同一格里存在两套精度口径：pt_* 是点预报口径，RMSE/R2 是实际部署读出口径，二者可能给出相反结论。
// C（算子导出内生权重）经 18 格消融未见稳定增益，最终采用固定阈值权重形式。
// 本文件由 tools/build_frontend_data_v2.py 自动生成，请勿手改。

export interface AblRow {
  mode: string
  thr: string
  h: number
  segment: string
  /** 部署读出口径的超阈 F1 */
  F1: number
  AUC: number
  recall: number
  precision: number
  /** 点预报口径 R² */
  ptR2: number
  /** 部署读出口径 R² */
  R2: number
  ptRMSE: number
  RMSE: number
  /** 报警率：发出预警的时间步占比 */
  predRate: number
  /** 预报最大值 */
  predMax: number
}

export const ablation: AblRow[] = [
  { mode: "A", thr: "62", h: 24, segment: "test", F1: 0.0721, AUC: 0.8621, recall: 0.0465, precision: 0.16, ptR2: 0.5854, R2: 0.5527, ptRMSE: 6.8442, RMSE: 7.1094, predRate: 0.0034, predMax: 83.13 },
  { mode: "A", thr: "67", h: 24, segment: "test", F1: 0.0, AUC: 0.8443, recall: 0.0, precision: 0.0, ptR2: 0.5854, R2: 0.5527, ptRMSE: 6.8442, RMSE: 7.1094, predRate: 0.0009, predMax: 83.13 },
  { mode: "A", thr: "75", h: 24, segment: "test", F1: 0.0, AUC: 0.794, recall: 0.0, precision: 0.0, ptR2: 0.5854, R2: 0.5527, ptRMSE: 6.8442, RMSE: 7.1094, predRate: 0.0001, predMax: 83.13 },
  { mode: "A", thr: "62", h: 48, segment: "test", F1: 0.0381, AUC: 0.8224, recall: 0.0233, precision: 0.1053, ptR2: 0.476, R2: 0.3721, ptRMSE: 7.6943, RMSE: 8.4221, predRate: 0.0026, predMax: 72.16 },
  { mode: "A", thr: "67", h: 48, segment: "test", F1: 0.0, AUC: 0.7723, recall: 0.0, precision: 0.0, ptR2: 0.476, R2: 0.3721, ptRMSE: 7.6943, RMSE: 8.4221, predRate: 0.0006, predMax: 72.16 },
  { mode: "A", thr: "75", h: 48, segment: "test", F1: 0.0, AUC: 0.6946, recall: 0.0, precision: 0.0, ptR2: 0.476, R2: 0.3721, ptRMSE: 7.6943, RMSE: 8.4221, predRate: 0.0, predMax: 72.16 },
  { mode: "A", thr: "62", h: 72, segment: "test", F1: 0.0, AUC: 0.807, recall: 0.0, precision: 0.0, ptR2: 0.4242, R2: 0.3904, ptRMSE: 8.0656, RMSE: 8.2987, predRate: 0.0007, predMax: 65.42 },
  { mode: "A", thr: "67", h: 72, segment: "test", F1: 0.0, AUC: 0.7711, recall: 0.0, precision: 0.0, ptR2: 0.4242, R2: 0.3904, ptRMSE: 8.0656, RMSE: 8.2987, predRate: 0.0, predMax: 65.42 },
  { mode: "A", thr: "75", h: 72, segment: "test", F1: 0.0, AUC: 0.7511, recall: 0.0, precision: 0.0, ptR2: 0.4242, R2: 0.3904, ptRMSE: 8.0656, RMSE: 8.2987, predRate: 0.0, predMax: 65.42 },
  { mode: "B", thr: "62", h: 24, segment: "test", F1: 0.1637, AUC: 0.903, recall: 0.186, precision: 0.1461, ptR2: 0.6552, R2: 0.3102, ptRMSE: 6.2418, RMSE: 8.8286, predRate: 0.015, predMax: 74.32 },
  { mode: "B", thr: "67", h: 24, segment: "test", F1: 0.0522, AUC: 0.8994, recall: 0.0536, precision: 0.0508, ptR2: 0.6552, R2: 0.3102, ptRMSE: 6.2418, RMSE: 8.8286, predRate: 0.004, predMax: 74.32 },
  { mode: "B", thr: "75", h: 24, segment: "test", F1: 0.0, AUC: 0.9016, recall: 0.0, precision: 0.0, ptR2: 0.6552, R2: 0.3102, ptRMSE: 6.2418, RMSE: 8.8286, predRate: 0.0, predMax: 74.32 },
  { mode: "B", thr: "62", h: 48, segment: "test", F1: 0.0889, AUC: 0.8592, recall: 0.0698, precision: 0.1224, ptR2: 0.5342, R2: 0.0991, ptRMSE: 7.2538, RMSE: 10.0883, predRate: 0.0067, predMax: 72.51 },
  { mode: "B", thr: "67", h: 48, segment: "test", F1: 0.0, AUC: 0.8503, recall: 0.0, precision: 0.0, ptR2: 0.5342, R2: 0.0991, ptRMSE: 7.2538, RMSE: 10.0883, predRate: 0.0007, predMax: 72.51 },
  { mode: "B", thr: "75", h: 48, segment: "test", F1: 0.0, AUC: 0.8217, recall: 0.0, precision: 0.0, ptR2: 0.5342, R2: 0.0991, ptRMSE: 7.2538, RMSE: 10.0883, predRate: 0.0, predMax: 72.51 },
  { mode: "B", thr: "62", h: 72, segment: "test", F1: 0.0538, AUC: 0.8558, recall: 0.0349, precision: 0.1176, ptR2: 0.4754, R2: -0.0781, ptRMSE: 7.6989, RMSE: 11.0366, predRate: 0.0035, predMax: 67.56 },
  { mode: "B", thr: "67", h: 72, segment: "test", F1: 0.0, AUC: 0.8535, recall: 0.0, precision: 0.0, ptR2: 0.4754, R2: -0.0781, ptRMSE: 7.6989, RMSE: 11.0366, predRate: 0.0002, predMax: 67.56 },
  { mode: "B", thr: "75", h: 72, segment: "test", F1: 0.0, AUC: 0.8354, recall: 0.0, precision: 0.0, ptR2: 0.4754, R2: -0.0781, ptRMSE: 7.6989, RMSE: 11.0366, predRate: 0.0, predMax: 67.56 },
  { mode: "C", thr: "62", h: 24, segment: "test", F1: 0.1116, AUC: 0.9024, recall: 0.0698, precision: 0.2791, ptR2: 0.651, R2: 0.3783, ptRMSE: 6.2797, RMSE: 8.3811, predRate: 0.0029, predMax: 69.96 },
  { mode: "C", thr: "67", h: 24, segment: "test", F1: 0.0, AUC: 0.8948, recall: 0.0, precision: 0.0, ptR2: 0.651, R2: 0.3783, ptRMSE: 6.2797, RMSE: 8.3811, predRate: 0.0003, predMax: 69.96 },
  { mode: "C", thr: "75", h: 24, segment: "test", F1: 0.0, AUC: 0.8979, recall: 0.0, precision: 0.0, ptR2: 0.651, R2: 0.3783, ptRMSE: 6.2797, RMSE: 8.3811, predRate: 0.0, predMax: 69.96 },
  { mode: "C", thr: "62", h: 48, segment: "test", F1: 0.0412, AUC: 0.8691, recall: 0.0233, precision: 0.1818, ptR2: 0.5342, R2: 0.1697, ptRMSE: 7.2544, RMSE: 9.6851, predRate: 0.0015, predMax: 68.52 },
  { mode: "C", thr: "67", h: 48, segment: "test", F1: 0.0, AUC: 0.8473, recall: 0.0, precision: 0.0, ptR2: 0.5342, R2: 0.1697, ptRMSE: 7.2544, RMSE: 9.6851, predRate: 0.0001, predMax: 68.52 },
  { mode: "C", thr: "75", h: 48, segment: "test", F1: 0.0, AUC: 0.8152, recall: 0.0, precision: 0.0, ptR2: 0.5342, R2: 0.1697, ptRMSE: 7.2544, RMSE: 9.6851, predRate: 0.0, predMax: 68.52 },
  { mode: "C", thr: "62", h: 72, segment: "test", F1: 0.0, AUC: 0.8601, recall: 0.0, precision: 0.0, ptR2: 0.476, R2: -0.0343, ptRMSE: 7.6938, RMSE: 10.8098, predRate: 0.0005, predMax: 63.95 },
  { mode: "C", thr: "67", h: 72, segment: "test", F1: 0.0, AUC: 0.8508, recall: 0.0, precision: 0.0, ptR2: 0.476, R2: -0.0343, ptRMSE: 7.6938, RMSE: 10.8098, predRate: 0.0, predMax: 63.95 },
  { mode: "C", thr: "75", h: 72, segment: "test", F1: 0.0, AUC: 0.8517, recall: 0.0, precision: 0.0, ptR2: 0.476, R2: -0.0343, ptRMSE: 7.6938, RMSE: 10.8098, predRate: 0.0, predMax: 63.95 },
  { mode: "A", thr: "62", h: 24, segment: "val", F1: 0.1905, AUC: 0.8471, recall: 0.1053, precision: 1.0, ptR2: 0.5569, R2: 0.5087, ptRMSE: 6.3109, RMSE: 6.6455, predRate: 0.0007, predMax: 64.48 },
  { mode: "A", thr: "67", h: 24, segment: "val", F1: 0.0, AUC: 0.8436, recall: 0.0, precision: 0.0, ptR2: 0.5569, R2: 0.5087, ptRMSE: 6.3109, RMSE: 6.6455, predRate: 0.0, predMax: 64.48 },
  { mode: "A", thr: "75", h: 24, segment: "val", F1: 0.0, AUC: 0.9887, recall: 0.0, precision: 0.0, ptR2: 0.5569, R2: 0.5087, ptRMSE: 6.3109, RMSE: 6.6455, predRate: 0.0, predMax: 64.48 },
  { mode: "A", thr: "62", h: 48, segment: "val", F1: 0.0, AUC: 0.8052, recall: 0.0, precision: 0.0, ptR2: 0.4006, R2: 0.2251, ptRMSE: 7.3407, RMSE: 8.3467, predRate: 0.0003, predMax: 62.09 },
  { mode: "A", thr: "67", h: 48, segment: "val", F1: 0.0, AUC: 0.843, recall: 0.0, precision: 0.0, ptR2: 0.4006, R2: 0.2251, ptRMSE: 7.3407, RMSE: 8.3467, predRate: 0.0, predMax: 62.09 },
  { mode: "A", thr: "75", h: 48, segment: "val", F1: 0.0, AUC: 0.9918, recall: 0.0, precision: 0.0, ptR2: 0.4006, R2: 0.2251, ptRMSE: 7.3407, RMSE: 8.3467, predRate: 0.0, predMax: 62.09 },
  { mode: "A", thr: "62", h: 72, segment: "val", F1: 0.0, AUC: 0.8032, recall: 0.0, precision: 0.0, ptR2: 0.3372, R2: 0.2919, ptRMSE: 7.7139, RMSE: 7.9734, predRate: 0.0, predMax: 57.5 },
  { mode: "A", thr: "67", h: 72, segment: "val", F1: 0.0, AUC: 0.8926, recall: 0.0, precision: 0.0, ptR2: 0.3372, R2: 0.2919, ptRMSE: 7.7139, RMSE: 7.9734, predRate: 0.0, predMax: 57.5 },
  { mode: "A", thr: "75", h: 72, segment: "val", F1: 0.0, AUC: 0.9778, recall: 0.0, precision: 0.0, ptR2: 0.3372, R2: 0.2919, ptRMSE: 7.7139, RMSE: 7.9734, predRate: 0.0, predMax: 57.5 },
  { mode: "B", thr: "62", h: 24, segment: "val", F1: 0.3846, AUC: 0.8697, recall: 0.5263, precision: 0.303, ptR2: 0.6162, R2: 0.0227, ptRMSE: 5.8734, RMSE: 9.3727, predRate: 0.0113, predMax: 81.77 },
  { mode: "B", thr: "67", h: 24, segment: "val", F1: 0.5517, AUC: 0.8535, recall: 0.8, precision: 0.4211, ptR2: 0.6162, R2: 0.0227, ptRMSE: 5.8734, RMSE: 9.3727, predRate: 0.0065, predMax: 81.77 },
  { mode: "B", thr: "75", h: 24, segment: "val", F1: 0.0, AUC: 0.9969, recall: 0.0, precision: 0.0, ptR2: 0.6162, R2: 0.0227, ptRMSE: 5.8734, RMSE: 9.3727, predRate: 0.0017, predMax: 81.77 },
  { mode: "B", thr: "62", h: 48, segment: "val", F1: 0.3333, AUC: 0.8325, recall: 0.4211, precision: 0.2759, ptR2: 0.4447, R2: -0.4359, ptRMSE: 7.0654, RMSE: 11.3619, predRate: 0.0099, predMax: 76.06 },
  { mode: "B", thr: "67", h: 48, segment: "val", F1: 0.2609, AUC: 0.7961, recall: 0.3, precision: 0.2308, ptR2: 0.4447, R2: -0.4359, ptRMSE: 7.0654, RMSE: 11.3619, predRate: 0.0044, predMax: 76.06 },
  { mode: "B", thr: "75", h: 48, segment: "val", F1: 0.0, AUC: 0.9932, recall: 0.0, precision: 0.0, ptR2: 0.4447, R2: -0.4359, ptRMSE: 7.0654, RMSE: 11.3619, predRate: 0.0003, predMax: 76.06 },
  { mode: "B", thr: "62", h: 72, segment: "val", F1: 0.0952, AUC: 0.8681, recall: 0.1053, precision: 0.087, ptR2: 0.3825, R2: -0.7173, ptRMSE: 7.4458, RMSE: 12.4166, predRate: 0.0079, predMax: 70.91 },
  { mode: "B", thr: "67", h: 72, segment: "val", F1: 0.0, AUC: 0.8984, recall: 0.0, precision: 0.0, ptR2: 0.3825, R2: -0.7173, ptRMSE: 7.4458, RMSE: 12.4166, predRate: 0.0027, predMax: 70.91 },
  { mode: "B", thr: "75", h: 72, segment: "val", F1: 0.0, AUC: 0.9829, recall: 0.0, precision: 0.0, ptR2: 0.3825, R2: -0.7173, ptRMSE: 7.4458, RMSE: 12.4166, predRate: 0.0, predMax: 70.91 },
  { mode: "C", thr: "62", h: 24, segment: "val", F1: 0.5161, AUC: 0.8762, recall: 0.4211, precision: 0.6667, ptR2: 0.6114, R2: 0.119, ptRMSE: 5.9102, RMSE: 8.8989, predRate: 0.0041, predMax: 69.4 },
  { mode: "C", thr: "67", h: 24, segment: "val", F1: 0.1667, AUC: 0.8444, recall: 0.1, precision: 0.5, ptR2: 0.6114, R2: 0.119, ptRMSE: 5.9102, RMSE: 8.8989, predRate: 0.0007, predMax: 69.4 },
  { mode: "C", thr: "75", h: 24, segment: "val", F1: 0.0, AUC: 0.9976, recall: 0.0, precision: 0.0, ptR2: 0.6114, R2: 0.119, ptRMSE: 5.9102, RMSE: 8.8989, predRate: 0.0, predMax: 69.4 },
  { mode: "C", thr: "62", h: 48, segment: "val", F1: 0.25, AUC: 0.828, recall: 0.1579, precision: 0.6, ptR2: 0.4559, R2: -0.2596, ptRMSE: 6.9937, RMSE: 10.6414, predRate: 0.0017, predMax: 64.54 },
  { mode: "C", thr: "67", h: 48, segment: "val", F1: 0.0, AUC: 0.7994, recall: 0.0, precision: 0.0, ptR2: 0.4559, R2: -0.2596, ptRMSE: 6.9937, RMSE: 10.6414, predRate: 0.0, predMax: 64.54 },
  { mode: "C", thr: "75", h: 48, segment: "val", F1: 0.0, AUC: 0.9904, recall: 0.0, precision: 0.0, ptR2: 0.4559, R2: -0.2596, ptRMSE: 6.9937, RMSE: 10.6414, predRate: 0.0, predMax: 64.54 },
  { mode: "C", thr: "62", h: 72, segment: "val", F1: 0.0, AUC: 0.873, recall: 0.0, precision: 0.0, ptR2: 0.3897, R2: -0.5638, ptRMSE: 7.4021, RMSE: 11.8488, predRate: 0.0003, predMax: 62.0 },
  { mode: "C", thr: "67", h: 72, segment: "val", F1: 0.0, AUC: 0.9195, recall: 0.0, precision: 0.0, ptR2: 0.3897, R2: -0.5638, ptRMSE: 7.4021, RMSE: 11.8488, predRate: 0.0, predMax: 62.0 },
  { mode: "C", thr: "75", h: 72, segment: "val", F1: 0.0, AUC: 0.9583, recall: 0.0, precision: 0.0, ptR2: 0.3897, R2: -0.5638, ptRMSE: 7.4021, RMSE: 11.8488, predRate: 0.0, predMax: 62.0 }
]

export const modeNames: Record<string, string> = {
  "A": "A · 纯 MSE（现有常规做法）",
  "B": "B · 在 MSE 上引入阈值加权风险项",
  "C": "C · B + 算子导出内生权重",
}

export interface VerdictRow {
  segment: string; h: number; thr: string
  F1_B: number; F1_C: number; dF1: number
  AUC_B: number; AUC_C: number; dAUC: number
  C_wins: boolean
}

export const verdict: VerdictRow[] = [
  { segment: "val", h: 24, thr: "62", F1_B: 0.3846, F1_C: 0.5161, dF1: 0.1315, AUC_B: 0.8697, AUC_C: 0.8762, dAUC: 0.0065, C_wins: true },
  { segment: "val", h: 24, thr: "67", F1_B: 0.5517, F1_C: 0.1667, dF1: -0.385, AUC_B: 0.8535, AUC_C: 0.8444, dAUC: -0.0091, C_wins: false },
  { segment: "val", h: 24, thr: "75", F1_B: 0.0, F1_C: 0.0, dF1: 0.0, AUC_B: 0.9969, AUC_C: 0.9976, dAUC: 0.0007, C_wins: false },
  { segment: "val", h: 48, thr: "62", F1_B: 0.3333, F1_C: 0.25, dF1: -0.0833, AUC_B: 0.8325, AUC_C: 0.828, dAUC: -0.0045, C_wins: false },
  { segment: "val", h: 48, thr: "67", F1_B: 0.2609, F1_C: 0.0, dF1: -0.2609, AUC_B: 0.7961, AUC_C: 0.7994, dAUC: 0.0033, C_wins: false },
  { segment: "val", h: 48, thr: "75", F1_B: 0.0, F1_C: 0.0, dF1: 0.0, AUC_B: 0.9932, AUC_C: 0.9904, dAUC: -0.0028, C_wins: false },
  { segment: "val", h: 72, thr: "62", F1_B: 0.0952, F1_C: 0.0, dF1: -0.0952, AUC_B: 0.8681, AUC_C: 0.873, dAUC: 0.0049, C_wins: false },
  { segment: "val", h: 72, thr: "67", F1_B: 0.0, F1_C: 0.0, dF1: 0.0, AUC_B: 0.8984, AUC_C: 0.9195, dAUC: 0.0211, C_wins: false },
  { segment: "val", h: 72, thr: "75", F1_B: 0.0, F1_C: 0.0, dF1: 0.0, AUC_B: 0.9829, AUC_C: 0.9583, dAUC: -0.0246, C_wins: false },
  { segment: "test", h: 24, thr: "62", F1_B: 0.1637, F1_C: 0.1116, dF1: -0.0521, AUC_B: 0.903, AUC_C: 0.9024, dAUC: -0.0006, C_wins: false },
  { segment: "test", h: 24, thr: "67", F1_B: 0.0522, F1_C: 0.0, dF1: -0.0522, AUC_B: 0.8994, AUC_C: 0.8948, dAUC: -0.0046, C_wins: false },
  { segment: "test", h: 24, thr: "75", F1_B: 0.0, F1_C: 0.0, dF1: 0.0, AUC_B: 0.9016, AUC_C: 0.8979, dAUC: -0.0037, C_wins: false },
  { segment: "test", h: 48, thr: "62", F1_B: 0.0889, F1_C: 0.0412, dF1: -0.0477, AUC_B: 0.8592, AUC_C: 0.8691, dAUC: 0.0099, C_wins: false },
  { segment: "test", h: 48, thr: "67", F1_B: 0.0, F1_C: 0.0, dF1: 0.0, AUC_B: 0.8503, AUC_C: 0.8473, dAUC: -0.003, C_wins: false },
  { segment: "test", h: 48, thr: "75", F1_B: 0.0, F1_C: 0.0, dF1: 0.0, AUC_B: 0.8217, AUC_C: 0.8152, dAUC: -0.0065, C_wins: false },
  { segment: "test", h: 72, thr: "62", F1_B: 0.0538, F1_C: 0.0, dF1: -0.0538, AUC_B: 0.8558, AUC_C: 0.8601, dAUC: 0.0043, C_wins: false },
  { segment: "test", h: 72, thr: "67", F1_B: 0.0, F1_C: 0.0, dF1: 0.0, AUC_B: 0.8535, AUC_C: 0.8508, dAUC: -0.0027, C_wins: false },
  { segment: "test", h: 72, thr: "75", F1_B: 0.0, F1_C: 0.0, dF1: 0.0, AUC_B: 0.8354, AUC_C: 0.8517, dAUC: 0.0163, C_wins: false }
]

/** C 档在全部 18 个（验证/测试 × 24/48/72 h × 三阈值）格中胜出的次数 */
export const cWinCount = 1
export const cGridCount = 18
