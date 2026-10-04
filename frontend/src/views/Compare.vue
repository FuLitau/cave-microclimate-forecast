<script setup lang="ts">
import Chart from '../components/Chart.vue'
import Panel from '../components/Panel.vue'
import { ablation } from '../data/ablation'
import { models24, leadtime, baselines } from '../data/compare'
import { iccp, crosscave, isd } from '../data/validate'

const thr = ['62', '67', '75']
const modeColor: Record<string, string> = { A: '#5d7191', B: '#e2a24a', C: '#56c2de' }
const modeLabel: Record<string, string> = {
  A: 'A · MSE（现有做法）', B: 'B · MSE + twCRPS', C: 'C · + 内生权重'
}

function grouped(field: 'F1' | 'AUC') {
  return thr.map(t => {
    const o: Record<string, unknown> = { name: t + '%' }
    for (const r of ablation.filter(x => x.thr === t)) o[r.mode] = r[field]
    return o
  })
}

const common = {
  backgroundColor: 'transparent',
  grid: { left: 44, right: 12, top: 34, bottom: 26 },
  legend: { top: 0, textStyle: { color: '#8ba0bd', fontSize: 11 } },
  xAxis: { type: 'category', data: thr.map(t => t + '%'), axisLine: { lineStyle: { color: '#27395a' } }, axisLabel: { color: '#8ba0bd' } },
  yAxis: { type: 'value', axisLabel: { color: '#8ba0bd' }, splitLine: { lineStyle: { color: '#16233a' } } }
}

function seriesFor(field: 'F1' | 'AUC') {
  return ['A', 'B', 'C'].map(m => ({
    name: modeLabel[m], type: 'bar' as const, color: modeColor[m], barWidth: 16,
    data: grouped(field).map(g => (g as Record<string, number>)[m] ?? 0),
    itemStyle: { color: modeColor[m], borderRadius: [4, 4, 0, 0] },
    label: {
      show: true, position: 'top' as const, color: '#8ba0bd', fontSize: 10,
      formatter: (p: { value: number }) => Number(p.value) > 0 ? Number(p.value).toFixed(3) : ''
    }
  }))
}

const f1Opt = { ...common, grid: { ...common.grid, top: 46 }, series: seriesFor('F1') }
const aucOpt = { ...common, grid: { ...common.grid, top: 46 }, series: seriesFor('AUC') }

const shortName: Record<string, string> = {
  'Operator-direct(本作品)': '本作品 · 输运+风险对齐',
  'Ablation-无慢变项': '消融 · 无慢变项',
  'Ablation-无Magnus项': '消融 · 无 Magnus 项',
  'Ablation-仅快变延迟': '消融 · 仅快变延迟',
  'Ablation-短延迟(12h)': '消融 · 短延迟(12h)',
  'FirstOrderTransfer-直接传递(初稿形式)': '初稿 · 直接传递',
  'FirstOrderTransfer-仅外场滞后(初稿原文)': '初稿 · 仅外场滞后（原文）',
  'FirstOrderTransfer-递归推演(不稳定极点)': '初稿 · 递归推演（发散）',
  'RidgeDirect(无延迟嵌入)': '直接回归（无延迟嵌入）',
  'Persistence-operator(可部署)': '持续性（可部署）',
  '[oracle]Persistence(需窟内实测)': '[oracle] 持续性（不可部署）',
  'Climatology(可部署)': '气候均值（可部署）'
}

function hBar(field: 'AUC' | 'F1', color: string) {
  return {
    backgroundColor: 'transparent',
    grid: { left: 190, right: 46, top: 26, bottom: 22 },
    xAxis: { type: 'value', max: 1, axisLabel: { color: '#8ba0bd', fontSize: 10 }, splitLine: { lineStyle: { color: '#16233a' } } },
    yAxis: {
      type: 'category', inverse: true,
      data: models24.map(m => shortName[m.model] || m.model),
      axisLabel: { color: '#8ba0bd', fontSize: 10.5 }, axisLine: { lineStyle: { color: '#27395a' } }
    },
    series: [{
      name: field, type: 'bar', color,
      data: models24.map(m => m[field]),
      itemStyle: { color, borderRadius: [0, 4, 4, 0] }, barWidth: 11,
      label: { show: true, position: 'right', color: '#8ba0bd', fontSize: 9.5, formatter: (p: { value: number }) => Number(p.value).toFixed(3) }
    }]
  }
}
const aucBarOpt = hBar('AUC', '#56c2de')
const f1BarOpt = hBar('F1', '#e2a24a')

