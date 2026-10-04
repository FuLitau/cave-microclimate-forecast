<script setup lang="ts">
import { computed, ref } from 'vue'
import Chart from '../components/Chart.vue'
import Panel from '../components/Panel.vue'
import { kpis } from '../data/kpi'
import { scenarios } from '../data/demo'
import { events62 } from '../data/compare'

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
    data: ['窟外 RH（驱动）', '窟内 RH 真值', '预报中位数', '预报 P90', 'MSE 读出（未风险对齐）'],
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
      name: 'MSE 读出（未风险对齐）', type: 'line', color: '#e0635c', data: pts.value.map(p => p.lin),
      symbol: 'none', lineStyle: { color: '#e0635c', width: 1.2, type: 'dotted' }
    },
    {
      name: '预报中位数', type: 'line', color: '#e2a24a', data: pts.value.map(p => p.p50),
      symbol: 'none', lineStyle: { color: '#e2a24a', width: 2.2 }
    }
  ]
}))

const maxP90 = computed(() => Math.max(...pts.value.map(p => p.p90)))
const maxLin = computed(() => Math.max(...pts.value.map(p => p.lin)))
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

  <Panel :title="`演示窟 · ${cur} 场景 72 h 预报`" cap="琥珀色实线 = 预报中位数；浅琥珀带 = 预报 P90；红色点线 = 未做风险对齐的 MSE 读出（同驱动对照）；灰虚线 = 窟外驱动 RH；背景色带 = 建议时段">
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
      <p class="para">
        <b>红线就是"不用我们方法"的样子。</b>红色点线是与本作品完全相同特征、但仍用 MSE 训练的读出：
        它系统性把湿度压得更低（本窗口峰值 {{ maxLin.toFixed(1) }}% vs 本作品 {{ Math.max(...pts.value.map(p => p.p50)).toFixed(1) }}%），
        离真实风险更远——这就是"平均意义上较准、风险意义上失真"的直接可视。
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

  <Panel title="用与不用，差别在这里：94 次真实超阈事件的预警命中" cap="每个圆点 = 测试段一次真实的湿度超阈起报事件（24 h 时效 / 62% 档，derisk02_leadtime.csv）；亮起 = 在事件前 72 h 窗口内发出过预警">
    <div v-for="row in events62" :key="row.name" style="margin-bottom: 16px">
      <div style="display: flex; align-items: baseline; gap: 10px; margin-bottom: 6px">
        <span style="font-size: 13px; font-weight: 700; min-width: 210px">{{ row.name }}</span>
        <span class="badge" :class="row.hit > 0 ? 'warn' : 'bad'">命中 {{ row.hit }} / {{ row.onset }}</span>
        <span style="font-size: 11.5px; color: var(--faint)">{{ row.note }}</span>
      </div>
      <div style="display: flex; flex-wrap: wrap; gap: 4px">
        <span v-for="i in row.onset" :key="i" :style="{
          width: '10px', height: '10px', borderRadius: '50%',
          background: i <= row.hit ? '#e2a24a' : '#1a2740',
          boxShadow: i <= row.hit ? '0 0 6px rgba(226,162,74,0.5)' : 'none'
        }" />
      </div>
    </div>
    <div class="note">
      初稿递归形式 0 命中：极点大于 1，推演必然饱和，"从不能预警"（docs/03 §5.9）。
      点阵为理想外场驱动的滚动预报口径；MSE 点预报直接判阈（端到端口径）召回率仅 0.047——
      若用"预测值 ≥ 阈值即报警"的传统方式，这 94 个点亮起来的会更少。
    </div>
  </Panel>
</template>
