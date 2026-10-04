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

export const INK = '#e8eef8'
export const INK_2 = '#8ba0bd'
export const INK_3 = '#6d82a2'
export const INK_4 = '#5d7191'
export const LINE = '#1d2a40'
export const PANEL = '#111a2b'
export const AZURITE = '#56c2de'
export const MALACHITE = '#5bc48e'
export const OCHRE = '#e2a24a'
export const CINNABAR = '#e0635c'
export const GOLD = '#f0c084'
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
  backgroundColor: 'rgba(13,21,35,0.96)',
  borderColor: '#27395a',
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
