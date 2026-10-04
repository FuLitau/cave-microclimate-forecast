// 首屏关键指标卡
// 出处：code/results/derisk02_leadtime.csv、exp03_abc_ablation.csv
// 端到端指标（F1 / AUC）与可部署性上界指标（检出率 / 提前量）分属两张卡片组，不得混读。
// 本文件由 tools/build_frontend_data.py 自动生成，请勿手改。

export interface Kpi {
  label: string
  value: string
  sub: string
  hint: string
  /** 'end2end' = 真实端到端可部署口径；'upper' = 用真实未来再分析替代预报的可部署性上界 */
  scope: 'end2end' | 'upper'
}

export const kpis: Kpi[] = [
  {
    label: '超阈 F1（端到端）',
    value: '0.072 → 0.164',
    sub: '测试段 · 24 h 时效 · 62% 阈值',
    hint: '在 MSE 目标上引入阈值加权风险项后的变化；驱动为真实预报',
    scope: 'end2end',
  },
  {
    label: 'AUC（端到端）',
    value: '0.862 → 0.903',
    sub: '同口径六格全胜',
    hint: '验证/测试 × 24/48/72 h，62% 口径全部为正增益',
    scope: 'end2end',
  },
  {
    label: '预警检出率（上界）',
    value: '35.1%',
    sub: '94 次真实超阈起报事件命中 33 次',
    hint: '理想外场驱动：以真实未来再分析替代预报，属可部署性上界，不代表端到端性能',
    scope: 'upper',
  },
  {
    label: '平均首次预警提前',
    value: '46.3 h',
    sub: '事件前 72 h 窗口内滚动预报口径',
    hint: '连续滚动预报信号的累计提前量，非单次预报直接预见',
    scope: 'upper',
  },
]

/** 消融实验中 A / B 两档在测试段 24 h / 62% 口径下的 AUC */
export const aucA = 0.8621
export const aucB = 0.9030