// 管线口径：Te'omim 洞信号方差低于 SD 门限被剔除；极端负 R² 截断至 −1 显示（Sela' 基线 −10.5 等）
const iccpShown = iccp.filter(c => c.name !== "Te'omim")
const clampR2 = (v: number) => Math.max(-1, Math.min(1, v))
const iccpOpt = {
  backgroundColor: 'transparent',
  grid: { left: 40, right: 14, top: 34, bottom: 64 },
  legend: { top: 0, textStyle: { color: '#8ba0bd', fontSize: 11 } },
  xAxis: { type: 'category', data: iccpShown.map(c => c.name), axisLabel: { color: '#5d7191', fontSize: 10, rotate: 40 }, axisLine: { lineStyle: { color: '#27395a' } } },
  yAxis: {
    type: 'value', name: '测试 R²', min: -1.05, max: 1.05, nameTextStyle: { color: '#5d7191' },
    axisLabel: { color: '#8ba0bd' }, splitLine: { lineStyle: { color: '#16233a' } }
  },
  series: [
    { name: '一阶传递（初稿形式）', type: 'bar', color: '#5d7191', data: iccpShown.map(c => clampR2(c.r2Fot)), itemStyle: { color: '#5d7191', borderRadius: [3, 3, 0, 0] }, barWidth: 12 },
    { name: '输运算子（本作品）', type: 'bar', color: '#e2a24a', data: iccpShown.map(c => clampR2(c.r2Op)), itemStyle: { color: '#e2a24a', borderRadius: [3, 3, 0, 0] }, barWidth: 12 }
  ]
}

const lead = leadtime.find(l => l.model.includes('本作品'))!
const leadFot = leadtime.find(l => l.model.includes('初稿'))!

function baseNote(m: string): string {
  if (m.includes('Persistence')) return '滞后使用窟内真值，不可部署，仅作诊断上界'
  if (m.includes('递归') || m.includes('递归推演')) return '极点 > 1，数值发散，必须弃用'
  if (m.includes('初稿')) return '初稿静态传递形式'
  if (m.includes('RidgeDirect')) return '无延迟嵌入的直接回归'
  if (m.includes('Operator-Full')) return '本作品 · 258 维延迟嵌入输运'
  if (m.startsWith('Ablation')) return '消融变体（特征族裁剪）'
  return ''
}
const fmtRmse = (v: number) => (Math.abs(v) > 1e6 ? '发散' : v.toFixed(2))

const isdMap: Record<string, string> = {
  'T2M (°C)': '气温 r = 0.955',
  '站压 @1140 m (hPa)': '本站气压 r = 0.939',
  'RH2M (%)': '湿度 r = 0.576（分辨率上限，如实披露）'
}
</script>

