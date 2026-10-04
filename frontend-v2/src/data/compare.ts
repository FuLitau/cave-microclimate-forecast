// 效果对照：多模型、事件命中、提前量与非线性读出
// 出处：code/results/derisk02_events.csv、derisk02_leadtime.csv、derisk01_model_comparison.csv、derisk03_readout_compare.csv
// derisk02 的检出率/提前量使用真实未来再分析替代预报，属可部署性上界。
// derisk03 的 GBDT 非线性读出并非全面更优：24 h/62% 格的 F1 反而低于线性岭回归，界面须如实标注。
// 本文件由 tools/build_frontend_data_v2.py 自动生成，请勿手改。

export interface CmpRow { model: string; label: string; AUC: number; F1: number; recall: number; precision: number; baseRate: number }
export const models24: CmpRow[] = [
  { model: "Operator-direct(本作品)", label: "Operator-direct", AUC: 0.8596, F1: 0.1277, recall: 0.1482, precision: 0.1122, baseRate: 0.0128 },
  { model: "Ablation-无慢变项", label: "Ablation-无慢变项", AUC: 0.8039, F1: 0.0979, recall: 0.1464, precision: 0.0735, baseRate: 0.0128 },
  { model: "Ablation-无Magnus项", label: "Ablation-无Magnus项", AUC: 0.8579, F1: 0.125, recall: 0.1446, precision: 0.1101, baseRate: 0.0128 },
  { model: "Ablation-仅快变延迟", label: "Ablation-仅快变延迟", AUC: 0.7955, F1: 0.0809, recall: 0.0929, precision: 0.0717, baseRate: 0.0128 },
  { model: "Ablation-短延迟(12h)", label: "Ablation-短延迟", AUC: 0.8591, F1: 0.1259, recall: 0.1393, precision: 0.1149, baseRate: 0.0128 },
  { model: "FirstOrderTransfer-直接传递(初稿形式)", label: "FirstOrderTransfer-直接传递", AUC: 0.8242, F1: 0.0757, recall: 0.0732, precision: 0.0784, baseRate: 0.0128 },
  { model: "FirstOrderTransfer-仅外场滞后(初稿原文)", label: "FirstOrderTransfer-仅外场滞后", AUC: 0.8957, F1: 0.0522, recall: 0.0375, precision: 0.0861, baseRate: 0.0128 },
  { model: "FirstOrderTransfer-递归推演(不稳定极点)", label: "FirstOrderTransfer-递归推演", AUC: 0.4995, F1: 0.0, recall: 0.0, precision: 0.0, baseRate: 0.0128 },
  { model: "RidgeDirect(无延迟嵌入)", label: "RidgeDirect", AUC: 0.7388, F1: 0.0531, recall: 0.0482, precision: 0.0592, baseRate: 0.0128 },
  { model: "Persistence-operator(可部署)", label: "Persistence-operator", AUC: 0.5, F1: 0.0252, recall: 1.0, precision: 0.0128, baseRate: 0.0128 },
  { model: "[oracle]Persistence(需窟内实测)", label: "[oracle]Persistence", AUC: 0.8361, F1: 0.0922, recall: 0.0929, precision: 0.0915, baseRate: 0.0128 },
  { model: "Climatology(可部署)", label: "Climatology", AUC: 0.7338, F1: 0.0023, recall: 0.0018, precision: 0.0033, baseRate: 0.0128 }
]

export interface LeadRow { model: string; label: string; onset: number; warned: number; detect: number; lead: number }
export const leadtime: LeadRow[] = [
  { model: "Operator-direct(本作品)", label: "Operator-direct", onset: 94, warned: 33, detect: 0.3511, lead: 46.27 },
  { model: "FirstOrderTransfer-直接传递(初稿形式)", label: "FirstOrderTransfer-直接传递", onset: 94, warned: 28, detect: 0.2979, lead: 42.46 }
]

