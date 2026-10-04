<script setup lang="ts">
/**
 * 风险指挥台 —— 首屏闭环：室外预报 → 窟内风险读出 → 分级建议。
 *
 * 口径纪律：
 *  · 窟内曲线是**合成标签**（文献标定物理模型），不是窟内实测；
 *  · 加粗的风险读出是**分位数回归的上分位读出（τ=0.95）**，不是预测分布中位数，禁止标为 P50；
 *  · 决策输出标注为辅助建议。
 */
import { computed, ref } from 'vue'
import EChart from '../components/EChart.vue'
import StatCard from '../components/StatCard.vue'
import SourceNote from '../components/SourceNote.vue'
import { baseAxis, baseLegend, baseTooltip, AZURITE, CINNABAR, GOLD, INK_3, INK_4, LINE, OCHRE } from '../lib/charts'
import { cuts24, scenarioMeta, scenarios } from '../data/demo'
import { history } from '../data/history'
import { demoStats } from '../data/stats'
import { kpis } from '../data/kpi'
import { DECISION_DISCLAIMER, SYNTHETIC_LABEL_NOTE, thresholds } from '../data/meta'

const idx = ref(0)
const showLin = ref(true)
const showOutdoor = ref(true)

const scen = computed(() => scenarios[idx.value])
const meta = computed(() => scenarioMeta[idx.value])
const pts = computed(() => scen.value.points)

/** "2024-04-16 00:00:00+00:00" -> "04-16 00:00" */
function hh(t: string) {
  return t.slice(5, 16)
}
function f1(n: number) {
  return n.toFixed(1)
}

const peakRisk = computed(() => Math.max(...pts.value.map((p) => p.risk)))
const peakRisk90 = computed(() => Math.max(...pts.value.map((p) => p.risk90)))
const peakLin = computed(() => Math.max(...pts.value.map((p) => p.lin)))
const peakTrue = computed(() => Math.max(...pts.value.map((p) => p.true)))
const nOver62 = computed(() => pts.value.filter((p) => p.true >= 62).length)
const nAlarm = computed(() => pts.value.filter((p) => p.risk >= 62).length)

/** 综合风险读出：主读出与 τ=0.90 读出取较大者，用于风险态势面板 */
const riskNow = computed(() => Math.max(peakRisk.value, peakRisk90.value))
const gapTo62 = computed(() => 62 - riskNow.value)
const caught = computed(() => peakRisk.value >= 62)

const advice = computed(() => pts.value[0]?.adv ?? '正常开放')

/**
 * 决策时间轴：逐小时一格，共 73 格，覆盖 0–72 h 的完整预报窗。
 * 之前这里错写成「24 格 × 3 步」再按 0h/6h/…/24h 标注，格数与坐标标签对不上，
 * 现改为一格一小时，标签给到 72 h。
 */
const hourly = computed(() =>
  pts.value.map((p) => ({ h: p.th, n: 1, over: p.true >= 62 ? 1 : 0 })),
)