<template>
  <div class="page-head">
    <div class="page-title">模型对比</div>
    <div class="page-cap">
      所有数字均出自 code/results/ 下的实验落盘 CSV；端到端口径含 L1 预报误差，检出率/提前量为理想外场驱动的滚动预报口径
    </div>
  </div>

  <div class="grid-2">
    <Panel title="风险对齐消融：损失函数的增益" cap="测试段 · 24 h 时效 · 三档阈值（exp03_abc_ablation.csv）">
      <div style="display: flex; gap: 14px">
        <div style="flex: 1">
          <div style="text-align: center; color: var(--dim); font-size: 12px; margin-bottom: 4px">超阈 F1</div>
          <Chart :option="f1Opt" height="230px" />
        </div>
        <div style="flex: 1">
          <div style="text-align: center; color: var(--dim); font-size: 12px; margin-bottom: 4px">AUC</div>
          <Chart :option="aucOpt" height="230px" />
        </div>
      </div>
      <div class="note">
        在 MSE 目标上引入阈值加权风险项（twCRPS）后，F1 由 0.072 提升至 0.164、AUC 由 0.862 提升至 0.903，
        点预报精度不降反升（pt_R² 0.585 → 0.655）；"内生权重"强化版经消融验证无稳定增益，最终未采用。
      </div>
    </Panel>

    <Panel title="与可部署基线的预警能力对比" cap="24 h 时效 / 62% 档（derisk02_events.csv）· 上 AUC / 下 F1">
      <Chart :option="aucBarOpt" height="252px" />
      <Chart :option="f1BarOpt" height="252px" />
      <div class="note">
        滚动预报口径下：本作品检出率 <b style="color:var(--amber2)">{{ (lead.detect * 100).toFixed(1) }}%</b>、平均首次预警提前
        <b style="color:var(--amber2)">{{ lead.lead.toFixed(1) }} h</b>；初稿直接传递形式为
        {{ (leadFot.detect * 100).toFixed(1) }}% / {{ leadFot.lead.toFixed(1) }} h。
        初稿原文（仅外场滞后）AUC 达 0.896，但校准阈值落在 48.9%、F1 仅 0.052——抓到了形状、丢掉了量级。
      </div>
    </Panel>
  </div>

  <div class="grid-2">
    <Panel title="真实洞穴外部验证 · ICCP 12 洞逐洞对比" cap="以色列岩溶洞穴 2019–2021 逐小时观测（CC-BY-4.0），不含任何合成标签；只验证输运建模思路在真实洞穴成立，不声称莫高窟精度">
      <Chart :option="iccpOpt" height="280px" />
      <div class="note">
        12 洞按管线口径剔除无受光区与低信号方差（SD &lt; 0.5）洞窟后为 8 洞，输运算子在其中
        <b style="color:var(--amber2)">{{ iccpShown.filter(c => c.r2Op > c.r2Fot).length }}/{{ iccpShown.length }}</b>
        洞占优；Sela' / Tzruya 的基线 R² 为 −10.5 / −2.3，图中截断至 −1 显示；本作品在个别信号极弱洞窟亦为负值，如实呈现。
      </div>
    </Panel>

    <div>
      <Panel title="外场真实性交叉核对" cap="NASA POWER 再分析 vs 敦煌地面站观测（NOAA ISD）">
        <div class="grid-3" style="gap: 10px">
          <div v-for="v in isd" :key="v.variable" class="kpi" style="padding: 12px 14px">
            <div class="kpi-label" style="font-size: 11.5px">{{ isdMap[v.variable]?.split(' r')[0] || v.variable }}</div>
            <div class="kpi-value" style="font-size: 20px">r = {{ v.r.toFixed(3) }}</div>
          </div>
        </div>
        <div class="note">再分析资料与站点观测在气温、气压上高度一致；湿度相关性有限，已作为外场湿度分辨率上限如实披露。</div>
      </Panel>

      <Panel title="跨窟验证与点预测基线" cap="validate_crosscave.csv · derisk01_model_comparison.csv">
        <table class="tb">
          <thead><tr><th>跨窟验证指标</th><th>模型（第 87 窟标定）</th><th>文献（第 71 窟）</th><th>判定</th></tr></thead>
          <tbody>
            <tr v-for="c in crosscave" :key="c.metric">
              <td>{{ c.metric }}</td>
              <td class="num">{{ c.lo }} ~ {{ c.hi }}</td>
              <td class="num">{{ c.litLo }} ~ {{ c.litHi }}</td>
              <td><span class="badge" :class="c.pass ? 'ok' : 'bad'">{{ c.pass ? '通过' : '未通过' }}</span></td>
            </tr>
          </tbody>
        </table>
        <table class="tb" style="margin-top: 10px">
          <thead><tr><th>点预测基线（测试段）</th><th>RMSE</th><th>R²</th><th>说明</th></tr></thead>
          <tbody>
            <tr v-for="b in baselines" :key="b.model">
              <td>{{ b.model }}</td>
              <td class="num">{{ fmtRmse(b.RMSE) }}</td>
              <td class="num">{{ Math.abs(b.R2) > 1e6 ? '发散' : b.R2.toFixed(3) }}</td>
              <td style="color: var(--faint)">{{ baseNote(b.model) }}</td>
            </tr>
          </tbody>
        </table>
      </Panel>
    </div>
  </div>
</template>