export interface BaseRow {
  model: string; label: string; RMSE: number; R2: number; MAE: number | null
  nFeatures: number | null; fitSeconds: number | null
  group: string; note: string
}
export const baselines: BaseRow[] = [
  { model: "Persistence", label: "Persistence", RMSE: 2.3338, R2: 0.953, MAE: 1.2493, nFeatures: null, fitSeconds: null, group: "参照模型", note: "以当前窟内 RH 原样外推。它不含任何室外驱动信息，是所有模型的下限参照——本表的目的是刻画「室外 → 窟内」这段可学习部分。" },
  { model: "FirstOrderTransfer(初稿方案)", label: "FirstOrderTransfer", RMSE: 9.4713, R2: 0.2263, MAE: 7.5521, nFeatures: null, fitSeconds: null, group: "一阶传递基线", note: "一阶传递式 RH_in = a·RH_out(t−Δ) + b，a、Δ 由标定得到——既有洞窟研究的常用做法。" },
  { model: "FirstOrderTransfer-递归推演(旧口径)", label: "FirstOrderTransfer-递归推演", RMSE: 1968149701311.284, R2: -3.341135248226826e+22, MAE: 536087657416.4301, nFeatures: null, fitSeconds: null, group: "一阶传递基线", note: "把一阶传递式反复迭代到 24 h。传递算子极点接近 1，迭代必然发散（RMSE 达 1e12），该路线不可用。" },
  { model: "RidgeDirect(仅当前时刻)", label: "RidgeDirect", RMSE: 6.549, R2: 0.6301, MAE: 5.1524, nFeatures: null, fitSeconds: null, group: "参照模型", note: "岭回归直接读当前时刻的室外场，没有任何时间结构，用来衬托延迟特征的价值。" },
  { model: "Operator-Full(本作品)", label: "Operator-Full", RMSE: 3.7873, R2: 0.8763, MAE: 2.7938, nFeatures: 258, fitSeconds: 5.63, group: "本作品与消融", note: "本作品：258 维可微输运读出（240 快变延迟 + 12 慢变均值 + 6 Magnus 比值）。" },
  { model: "Ablation-无慢变项", label: "Ablation-无慢变项", RMSE: 5.491, R2: 0.7399, MAE: 4.1499, nFeatures: 246, fitSeconds: 4.4, group: "本作品与消融", note: "消融：去掉 12 个慢变滑动均值，仅留快变延迟与 Magnus 比值。" },
  { model: "Ablation-无Magnus项", label: "Ablation-无Magnus项", RMSE: 3.8201, R2: 0.8741, MAE: 2.8195, nFeatures: 252, fitSeconds: 4.02, group: "本作品与消融", note: "消融：去掉 6 个 Magnus 水汽比特征，仅留延迟与慢变均值。" },
  { model: "Ablation-仅快变延迟", label: "Ablation-仅快变延迟", RMSE: 5.6541, R2: 0.7243, MAE: 4.2472, nFeatures: 240, fitSeconds: 3.94, group: "本作品与消融", note: "消融：只留 240 个快变延迟特征，去掉全部慢变与物理比值。" },
  { model: "Ablation-短延迟(12h)", label: "Ablation-短延迟", RMSE: 3.8908, R2: 0.8694, MAE: 2.8609, nFeatures: 78, fitSeconds: 1.52, group: "本作品与消融", note: "消融：快变延迟由 48 h 截短到 12 h，检验长延迟记忆的贡献。" }
]

export interface EventRow { name: string; hit: number; onset: number; note: string }
export const events62: EventRow[] = [
  { name: "本作品 · 风险对齐预警", hit: 33, onset: 94, note: "风险分数连续滚动预警" },
  { name: "一阶传递 · 直接形式", hit: 28, onset: 94, note: "既有洞窟研究的常规可部署形式" },
  { name: "一阶传递 · 递归推演", hit: 0, onset: 94, note: "传递算子极点 > 1，迭代必然饱和，无法发出预警" }
]

export interface ReadoutRow {
  h: number; readout: string; RMSE: number; peakRatio: number
  auc62: number; f162: number; auc67: number; f167: number; auc75: number; f175: number
}
export const readoutCompare: ReadoutRow[] = [
  { h: 24, readout: "线性岭回归", RMSE: 7.27, peakRatio: 0.5923, auc62: 0.8188, f162: 0.0998, auc67: 0.7821, f167: 0.0216, auc75: 0.7592, f175: 0.0 },
  { h: 24, readout: "GBDT 非线性", RMSE: 6.626, peakRatio: 0.6834, auc62: 0.8757, f162: 0.0849, auc67: 0.8797, f167: 0.0356, auc75: 0.8786, f175: 0.0194 },
  { h: 48, readout: "线性岭回归", RMSE: 7.809, peakRatio: 0.5691, auc62: 0.7847, f162: 0.0896, auc67: 0.7404, f167: 0.019, auc75: 0.7323, f175: 0.0 },
  { h: 48, readout: "GBDT 非线性", RMSE: 7.65, peakRatio: 0.6218, auc62: 0.816, f162: 0.0811, auc67: 0.7983, f167: 0.0067, auc75: 0.7985, f175: 0.0 },
  { h: 72, readout: "线性岭回归", RMSE: 8.149, peakRatio: 0.559, auc62: 0.7684, f162: 0.0655, auc67: 0.7341, f167: 0.0121, auc75: 0.718, f175: 0.0 },
  { h: 72, readout: "GBDT 非线性", RMSE: 8.262, peakRatio: 0.5964, auc62: 0.7882, f162: 0.0205, auc67: 0.7713, f167: 0.0172, auc75: 0.7714, f175: 0.0 }
]

export interface DurRow { model: string; threshold: string; maeH: number; biasH: number; rmseH: number }
export const duration: DurRow[] = [
  { model: "FirstOrderTransfer(初稿方案)", threshold: 62.0, maeH: 0.3067, biasH: -0.3067, rmseH: 1.7572 },
  { model: "Operator-Full(本作品)", threshold: 62.0, maeH: 0.2673, biasH: -0.1544, rmseH: 1.4524 },
  { model: "FirstOrderTransfer(初稿方案)", threshold: 67.0, maeH: 0.1019, biasH: -0.1019, rmseH: 0.8052 },
  { model: "Operator-Full(本作品)", threshold: 67.0, maeH: 0.0942, biasH: -0.0756, rmseH: 0.7422 },
  { model: "FirstOrderTransfer(初稿方案)", threshold: 75.0, maeH: 0.0257, biasH: -0.0257, rmseH: 0.3909 },
  { model: "Operator-Full(本作品)", threshold: 75.0, maeH: 0.0257, biasH: -0.0257, rmseH: 0.3909 }
]