/* ------------------------------------------------------------------ 主预报图 */
const forecastOption = computed(() => {
  const xs = pts.value.map((p) => hh(p.t))
  const series: any[] = [
    {
      name: '窟内 RH 合成标签',
      type: 'line',
      data: pts.value.map((p) => p.true),
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 2, color: '#e8eef8' },
      itemStyle: { color: '#e8eef8' },
      z: 5,
      markArea: {
        silent: true,
        itemStyle: { color: 'rgba(212,85,63,0.10)' },
        data: [[{ yAxis: 62 }, { yAxis: 100 }]],
      },
      markLine: {
        silent: true,
        symbol: 'none',
        label: {
          formatter: (p: any) => `${thresholds[p.dataIndex]?.value ?? ''}% ${thresholds[p.dataIndex]?.label ?? ''}`,
          color: INK_3,
          fontSize: 10.5,
          // 标签放在线的左端。放右端（insideEndTop）会被画布右边界裁掉——
          // markLine 标签不会自动向内翻转。
          position: 'insideStartTop',
        },
        lineStyle: { type: 'dashed', width: 1 },
        data: [
          { yAxis: 62, lineStyle: { color: CINNABAR, opacity: 0.75 } },
          { yAxis: 67, lineStyle: { color: OCHRE, opacity: 0.6 } },
          { yAxis: 75, lineStyle: { color: GOLD, opacity: 0.5 } },
        ],
      },
    },
  ]
  if (showOutdoor.value) {
    series.push({
      name: '窟外 RH（驱动）',
      type: 'line',
      data: pts.value.map((p) => p.rhOut),
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 1, color: INK_4, type: 'dashed' },
      itemStyle: { color: INK_4 },
      z: 1,
    })
  }
  if (showLin.value) {
    series.push({
      name: '线性 MSE 对照（未做风险对齐）',
      type: 'line',
      data: pts.value.map((p) => p.lin),
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 1.4, color: INK_3, type: [5, 4] },
      itemStyle: { color: INK_3 },
      z: 3,
    })
  }
  series.push({
    name: 'τ=0.90 读出',
    type: 'line',
    data: pts.value.map((p) => p.risk90),
    smooth: true,
    symbol: 'none',
    lineStyle: { width: 1.4, color: OCHRE, opacity: 0.8 },
    itemStyle: { color: OCHRE },
    z: 3,
  })
  series.push({
    name: '风险对齐读出（τ=0.95，本作品）',
    type: 'line',
    data: pts.value.map((p) => p.risk),
    smooth: true,
    symbol: 'none',
    lineStyle: { width: 2.6, color: AZURITE },
    itemStyle: { color: AZURITE },
    areaStyle: { color: 'rgba(74,144,196,0.12)' },
    z: 6,
  })
  return {
    // 图例用图表下方的 HTML 版本（文案更长、可换行），所以这里不再让 ECharts 画一遍，
    // 否则图例条会压在 y 轴名称上。
    grid: { left: 44, right: 18, top: 32, bottom: 34 },
    tooltip: {
      ...baseTooltip,
      trigger: 'axis',
      valueFormatter: (v: any) => (typeof v === 'number' ? `${v.toFixed(1)} %RH` : '—'),
    },
    xAxis: {
      type: 'category',
      data: xs,
      boundaryGap: false,
      ...baseAxis,
      axisLabel: { ...baseAxis.axisLabel, interval: 11 },
    },
    yAxis: {
      type: 'value',
      name: '窟内相对湿度 / %',
      nameTextStyle: { color: INK_4, fontSize: 11, align: 'left' },
      min: 0,
      max: 100,
      ...baseAxis,
    },
    series,
  }
})

/* --------------------------------------------------------------- 背景态势图 */
const historyOption = computed(() => ({
  grid: { left: 44, right: 18, top: 36, bottom: 28 },
  legend: { ...baseLegend, data: ['窟内日最大', '窟内日均', '窟外日均'] },
  tooltip: { ...baseTooltip, trigger: 'axis', valueFormatter: (v: any) => (typeof v === 'number' ? `${v.toFixed(1)} %RH` : '—') },
  xAxis: { type: 'category', data: history.map((d) => d.t), boundaryGap: false, ...baseAxis, axisLabel: { ...baseAxis.axisLabel, interval: 180 } },
  yAxis: { type: 'value', min: 0, max: 100, ...baseAxis, splitLine: { lineStyle: { color: LINE, type: 'dashed', opacity: 0.4 } } },
  series: [
    {
      name: '窟内日最大',
      type: 'line',
      data: history.map((d) => d.max),
      symbol: 'none',
      lineStyle: { width: 1, color: CINNABAR, opacity: 0.55 },
      itemStyle: { color: CINNABAR },
      markLine: {
        silent: true,
        symbol: 'none',
        label: { formatter: '62% 业务预警线', color: INK_3, fontSize: 10.5, position: 'insideEndTop' },
        lineStyle: { color: CINNABAR, type: 'dashed', width: 1, opacity: 0.7 },
        data: [{ yAxis: 62 }],
      },
    },
    {
      name: '窟内日均',
      type: 'line',
      data: history.map((d) => d.mean),
      symbol: 'none',
      lineStyle: { width: 1.6, color: AZURITE },
      itemStyle: { color: AZURITE },
      areaStyle: { color: 'rgba(74,144,196,0.10)' },
    },
    {
      name: '窟外日均',
      type: 'line',
      data: history.map((d) => d.out),
      symbol: 'none',
      lineStyle: { width: 1, color: INK_4, type: 'dashed' },
      itemStyle: { color: INK_4 },
    },
  ],
}))

