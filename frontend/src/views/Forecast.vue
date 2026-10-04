<script setup lang="ts">
import { computed, ref } from 'vue'
import Chart from '../components/Chart.vue'
import Panel from '../components/Panel.vue'
import { kpis } from '../data/kpi'
import { scenarios } from '../data/demo'

const cur = ref(scenarios[0].name)
const scen = computed(() => scenarios.find(s => s.name === cur.value)!)
const pts = computed(() => scen.value.points)

const TH = [
  { v: 62, c: '#e2a24a', t: '62% 业务预警' },
  { v: 67, c: '#e8833a', t: '67% 潮解起始' },
  { v: 75, c: '#e0635c', t: '75% 吸湿突变' }
]

function fmtT(t: string) { return t.slice(5, 16).replace('T', ' ') }

// 预报建议 ≠ 正常开放 的连续时段 → 背景色带
const alarmAreas = computed(() => {
  const areas: Array<{ xAxis: string[]; itemStyle: { color: string } }> = []
  let start: string | null = null
  let prev: string | null = null
  for (const p of pts.value) {
    const alarm = p.advice !== '正常开放'
    if (alarm && !start) start = p.t
    if (!alarm && start) { areas.push({ xAxis: [fmtT(start), fmtT(prev!)] , itemStyle: { color: 'rgba(226,162,74,0.13)' } }); start = null }
    if (alarm) prev = p.t
  }
  if (start) areas.push({ xAxis: [fmtT(start), fmtT(prev!)], itemStyle: { color: 'rgba(226,162,74,0.13)' } })
  return areas
})

const chartOpt = computed(() => ({
  backgroundColor: 'transparent',
  grid: { left: 46, right: 16, top: 40, bottom: 30 },
  tooltip: { trigger: 'axis' },
  legend: {
    data: ['窟外 RH（驱动）', '窟内 RH 真值', '预报中位数', '预报 P90'],
    textStyle: { color: '#8ba0bd', fontSize: 11 }, top: 0
  },
  xAxis: {
    type: 'category',
    data: pts.value.map(p => fmtT(p.t)),
    axisLine: { lineStyle: { color: '#27395a' } },
    axisLabel: { color: '#5d7191', fontSize: 10, interval: Math.max(2, Math.floor(pts.value.length / 12)) }
  },
  yAxis: {
    type: 'value', name: 'RH %', min: 0, max: 100, nameTextStyle: { color: '#5d7191' },
    axisLabel: { color: '#8ba0bd' }, splitLine: { lineStyle: { color: '#16233a' } }
  },
  series: [
    {
      name: '窟外 RH（驱动）', type: 'line', color: '#5d7191', data: pts.value.map(p => p.rhOut),
      symbol: 'none', lineStyle: { color: '#5d7191', width: 1, type: 'dashed' }
    },
    {
      name: '窟内 RH 真值', type: 'line', color: '#56c2de', data: pts.value.map(p => p.true),
      symbol: 'none', lineStyle: { color: '#56c2de', width: 1.6 }
    },
    {
      name: '_band_base', type: 'line', stack: 'band', data: pts.value.map(p => p.p50),
      symbol: 'none', lineStyle: { opacity: 0 }, areaStyle: { opacity: 0 }, silent: true,
      tooltip: { show: false }
    },
    {
      name: '预报 P90', type: 'line', color: '#e2a24a', stack: 'band',
      data: pts.value.map(p => Math.max(0, p.p90 - p.p50)), symbol: 'none',
      lineStyle: { opacity: 0 },
      areaStyle: { color: 'rgba(226,162,74,0.16)' },
      markArea: { silent: true, data: alarmAreas.value },
      markLine: {
        symbol: 'none', silent: true, label: { position: 'insideEndTop', fontSize: 10 },
        data: TH.map(h => ({ yAxis: h.v, lineStyle: { color: h.c, type: 'dashed' }, label: { color: h.c, formatter: h.t } }))
      }
    },
    {
      name: '预报中位数', type: 'line', color: '#e2a24a', data: pts.value.map(p => p.p50),
      symbol: 'none', lineStyle: { color: '#e2a24a', width: 2.2 }
    }
  ]
}))

const maxP90 = computed(() => Math.max(...pts.value.map(p => p.p90)))
const adviceSeq = computed(() => pts.value.map(p => p.advice))
const nAlarmHours = computed(() => adviceSeq.value.filter(a => a !== '正常开放').length)
</script>

<template>
  <div class="page-head">
    <div class="page-title">预报看板</div>
    <div class="page-cap">
      单窟未来 72 小时窟内湿度轨迹预报与风险预警 —— 演示口径：τ=0.95 分位数读出，窟内真值为文献标定物理模型生成
    </div>
  </div>

  <div style="display: flex; gap: 10px; margin-bottom: 16px">
    <button v-for="s in scenarios" :key="s.name" class="chip" :class="{ on: cur === s.name }" @click="cur = s.name">
      {{ s.name }}
    </button>
    <span style="flex: 1" />
    <span v-if="nAlarmHours > 0" class="badge warn">本窗口建议"限流/关闭" {{ nAlarmHours }} 小时</span>
    <span v-else class="badge info">本窗口未触发限流建议 · 预报 P90 峰值 {{ maxP90.toFixed(1) }}%（62% 阈值）</span>
  </div>

  <Panel :title="`演示窟 · ${cur} 场景 72 h 预报`" cap="琥珀色实线 = 预报中位数；浅琥珀带 = 预报 P90；灰虚线 = 窟外驱动 RH；背景色带 = 预报触发限流/关闭建议的时段">
    <Chart :option="chartOpt" height="380px" />
  </Panel>

  <div class="grid-2">
    <Panel title="这屏在做什么">
      <p class="para">
        管理人员每天要回答的不是"窟内现在湿度多少"，而是<b>"未来 72 小时会不会长时间超过风险阈值"</b>。
        本看板以过去 168 小时窟外气象为输入，给出未来 72 小时的窟内湿度概率预报（中位数 + P90），
        并对照三级风险参考阈值给出限流 / 关闭的<b>辅助建议</b>与预计时段。
      </p>
      <p class="para">
        窟外湿度经围岩热湿传递进入窟内，存在明显的<b>延迟、衰减与记忆</b>——预报曲线的形态滞后于窟外，
        正是输运算子刻画的对象。
      </p>
    </Panel>
    <Panel title="这套预警的实测表现" cap="62% 档 · 测试段 2021–2025">
      <div class="grid-2" style="gap: 10px">
        <div class="kpi">
          <div class="kpi-label">预警检出率（上界）</div>
          <div class="kpi-value" style="font-size: 21px">{{ kpis[2].value }}</div>
          <div class="kpi-hint">{{ kpis[2].sub }}</div>
        </div>
        <div class="kpi">
          <div class="kpi-label">平均首次预警提前</div>
          <div class="kpi-value" style="font-size: 21px">{{ kpis[3].value }}</div>
          <div class="kpi-hint">事件前 72 h 窗口内滚动预报口径</div>
        </div>
      </div>
      <div class="note">
        两个数字为理想外场驱动（以真实未来再分析替代预报）的<b style="color:var(--dim)">可部署性上界</b>；
        端到端口径（含 L1 预报误差）的排序与检出指标见"模型对比"页。
      </div>
    </Panel>
  </div>
</template>
