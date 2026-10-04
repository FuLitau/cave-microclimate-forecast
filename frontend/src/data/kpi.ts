// 关键指标（口径见 docs/03 §5.9；端到端 = 含 L1 预报误差；检出率/提前量为滚动预报口径）
export interface Kpi { label: string; value: string; sub: string; hint: string }
export const kpis: Kpi[] = [
  { label: '超阈 F1（端到端）', value: '0.072 → 0.164', sub: '风险对齐训练后 · 测试段 2021–2025', hint: '24 h 时效 / 62% 阈值；MSE 基线 → MSE+twCRPS' },
  { label: 'AUC（端到端）', value: '0.862 → 0.903', sub: '同口径六格全胜', hint: '验证/测试 × 24/48/72 h，62% 口径全部为正增益' },
  { label: '预警检出率（上界）', value: '35.1%', sub: '94 次真实超阈起报事件命中 33 次', hint: '理想外场驱动：以真实未来再分析替代预报，属可部署性上界' },
  { label: '平均首次预警提前', value: '46.3 h', sub: '事件前 72 h 窗口内滚动预报口径', hint: '连续滚动预报信号的累计提前量，非单次预报直接预见' },
]
export const aucB = 0.9030
export const aucA = 0.8621