const gaugePct = computed(() => Math.min(100, riskNow.value))
</script>

<template>
  <section class="view-head">
    <h1>风险指挥台</h1>
    <p>
      从公开气象预报出发，直接给出未来 72 小时的窟内相对湿度风险读出与分级处置建议。
      下面每一条曲线、每一个数字都可在 <span class="src">code/results/*.csv</span> 中溯源。
    </p>
  </section>

  <!-- 情景切换 --------------------------------------------------------- -->
  <div class="row wrap between" style="margin-bottom: 14px">
    <div class="row wrap">
      <span class="eyebrow">演示窗口</span>
      <div class="seg">
        <button
          v-for="(s, i) in scenarios"
          :key="s.name"
          :class="{ on: idx === i }"
          @click="idx = i"
        >
          {{ s.name }}
        </button>
      </div>
      <span class="badge plain">起报 {{ meta.origin.slice(0, 16) }} · 逐小时 72 步</span>
    </div>
    <div class="row wrap">
      <div class="seg sm">
        <button :class="{ on: showLin }" @click="showLin = !showLin">线性对照</button>
        <button :class="{ on: showOutdoor }" @click="showOutdoor = !showOutdoor">窟外驱动</button>
      </div>
    </div>
  </div>

  <div class="console-grid">
    <!-- 左：主图 + 时间轴 ------------------------------------------------- -->
    <div class="stack">
      <div class="card">
        <div class="card-head">
          <div>
            <div class="card-title">窟内相对湿度 72 小时预报</div>
            <div class="card-sub">
              起报时刻 {{ meta.origin.slice(0, 16) }}（UTC） · 三条预报曲线同驱动、同特征，只差目标函数与读出方式
            </div>
          </div>
          <span class="badge">合成标签</span>
        </div>
        <div class="card-body">
          <EChart :option="forecastOption" height="330px" />
          <div class="legend">
            <span class="legend-item"><i class="legend-swatch" style="background: #e8eef8" />窟内合成标签</span>
            <span class="legend-item"><i class="legend-swatch" :style="{ background: AZURITE }" />风险对齐读出 τ=0.95（本作品）</span>
            <span class="legend-item"><i class="legend-swatch" :style="{ background: OCHRE }" />τ=0.90 读出</span>
            <span class="legend-item"><i class="legend-swatch" :style="{ background: INK_3 }" />线性 MSE 对照</span>
            <span class="legend-item"><i class="legend-swatch" :style="{ background: INK_4 }" />窟外 RH（驱动）</span>
          </div>
          <SourceNote kind="warn">
            窟内曲线为<b>文献标定物理模型生成的合成标签</b>，不是窟内实测；风险读出为分位数回归的<b>上分位读出</b>，
            不是预测分布中位数。三级阈值分别为 62%（业务流程线）、67%（潮解起始）、75%（吸湿突变）。
          </SourceNote>
        </div>
      </div>

      <div class="card">
        <div class="card-head">
          <div>
            <div class="card-title">决策时间轴 · 未来 72 小时</div>
            <div class="card-sub">每格 1 小时；染色格表示合成标签中该小时超过 62% 业务预警线</div>
          </div>
          <span class="badge" :class="nOver62 ? 'alert' : 'ok'">
            <i class="dot" />合成标签超阈 {{ nOver62 }} / 73 h
          </span>
        </div>
        <div class="card-body">
          <div class="timeline">
            <div class="tl-track">
              <div
                v-for="c in hourly"
                :key="c.h"
                class="tl-cell"
                :class="{ over: c.over > 0 }"
                :title="`第 ${c.h} 小时 · 合成标签${c.over ? '超阈' : '未超阈'}`"
              />
            </div>
            <div class="tl-axis">
              <span>0 h</span><span>18 h</span><span>36 h</span><span>54 h</span><span>72 h</span>
            </div>
          </div>

          <div class="hr" />

          <div class="row wrap" style="gap: 22px">
            <div class="col">
              <span class="eyebrow">24 h 判定切点（预报值口径）</span>
              <span class="num">{{ cuts24['62'].toFixed(2) }} / {{ cuts24['67'].toFixed(2) }} / {{ cuts24['75'].toFixed(2) }} %RH</span>
            </div>
            <div class="col">
              <span class="eyebrow">模型给出的处置建议</span>
              <span class="badge" :class="nAlarm ? 'alert' : 'ok'">{{ advice }}</span>
            </div>
            <div class="col">
              <span class="eyebrow">本窗口发出预警的小时数</span>
              <span class="num">{{ nAlarm }} h</span>
            </div>
          </div>

          <SourceNote kind="watch">
            本窗口风险读出峰值 {{ f1(peakRisk) }}%RH，未触及 62% 判定线，系统维持「正常开放」建议；
            同窗口合成标签真实峰值 <b>{{ f1(peakTrue) }}%RH</b>、其中 13 小时超过 62%。
            单一窗口不代表整体水平——完整测试段的滚动预警能力见「效果对照」页。
          </SourceNote>
        </div>
      </div>
    </div>

    <!-- 右：风险态势 + 建议 ---------------------------------------------- -->
    <div class="stack">
      <div class="card">
        <div class="card-head">
          <div class="card-title">风险态势</div>
          <span class="badge" :class="caught ? 'alert' : 'watch'">
            <i class="dot" />{{ caught ? '触发预警' : '未触发预警' }}
          </span>
        </div>
        <div class="card-body">
          <div class="eyebrow">模型风险读出峰值</div>
          <div class="h-display" :style="{ color: caught ? CINNABAR : AZURITE }">{{ f1(peakRisk) }}<span style="font-size: 15px; color: var(--ink-3)"> %RH</span></div>
          <div class="dim" style="font-size: 11.5px">
            距 62% 业务预警线还差 <b class="num">{{ f1(gapTo62) }}</b> 个百分点
          </div>

          <div class="gauge" style="margin-top: 14px">
            <div class="gauge-track">
              <div v-for="t in thresholds" :key="t.value" class="gauge-mark danger" :style="{ left: t.value + '%' }" />
              <div class="gauge-needle" :style="{ left: gaugePct + '%' }" />
            </div>
            <div class="gauge-labels">
              <span>0</span>
              <span v-for="t in thresholds" :key="t.value" :style="{ position: 'absolute', left: t.value + '%' }">{{ t.value }}%</span>
              <span style="position: absolute; right: 0">100</span>
            </div>
          </div>

          <div class="hr" />

          <dl class="kv">
            <dt>合成标签峰值</dt><dd>{{ f1(peakTrue) }} %RH</dd>
            <dt>τ=0.90 读出峰值</dt><dd>{{ f1(peakRisk90) }} %RH</dd>
            <dt>线性 MSE 对照峰值</dt><dd>{{ f1(peakLin) }} %RH</dd>
            <dt>超阈小时数（标签）</dt><dd>{{ nOver62 }} / 73 h</dd>
            <dt>预警小时数（模型）</dt><dd>{{ nAlarm }} / 73 h</dd>
          </dl>
        </div>
      </div>

      <div class="card">
        <div class="card-head">
          <div class="card-title">处置建议</div>
        </div>
        <div class="card-body">
          <div class="callout" :class="nAlarm ? 'alert' : 'ok'">
            <b>{{ advice }}</b><br />
            <span class="dimmer">模型在 {{ meta.name }} 窗口给出的原始建议，未经人工修改。</span>
          </div>
          <p class="note">
            <b>判定依据</b>：风险读出峰值 {{ f1(peakRisk) }}%RH，低于 24 h 判定切点
            {{ cuts24['62'].toFixed(2) }}%RH（由验证年份校准得到，而非直接用阈值 62%）。
            模型据此判定未来 72 小时无需限流。
          </p>
          <p class="note info">{{ DECISION_DISCLAIMER }}</p>
        </div>
      </div>
    </div>
  </div>

  <!-- KPI ------------------------------------------------------------- -->
  <div class="grid g-4" style="margin-top: 14px">
    <StatCard
      v-for="(k, i) in kpis"
      :key="k.label"
      :label="k.label"
      :value="k.value"
      :sub="k.sub"
      :hint="k.hint"
      :scope="k.scope"
      :accent="k.scope === 'upper' ? 'ochre' : ['azurite', 'malachite', 'ochre', 'gold'][i]"
    />
  </div>
  <SourceNote kind="info">
    前两张为<b>端到端</b>口径（真实预报驱动）；后两张为<b>可部署性上界</b>口径
    （以真实未来再分析替代预报），两者不得混读。出处 <span class="src">code/results/exp03_abc_ablation.csv、derisk02_leadtime.csv</span>。
  </SourceNote>

  <!-- 三窗口对照 ------------------------------------------------------- -->
  <div class="card">
    <div class="card-head">
      <div>
        <div class="card-title">三个演示窗口横向对照</div>
        <div class="card-sub">同一模型、同一套参数，不做任何逐窗口调参</div>
      </div>
    </div>
    <div class="card-body tight">
      <table class="tbl">
        <thead>
          <tr>
            <th>窗口</th>
            <th class="r">合成标签峰值</th>
            <th class="r">超阈小时</th>
            <th class="r">风险读出峰值</th>
            <th class="r">τ=0.90 峰值</th>
            <th class="r">线性对照峰值</th>
            <th class="r">预警小时</th>
            <th>结果</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(m, i) in scenarioMeta" :key="m.name" :class="{ hl: i === idx }">
            <td class="strong">{{ m.name }}</td>
            <td class="r">{{ m.truePeak.toFixed(1) }}%</td>
            <td class="r">{{ m.nTrueOver62 }} / {{ m.n }}</td>
            <td class="r strong">{{ m.riskPeak.toFixed(1) }}%</td>
            <td class="r">{{ m.risk90Peak.toFixed(1) }}%</td>
            <td class="r">{{ m.linPeak.toFixed(1) }}%</td>
            <td class="r">{{ m.nRiskOver62 }} h</td>
            <td>
              <span class="badge" :class="m.nRiskOver62 ? 'alert' : 'watch'">
                {{ m.nRiskOver62 ? '已预警' : '未预警' }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
      <SourceNote kind="alert">
        三个窗口<b>均未触发预警</b>。偏高湿窗口的标签峰值 72.9%、高湿事件窗口 89.0%，均远高于 62% 业务线，
        而 τ=0.95 读出的峰值分别只有 {{ scenarioMeta[1].riskPeak.toFixed(1) }}% 与 {{ scenarioMeta[0].riskPeak.toFixed(1) }}%。
        相对线性对照（{{ scenarioMeta[0].linPeak.toFixed(1) }}% / {{ scenarioMeta[1].linPeak.toFixed(1) }}%）本作品已明显抬高读出，
        但距离可用的预警灵敏度仍有差距——这是本项目当前最主要的短板。
      </SourceNote>
    </div>
  </div>

  <!-- 背景态势 --------------------------------------------------------- -->
  <div class="card">
    <div class="card-head">
      <div>
        <div class="card-title">背景态势 · 演示窟历年逐日相对湿度</div>
        <div class="card-sub">
          {{ demoStats.period.slice(0, 10) }} 起共 {{ demoStats.n_hours.toLocaleString() }} 小时，日均 {{ demoStats.RH_in_mean }}%RH；
          全年有 {{ demoStats.frac_gt62 }}% 的小时超过 62%
        </div>
      </div>
      <span class="badge plain">合成序列</span>
    </div>
    <div class="card-body">
      <EChart :option="historyOption" height="230px" />
      <SourceNote>
        数据出处 <span class="src">code/results/demo_history.csv</span>；超阈比例出处
        <span class="src">code/results/demo_stats.json</span>（原值已是百分数）。
      </SourceNote>
    </div>
  </div>
</template>
