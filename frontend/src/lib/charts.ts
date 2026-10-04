/**
 * ECharts 按需引入。
 *
 * 整包 `import * as echarts from 'echarts'` 会把全部图表类型与组件打进产物
 * （旧版本实测 1.26 MB，触发 Vite 的 500 kB 分块告警）。比赛演示是离线单页，
 * 体积直接影响首屏，因此这里只注册本项目真正用到的模块。
 */
import * as echarts from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { ComposeOption } from 'echarts/core'
import type { BarSeriesOption, LineSeriesOption } from 'echarts/charts'
import type {
  GridComponentOption,
  LegendComponentOption,
  MarkAreaComponentOption,
  MarkLineComponentOption,
  TooltipComponentOption,
} from 'echarts/components'

echarts.use([
  LineChart,
  BarChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  MarkLineComponent,
  MarkAreaComponent,
  CanvasRenderer,
])

export type ChartOption = ComposeOption<
  | LineSeriesOption
  | BarSeriesOption
  | GridComponentOption
  | TooltipComponentOption
  | LegendComponentOption
  | MarkLineComponentOption
  | MarkAreaComponentOption
>

export { echarts }

/* ---------------------------------------------------------------------------
   与设计系统保持一致的图表默认值
   --------------------------------------------------------------------------- */

export const INK = '#ece6da'
export const INK_2 = '#b3a992'
export const INK_3 = '#837a68'
export const INK_4 = '#5f5849'
export const LINE = '#312b22'
export const PANEL = '#1b1814'
export const AZURITE = '#4a90c4'
export const MALACHITE = '#4f9d8b'
export const OCHRE = '#d99a3f'
export const CINNABAR = '#d4553f'
export const GOLD = '#c9a84c'
export const VIOLET = '#8b7bb8'

export const FONT =
  '"PingFang SC", "HarmonyOS Sans SC", "Microsoft YaHei", "Source Han Sans SC", system-ui, sans-serif'

/** 所有图共用的坐标轴/提示框基调，避免每个视图各写一套。 */
export const baseAxis = {
  axisLine: { lineStyle: { color: LINE } },
  axisTick: { show: false },
  axisLabel: { color: INK_3, fontSize: 11, fontFamily: FONT },
  splitLine: { lineStyle: { color: LINE, type: 'dashed' as const, opacity: 0.55 } },
}

export const baseTooltip = {
  backgroundColor: 'rgba(22,19,15,0.96)',
  borderColor: '#453d30',
  borderWidth: 1,
  padding: [8, 11] as [number, number],
  textStyle: { color: INK, fontSize: 12, fontFamily: FONT },
  extraCssText: 'border-radius:8px;box-shadow:0 10px 30px -14px #000;',
}

export const baseLegend = {
  textStyle: { color: INK_2, fontSize: 11.5, fontFamily: FONT },
  icon: 'roundRect',
  itemWidth: 10,
  itemHeight: 3,
  itemGap: 14,
  top: 0,
  left: 0,
}
