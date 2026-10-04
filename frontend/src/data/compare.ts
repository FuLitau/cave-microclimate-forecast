// 多模型对比（24h / 62% 档，出处 code/results/derisk02_events.csv、derisk02_leadtime.csv、derisk01_model_comparison.csv）
export interface CmpRow { model: string; AUC: number; F1: number; recall: number; precision: number }
export const models24: CmpRow[] = [
  { model: "Operator-direct(本作品)", AUC: 0.8596, F1: 0.1277, recall: 0.1482, precision: 0.1122 },
  { model: "Ablation-无慢变项", AUC: 0.8039, F1: 0.0979, recall: 0.1464, precision: 0.0735 },
  { model: "Ablation-无Magnus项", AUC: 0.8579, F1: 0.1250, recall: 0.1446, precision: 0.1101 },
  { model: "Ablation-仅快变延迟", AUC: 0.7955, F1: 0.0809, recall: 0.0929, precision: 0.0717 },
  { model: "Ablation-短延迟(12h)", AUC: 0.8591, F1: 0.1259, recall: 0.1393, precision: 0.1149 },
  { model: "FirstOrderTransfer-直接传递(初稿形式)", AUC: 0.8242, F1: 0.0757, recall: 0.0732, precision: 0.0784 },
  { model: "FirstOrderTransfer-仅外场滞后(初稿原文)", AUC: 0.8957, F1: 0.0522, recall: 0.0375, precision: 0.0861 },
  { model: "FirstOrderTransfer-递归推演(不稳定极点)", AUC: 0.4995, F1: 0.0000, recall: 0.0000, precision: 0.0000 },
  { model: "RidgeDirect(无延迟嵌入)", AUC: 0.7388, F1: 0.0531, recall: 0.0482, precision: 0.0592 },
  { model: "Persistence-operator(可部署)", AUC: 0.5000, F1: 0.0252, recall: 1.0000, precision: 0.0128 },
  { model: "[oracle]Persistence(需窟内实测)", AUC: 0.8361, F1: 0.0922, recall: 0.0929, precision: 0.0915 },
  { model: "Climatology(可部署)", AUC: 0.7338, F1: 0.0023, recall: 0.0018, precision: 0.0033 }
]
export interface LeadRow { model: string; detect: number; lead: number }
export const leadtime: LeadRow[] = [
  { model: "Operator-direct(本作品)", detect: 0.3511, lead: 46.27 },
  { model: "FirstOrderTransfer-直接传递(初稿形式)", detect: 0.2979, lead: 42.46 }
]
export interface BaseRow { model: string; RMSE: number; R2: number }
export const baselines: BaseRow[] = [
  { model: "Persistence", RMSE: 2.334, R2: 0.9530 },
  { model: "FirstOrderTransfer(初稿方案)", RMSE: 9.471, R2: 0.2263 },
  { model: "FirstOrderTransfer-递归推演(旧口径)", RMSE: 1968149701311.284, R2: -33411352482268261122048.0000 },
  { model: "RidgeDirect(仅当前时刻)", RMSE: 6.549, R2: 0.6301 },
  { model: "Operator-Full(本作品)", RMSE: 3.787, R2: 0.8763 },
  { model: "Ablation-无慢变项", RMSE: 5.491, R2: 0.7399 },
  { model: "Ablation-无Magnus项", RMSE: 3.820, R2: 0.8741 },
  { model: "Ablation-仅快变延迟", RMSE: 5.654, R2: 0.7243 },
  { model: "Ablation-短延迟(12h)", RMSE: 3.891, R2: 0.8694 }
]

// 94 次真实超阈起报事件的命中数（24h / 62% 档，出处 code/results/derisk02_leadtime.csv）
export interface EventRow { name: string; hit: number; onset: number; note: string }
export const events62: EventRow[] = [
  { name: '本作品 · 风险对齐预警', hit: 33, onset: 94, note: '风险分数滚动预警' },
  { name: '初稿 · 直接传递形式', hit: 28, onset: 94, note: '未做风险对齐的可部署化形式' },
  { name: '初稿 · 递归推演', hit: 0, onset: 94, note: '极点 > 1 必然饱和，从不能发出预警' },
]
