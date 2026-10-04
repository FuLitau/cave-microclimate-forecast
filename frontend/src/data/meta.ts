// 项目口径常量
// 出处：docs/03_作品方案.md §3.5 / §5.9、docs/06_佐证材料.md §3
// thresholds 的三级阈值分别对应敦煌研究院业务预警口径、Demas(2015) 潮解起始、npj Heritage Science(2025) 吸湿突变。
// 本文件由 tools/build_frontend_data.py 自动生成，请勿手改。

export interface ThresholdDef {
  /** 相对湿度百分数 */
  value: number
  /** 名称 */
  label: string
  /** 业务含义 */
  meaning: string
  /** 文献/业务出处 */
  source: string
}

export const thresholds: ThresholdDef[] = [
  { value: 62, label: '业务预警线', meaning: '敦煌研究院日常监测采取的窟内相对湿度上限', source: '敦煌研究院业务口径' },
  { value: 67, label: '潮解起始', meaning: '可溶盐开始吸收水分、由固态转为溶液的临界湿度', source: 'Demas 2015' },
  { value: 75, label: '吸湿突变', meaning: 'NaCl 等盐类吸湿量急剧上升的突变点', source: 'npj Heritage Science 2025' },
]

/** 最高一级阈值，用于图表的"危险区"底色 */
export const HARD_THRESHOLD = 62

/** 涉及窟内序列时**必须**同时出现的一句话（任务书口径纪律第 4 条） */
export const SYNTHETIC_LABEL_NOTE =
  '窟内序列为文献标定物理模型生成的合成标签，非窟内实测；模型参数取自公开文献与敦煌气象站观测。'

/** 决策输出必须附带的免责说明 */
export const DECISION_DISCLAIMER = '上述结论为模型辅助建议，供文物保护管理人员研判，不构成自动控制指令。'

/** 演示窗口说明 */
export const DEMO_HONEST_NOTE =
  '演示窗口为教学样例：本窗口读出峰值未触及判定线，系统维持正常开放建议；完整测试段的滚动预警能力见「效果对照」页。'
