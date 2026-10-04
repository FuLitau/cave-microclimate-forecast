<script setup lang="ts">
import Chart from '../components/Chart.vue'
import Panel from '../components/Panel.vue'
import { kpis } from '../data/kpi'
import { history } from '../data/history'
import { demoStats } from '../data/stats'

const histOpt = {
  backgroundColor: 'transparent',
  grid: { left: 46, right: 14, top: 30, bottom: 26 },
  tooltip: { trigger: 'axis' },
  legend: { data: ['窟内日均 RH', '窟内日最高 RH'], textStyle: { color: '#8ba0bd', fontSize: 11 }, top: 0 },
  xAxis: {
    type: 'category',
    data: history.map(p => p.t),
    axisLine: { lineStyle: { color: '#27395a' } },
    axisLabel: { color: '#5d7191', fontSize: 10, interval: 240 }
  },
  yAxis: {
    type: 'value', name: 'RH %', nameTextStyle: { color: '#5d7191' },
    axisLabel: { color: '#8ba0bd' }, splitLine: { lineStyle: { color: '#16233a' } }
  },
  series: [
    {
      name: '窟内日最高 RH', type: 'line', color: '#e0635c', data: history.map(p => p.max),
      symbol: 'none', lineStyle: { color: 'rgba(224,99,92,0.55)', width: 1 }
    },
    {
      name: '窟内日均 RH', type: 'line', color: '#56c2de', data: history.map(p => p.mean),
      symbol: 'none', lineStyle: { color: '#56c2de', width: 1.4 },
      areaStyle: { color: 'rgba(86,194,222,0.08)' },
      markLine: {
        symbol: 'none', silent: true, label: { position: 'insideEndTop', fontSize: 10 },
        data: [
          { yAxis: 62, lineStyle: { color: '#e2a24a', type: 'dashed' }, label: { color: '#e2a24a', formatter: '62% 业务预警' } },
          { yAxis: 67, lineStyle: { color: '#e8833a', type: 'dashed' }, label: { color: '#e8833a', formatter: '67% 潮解起始' } },
          { yAxis: 75, lineStyle: { color: '#e0635c', type: 'dashed' }, label: { color: '#e0635c', formatter: '75% 吸湿突变' } }
        ]
      }
    }
  ]
}

const expo = [
  { k: '超 62%（业务预警）', v: demoStats.frac_gt62, c: '#e2a24a' },
  { k: '超 67%（潮解起始）', v: demoStats.frac_gt67, c: '#e8833a' },
  { k: '超 75%（吸湿突变）', v: demoStats.frac_gt75, c: '#e0635c' }
]
const expoMax = Math.max(...expo.map(e => e.v)) || 1
</script>

<template>
  <div class="page-head">
    <div class="page-title">风险总览</div>
    <div class="page-cap">
      面向石窟寺文物保护的窟内微气候风险预报 —— 由公开室外气象驱动，对未来 24–72 小时窟内湿度及超阈风险提前预警
    </div>
  </div>

  <div class="grid-4">
    <div v-for="k in kpis" :key="k.label" class="kpi" :title="k.hint">
      <div class="kpi-label">{{ k.label }}</div>
      <div class="kpi-value">{{ k.value }}</div>
      <div class="kpi-sub">{{ k.sub }}</div>
      <div class="kpi-hint">{{ k.hint }}</div>
    </div>
  </div>

  <div class="grid-23" style="margin-top: 18px">
    <Panel title="演示窟 · 四年窟内湿度环境（2022–2025）" cap="窟内序列由文献标定物理模型生成；虚线为三级风险参考阈值（敦煌研究院业务口径 62% / Demas 2015 潮解起始 67% / npj Heritage Science 2025 吸湿突变 75%）">
      <Chart :option="histOpt" height="340px" />
    </Panel>

    <div>
      <Panel title="阈值暴露统计" :cap="`演示窟 ${demoStats.n_hours.toLocaleString()} 小时中超过各级阈值的时长占比`">
        <div v-for="e in expo" :key="e.k" style="margin-bottom: 14px">
          <div style="display: flex; justify-content: space-between; font-size: 12.5px">
            <span style="color: var(--dim)">{{ e.k }}</span>
            <span style="font-variant-numeric: tabular-nums">{{ e.v.toFixed(2) }}%</span>
          </div>
          <div style="height: 8px; background: #16233a; border-radius: 4px; margin-top: 5px; overflow: hidden">
            <div :style="{ width: (e.v / expoMax * 100) + '%', height: '100%', background: e.c, borderRadius: 4 }" />
          </div>
        </div>
        <div class="note">
          高湿暴露是尾部事件：绝大多数时间湿度安全，风险集中在少数时段 —— 这正是"平均误差"训练目标容易漏报的部分。
        </div>
      </Panel>

      <Panel title="风险决策映射">
        <div style="display: flex; flex-direction: column; gap: 9px; font-size: 13px">
          <div><span class="badge ok">正常开放</span> <span style="color: var(--dim)">预报风险未触及参考阈值</span></div>
          <div><span class="badge warn">限流</span> <span style="color: var(--dim)">62% 档风险触发，控制游客批次</span></div>
          <div><span class="badge bad">关闭</span> <span style="color: var(--dim)">67% / 75% 档风险触发，暂停开放并除湿</span></div>
        </div>
        <div class="note">输出为辅助建议，供管理人员研判，不构成自动决策。</div>
      </Panel>
    </div>
  </div>

  <Panel title="三层技术路线" cap="公开气象数据 → 风险预报 → 决策建议的完整闭环">
    <div class="pipe">
      <div class="pipe-stage">
        <span class="pipe-tag">L1 · 气象预报</span>
        <div class="pipe-name">多时效概率预报网络</div>
        <div class="pipe-io">过去 168 h 外场 → 未来 72 h 分位数轨迹</div>
        <div class="pipe-desc">MLP 神经网络，直接输出分位数，保留预报不确定性。</div>
      </div>
      <div class="pipe-arrow">→</div>
      <div class="pipe-stage">
        <span class="pipe-tag">L2 · 微气候输运</span>
        <div class="pipe-name">延迟嵌入输运算子</div>
        <div class="pipe-io">室外气象轨迹 → 窟内湿度风险</div>
        <div class="pipe-desc">借鉴 Koopman/EDMD 思想：258 维延迟嵌入特征 + 岭回归闭式解，刻画围岩热湿惯性带来的延迟、衰减与记忆。</div>
      </div>
      <div class="pipe-arrow">→</div>
      <div class="pipe-stage">
        <span class="pipe-tag">L3 · 风险对齐</span>
        <div class="pipe-name">风险对齐训练</div>
        <div class="pipe-io">在 MSE 目标上引入阈值加权风险项 twCRPS</div>
        <div class="pipe-desc">让模型直接优化"超阈 + 持续"的文保损伤判据，而不是平均误差。</div>
      </div>
    </div>
  </Panel>
</template>
