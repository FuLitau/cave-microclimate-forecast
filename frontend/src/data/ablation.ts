// 消融实验（测试段 24h，出处 code/results/exp03_abc_ablation.csv）
export interface AblRow { mode: string; modeName: string; thr: string; F1: number; AUC: number; ptR2: number; predMax: number }
export const ablation: AblRow[] = [
  { mode: 'A', modeName: "A · MSE（现有做法）", thr: '62', F1: 0.0721, AUC: 0.8621, ptR2: 0.5854, predMax: 83.13 },
  { mode: 'A', modeName: "A · MSE（现有做法）", thr: '67', F1: 0.0000, AUC: 0.8443, ptR2: 0.5854, predMax: 83.13 },
  { mode: 'A', modeName: "A · MSE（现有做法）", thr: '75', F1: 0.0000, AUC: 0.7940, ptR2: 0.5854, predMax: 83.13 },
  { mode: 'B', modeName: "B · MSE + twCRPS（固定阈值）", thr: '62', F1: 0.1637, AUC: 0.9030, ptR2: 0.6552, predMax: 74.32 },
  { mode: 'B', modeName: "B · MSE + twCRPS（固定阈值）", thr: '67', F1: 0.0522, AUC: 0.8994, ptR2: 0.6552, predMax: 74.32 },
  { mode: 'B', modeName: "B · MSE + twCRPS（固定阈值）", thr: '75', F1: 0.0000, AUC: 0.9016, ptR2: 0.6552, predMax: 74.32 },
  { mode: 'C', modeName: "C · + 算子导出内生权重", thr: '62', F1: 0.1116, AUC: 0.9024, ptR2: 0.6510, predMax: 69.96 },
  { mode: 'C', modeName: "C · + 算子导出内生权重", thr: '67', F1: 0.0000, AUC: 0.8948, ptR2: 0.6510, predMax: 69.96 },
  { mode: 'C', modeName: "C · + 算子导出内生权重", thr: '75', F1: 0.0000, AUC: 0.8979, ptR2: 0.6510, predMax: 69.96 }
]
