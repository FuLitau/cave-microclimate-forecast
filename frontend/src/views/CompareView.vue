<script setup lang="ts">
/**
 * 效果对照 —— 回答评委最关心的一个问题：用了这个算法，到底哪里不一样。
 *
 * 口径纪律：
 *  · 端到端口径（真实预报驱动）与可部署性上界口径（真实未来再分析替代预报）分栏呈现；
 *  · 46.3 h 提前量必须带「事件前 72 h 窗口内滚动预报口径」；
 *  · twCRPS 的说法是「在 MSE 目标上引入阈值加权风险项」，不是「替代 MSE」；
 *  · C 档（算子导出内生权重）经 18 格消融未见稳定增益，最终采用固定阈值形式；
 *  · GBDT 非线性读出并非全面更优，最终采用线性闭式解（过程性记录）。
 */
import { computed } from 'vue'
import EChart from '../components/EChart.vue'
import StatCard from '../components/StatCard.vue'
import SourceNote from '../components/SourceNote.vue'
import { AZURITE, baseAxis, baseLegend, baseTooltip, CINNABAR, GOLD, INK_2, INK_3, INK_4, MALACHITE, OCHRE, VIOLET } from '../lib/charts'
import { ablation } from '../data/ablation'
import { baselines, duration, events62, leadtime, models24, readoutCompare } from '../data/compare'

const SEG_LABEL: Record<string, string> = { val: '验证段', test: '测试段' }
const CELLS = ['val', 'test'].flatMap((s) => [24, 48, 72].map((h) => ({ s, h })))

const cellLabel = (c: { s: string; h: number }) => `${SEG_LABEL[c.s]} · ${c.h} h`

/** 62% 阈值、A/B/C 三档在六个格上的 F1 与 AUC */
const grid62 = computed(() =>
  CELLS.map((c) => {
    const pick = (m: string) => ablation.find((r) => r.segment === c.s && r.h === c.h && r.thr === '62' && r.mode === m)
    return { label: cellLabel(c), A: pick('A'), B: pick('B'), C: pick('C') }
  }),
)

/** A → B 的端到端提升（测试段 24 h / 62% / 62% 阈值） */
const head = computed(() => {
  const a = ablation.find((r) => r.segment === 'test' && r.h === 24 && r.thr === '62' && r.mode === 'A')!
  const b = ablation.find((r) => r.segment === 'test' && r.h === 24 && r.thr === '62' && r.mode === 'B')!
  return { a, b }
})

/** 「用与不用」六格增益：全是 62% 口径 */
const gains = computed(() =>
  CELLS.map((c) => {
    const a = ablation.find((r) => r.segment === c.s && r.h === c.h && r.thr === '62' && r.mode === 'A')!
    const b = ablation.find((r) => r.segment === c.s && r.h === c.h && r.thr === '62' && r.mode === 'B')!
    return { label: cellLabel(c), dF1: b.F1 - a.F1, dAUC: b.AUC - a.AUC, dR2: b.R2 - a.R2, dPtR2: b.ptR2 - a.ptR2, a, b }
  }),
)

const f1Option = computed(() => ({
  grid: { left: 44, right: 18, top: 44, bottom: 30 },
  legend: { ...baseLegend, data: ['A · 纯 MSE', 'B · + twCRPS', 'C · + 算子内生权重'] },
  tooltip: { ...baseTooltip, trigger: 'axis', axisPointer: { type: 'shadow' } },
  xAxis: { type: 'category', data: grid62.value.map((g) => g.label), ...baseAxis },
  yAxis: { type: 'value', name: '超阈 F1', nameTextStyle: { color: INK_4, fontSize: 11 }, min: 0, ...baseAxis },
  series: [
    { name: 'A · 纯 MSE', type: 'bar', data: grid62.value.map((g) => g.A?.F1 ?? 0), itemStyle: { color: INK_3, borderRadius: [3, 3, 0, 0] }, barMaxWidth: 16 },
    { name: 'B · + twCRPS', type: 'bar', data: grid62.value.map((g) => g.B?.F1 ?? 0), itemStyle: { color: AZURITE, borderRadius: [3, 3, 0, 0] }, barMaxWidth: 16 },
    { name: 'C · + 算子内生权重', type: 'bar', data: grid62.value.map((g) => g.C?.F1 ?? 0), itemStyle: { color: INK_4, borderRadius: [3, 3, 0, 0] }, barMaxWidth: 16 },
  ],
}))

const aucOption = computed(() => ({
  grid: { left: 50, right: 18, top: 44, bottom: 30 },
  legend: { ...baseLegend, data: ['A · 纯 MSE', 'B · + twCRPS', 'C · + 算子内生权重'] },
  tooltip: { ...baseTooltip, trigger: 'axis', axisPointer: { type: 'shadow' } },
  xAxis: { type: 'category', data: grid62.value.map((g) => g.label), ...baseAxis },
  yAxis: { type: 'value', name: 'AUC', nameTextStyle: { color: INK_4, fontSize: 11 }, min: 0.7, max: 1, ...baseAxis },
  series: [
    { name: 'A · 纯 MSE', type: 'bar', data: grid62.value.map((g) => g.A?.AUC ?? 0), itemStyle: { color: INK_3, borderRadius: [3, 3, 0, 0] }, barMaxWidth: 16 },
    { name: 'B · + twCRPS', type: 'bar', data: grid62.value.map((g) => g.B?.AUC ?? 0), itemStyle: { color: MALACHITE, borderRadius: [3, 3, 0, 0] }, barMaxWidth: 16 },
    { name: 'C · + 算子内生权重', type: 'bar', data: grid62.value.map((g) => g.C?.AUC ?? 0), itemStyle: { color: INK_4, borderRadius: [3, 3, 0, 0] }, barMaxWidth: 16 },
  ],
}))

/** 提前量：检出率与平均首次预警提前小时 */
const leadOption = computed(() => ({
  grid: { left: 56, right: 54, top: 44, bottom: 30 },
  legend: { ...baseLegend, data: ['超阈事件检出率', '平均首次预警提前（h）'] },
  tooltip: { ...baseTooltip, trigger: 'axis', axisPointer: { type: 'shadow' } },
  xAxis: { type: 'category', data: leadtime.map((l) => l.model.replace(/\(.*?\)/g, '')), ...baseAxis },
  yAxis: [
    { type: 'value', name: '检出率', min: 0, max: 0.5, nameTextStyle: { color: INK_4, fontSize: 11 }, ...baseAxis },
    { type: 'value', name: '提前 h', min: 0, max: 60, nameTextStyle: { color: INK_4, fontSize: 11 }, ...baseAxis, splitLine: { show: false } },
  ],
  series: [
    { name: '超阈事件检出率', type: 'bar', data: leadtime.map((l) => l.detect), itemStyle: { color: AZURITE, borderRadius: [3, 3, 0, 0] }, barMaxWidth: 34 },
    { name: '平均首次预警提前（h）', type: 'line', yAxisIndex: 1, data: leadtime.map((l) => l.lead), symbolSize: 7, lineStyle: { color: GOLD, width: 2 }, itemStyle: { color: GOLD } },
  ],
}))

/**
 * 基线条形图只画「量纲可比」的行。
 * 「FirstOrderTransfer-递归推演」的 R² = −3.34e+22，一旦入图坐标轴会被拉到 ±1e22，
 * 其余 8 个 R²∈[−0.02, 0.95] 的模型全部被压成贴着 0 的细线 —— 图比不画还糟。
 * 该行仍完整保留在下方表格里（含发散原因说明），这里只在图注里点名。
 */
const basePlot = computed(() => baselines.filter((b) => Math.abs(b.R2) < 100))
const baseExcluded = computed(() => baselines.filter((b) => Math.abs(b.R2) >= 100))

const baseOption = computed(() => ({
  grid: { left: 176, right: 46, top: 16, bottom: 26 },
  tooltip: { ...baseTooltip, trigger: 'axis', axisPointer: { type: 'shadow' } },
  xAxis: { type: 'value', name: 'R²', min: 0, max: 1, nameTextStyle: { color: INK_4, fontSize: 11 }, ...baseAxis },
  yAxis: { type: 'category', data: basePlot.value.map((b) => b.model.replace(/\(.*?\)/g, '')).reverse(), ...baseAxis, axisLabel: { color: INK_2, fontSize: 11 } },
  series: [
    {
      type: 'bar',
      data: basePlot.value
        .map((b) => ({
          value: b.R2,
          itemStyle: {
            color: b.group === '本作品与消融' ? AZURITE : INK_4,
            borderRadius: [0, 3, 3, 0],
          },
        }))
        .reverse(),
      barMaxWidth: 15,
      label: { show: true, position: 'right', color: INK_3, fontSize: 10.5, formatter: (p: any) => p.value.toFixed(3) },
      markLine: {
        silent: true,
        symbol: 'none',
        label: { formatter: '持续性参照 0.953', color: INK_4, fontSize: 10 },
        lineStyle: { color: GOLD, type: 'dashed', width: 1 },
        data: [{ xAxis: 0.953 }],
      },
    },
  ],
}))

const rcOption = computed(() => ({
  grid: { left: 44, right: 18, top: 44, bottom: 30 },
  legend: { ...baseLegend, data: ['线性岭回归', 'GBDT 非线性'] },
  tooltip: { ...baseTooltip, trigger: 'axis', valueFormatter: (v: any) => (typeof v === 'number' ? v.toFixed(4) : '—') },
  xAxis: { type: 'category', data: ['24 h', '48 h', '72 h'], ...baseAxis },
  yAxis: { type: 'value', min: 0, name: 'F1 @ 62%', nameTextStyle: { color: INK_4, fontSize: 11 }, ...baseAxis },
  series: [
    {
      name: '线性岭回归',
      type: 'bar',
      barMaxWidth: 26,
      itemStyle: { color: INK_3, borderRadius: [3, 3, 0, 0] },
      data: [24, 48, 72].map((h) => readoutCompare.find((r) => r.h === h && r.readout.includes('线性'))!.f162),
      label: { show: true, position: 'top', color: INK_3, fontSize: 10.5, formatter: (p: any) => p.value.toFixed(4) },
    },
    {
      name: 'GBDT 非线性',
      type: 'bar',
      barMaxWidth: 26,
      itemStyle: { color: VIOLET, borderRadius: [3, 3, 0, 0] },
      data: [24, 48, 72].map((h) => readoutCompare.find((r) => r.h === h && r.readout.includes('GBDT'))!.f162),
      label: { show: true, position: 'top', color: VIOLET, fontSize: 10.5, formatter: (p: any) => p.value.toFixed(4) },
    },
  ],
}))

const dots = (n: number) => Array.from({ length: events62[0].onset }, (_, i) => i < n)
</script>

<template>
  <section class="view-head">
    <h1>效果对照</h1>
    <p>
      同一批特征、同一批驱动数据，只改目标函数与读出方式。「用与不用本模型」的差别，全部落在
      超阈判对率、AUC、事件检出与提前量四类指标上。
    </p>
  </section>

  <!-- 头条：A → B ------------------------------------------------------ -->
  <div class="grid g-4">
    <StatCard
      label="超阈 F1"
      :value="`${head.a.F1.toFixed(3)} → ${head.b.F1.toFixed(3)}`"
      sub="测试段 · 24 h · 62% 阈值"
      hint="在 MSE 目标上引入阈值加权风险项"
      accent="azurite"
      scope="end2end"
    />
    <StatCard
      label="AUC"
      :value="`${head.a.AUC.toFixed(3)} → ${head.b.AUC.toFixed(3)}`"
      sub="同口径六格全胜"
      hint="验证 / 测试 × 24 / 48 / 72 h"
      accent="malachite"
      scope="end2end"
    />
    <StatCard
      label="超阈事件检出率"
      :value="`${(leadtime.find((l) => l.model.includes('本作品'))!.detect * 100).toFixed(1)}%`"
      :sub="`${leadtime.find((l) => l.model.includes('本作品'))!.warned} / ${leadtime.find((l) => l.model.includes('本作品'))!.onset} 次起报事件`"
      hint="以真实未来再分析替代预报，属可部署性上界口径"
      accent="ochre"
      scope="upper"
    />
    <StatCard
      label="平均首次预警提前"
      :value="`${leadtime.find((l) => l.model.includes('本作品'))!.lead.toFixed(1)} h`"
      sub="事件前 72 h 窗口内滚动预报口径"
      hint="连续滚动预报信号的累计提前量，非单次预报直接预见"
      accent="gold"
      scope="upper"
    />
  </div>

  <SourceNote kind="info">
    前两张卡片是<b>端到端</b>口径：驱动来自真实预报，评委看到的就是系统实际能达到的水平。
    后两张卡片是<b>可部署性上界</b>口径：把真实未来再分析当作完美预报喂进模型，衡量的是算法本身的上限，
    不代表端到端性能。两种口径在材料中始终分栏出现。
  </SourceNote>

  <!-- A/B/C 消融 ------------------------------------------------------- -->
  <div class="grid g-2">
    <div class="card">
      <div class="card-head">
        <div>
          <div class="card-title">目标函数消融 · 超阈 F1（62% 阈值）</div>
          <div class="card-sub">六个格 = 验证段 / 测试段 × 24 / 48 / 72 h，阈值固定 62%</div>
        </div>
      </div>
      <div class="card-body">
        <EChart :option="f1Option" height="250px" />
      </div>
    </div>
    <div class="card">
      <div class="card-head">
        <div>
          <div class="card-title">目标函数消融 · AUC（62% 阈值）</div>
          <div class="card-sub">AUC 对类别不平衡不敏感，是更稳的比较口径</div>
        </div>
      </div>
      <div class="card-body">
        <EChart :option="aucOption" height="250px" />
      </div>
    </div>
  </div>

  <SourceNote kind="info">
    「算子导出内生权重」的强化版（C 档）经 18 格消融未见稳定增益，最终采用固定阈值权重形式；
    完整对照见 <span class="src">code/results/exp03_verdict.csv</span>。
  </SourceNote>

  <!-- 口径分歧 --------------------------------------------------------- -->
  <div class="card">
    <div class="card-head">
      <div>
        <div class="card-title">指标说明：R² 与 F1 / AUC 变化方向不同</div>
        <div class="card-sub">同样比较 A → B（加 twCRPS），六个格上四项指标的变化</div>
      </div>
    </div>
    <div class="card-body tight">
      <table class="tbl">
        <thead>
          <tr>
            <th>格</th>
            <th class="r">ΔAUC</th>
            <th class="r">ΔF1</th>
            <th class="r">ΔR²（点预报口径）</th>
            <th class="r">ΔR²（部署读出口径）</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="g in gains" :key="g.label">
            <td class="strong">{{ g.label }}</td>
            <td class="r" :style="{ color: g.dAUC > 0 ? MALACHITE : CINNABAR }">+{{ g.dAUC.toFixed(4) }}</td>
            <td class="r" :style="{ color: g.dF1 > 0 ? MALACHITE : CINNABAR }">+{{ g.dF1.toFixed(4) }}</td>
            <td class="r" :style="{ color: g.dPtR2 > 0 ? MALACHITE : CINNABAR }">{{ g.dPtR2 > 0 ? '+' : '' }}{{ g.dPtR2.toFixed(4) }}</td>
            <td class="r" :style="{ color: g.dR2 > 0 ? MALACHITE : CINNABAR }">{{ g.dR2.toFixed(4) }}</td>
          </tr>
        </tbody>
      </table>
      <SourceNote kind="alert">
        <b>不遮掩地说</b>：加上阈值加权项之后，<b>点预报的 R² 六个格全部变好</b>（+0.044 ~ +0.070），
        但<b>部署读出的 R² 六个格全部变差</b>（−0.24 ~ −1.01）；与此同时，与判定直接相关的
        <b>AUC 与 F1 六个格全部变好</b>。
        机制是清楚的：阈值加权项把读出的重心从"平均意义上贴合"挪到"在阈值附近判对"，
        <b>用均方精度换取了判定精度</b>。所以本项目的成果只能表述为「超阈判定能力提升」，
        不能表述为「预报精度全面提升」。这也是我们在材料中始终区分两套 R² 口径的原因。
        两套口径的原始值同表列在 <span class="src">code/results/exp03_abc_ablation.csv</span> 的
        <span class="src">pt_R2</span> 与 <span class="src">R2</span> 两列。
      </SourceNote>
    </div>
  </div>

  <!-- 事件命中 --------------------------------------------------------- -->
  <div class="card">
    <div class="card-head">
      <div>
        <div class="card-title">超阈事件命中点阵 · 24 h / 62% 档</div>
        <div class="card-sub">共 {{ events62[0].onset }} 次真实超阈起报事件；实心格 = 该事件在提前窗口内被预警到</div>
      </div>
      <span class="badge info">可部署性上界口径</span>
    </div>
    <div class="card-body">
      <div v-for="e in events62" :key="e.name" style="margin-bottom: 14px">
        <div class="row between" style="margin-bottom: 6px">
          <div class="row">
            <span class="strong" style="font-weight: 600">{{ e.name }}</span>
            <span class="src">{{ e.note }}</span>
          </div>
          <span class="badge" :class="e.hit ? 'info' : 'alert'">
            命中 {{ e.hit }} / {{ e.onset }}（{{ ((e.hit / e.onset) * 100).toFixed(1) }}%）
          </span>
        </div>
        <div class="dotgrid">
          <i v-for="(h, i) in dots(e.hit)" :key="i" class="d" :class="h ? 'hit' : 'miss'" />
        </div>
      </div>
      <SourceNote kind="warn">
        即使在上界口径下，本作品也只检出 <b>{{ ((events62[0].hit / events62[0].onset) * 100).toFixed(1) }}%</b> 的超阈事件。
        三个演示窗口的漏报与此一致：模型的偏高湿风险识别能力确有不足。
        一阶传递的递归推演形式因传递算子极点 &gt; 1 而数值饱和，<b>从未发出过任何预警</b>。
        出处 <span class="src">code/results/derisk02_leadtime.csv</span>。
      </SourceNote>

      <div class="hr" />

      <div class="eyebrow" style="margin-bottom: 8px">三种预警形式的分类指标（24 h / 62% 档）</div>
      <table class="tbl">
        <thead>
          <tr>
            <th>形式</th><th class="r">AUC</th><th class="r">F1</th>
            <th class="r">召回率</th><th class="r">精确率</th><th class="r">基准发生率</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="m in models24" :key="m.model">
            <td class="strong">{{ m.model.replace(/\(.*?\)/g, '') }}</td>
            <td class="r">{{ m.AUC.toFixed(4) }}</td>
            <td class="r">{{ m.F1.toFixed(4) }}</td>
            <td class="r">{{ m.recall.toFixed(4) }}</td>
            <td class="r">{{ m.precision.toFixed(4) }}</td>
            <td class="r dimmer">{{ m.baseRate.toFixed(4) }}</td>
          </tr>
        </tbody>
      </table>
      <SourceNote>
        AUC 看起来很高而 F1 只有 0.1 量级，原因是<b>超阈事件本身稀疏</b>（基准发生率见最后一列）：
        即便排序能力不错，按固定切点二值化后仍会大量漏报或误报。这正是本项目用<b>分级风险读出</b>
        而不是单点二值判断来交付的原因。
      </SourceNote>
    </div>
  </div>

  <div class="grid g-2">
    <div class="card">
      <div class="card-head">
        <div>
          <div class="card-title">预警提前量</div>
          <div class="card-sub">检出率（柱）与平均首次预警提前小时（线）</div>
        </div>
      </div>
      <div class="card-body">
        <EChart :option="leadOption" height="250px" />
        <SourceNote kind="warn">
          <b>提前量的口径</b>：这是「事件前 72 h 窗口内滚动预报」的累计提前量，即连续发出预警时
          「首次预警比事件早多少小时」，不是单次 24 h 预报能直接预见 46 小时后的情况。
          出处 <span class="src">code/results/derisk02_leadtime.csv</span>。
        </SourceNote>
      </div>
    </div>

    <div class="card">
      <div class="card-head">
        <div>
          <div class="card-title">阈值外推时长预报误差</div>
          <div class="card-sub">超过阈值后能维持多久，直接决定限流方案要开多久</div>
        </div>
      </div>
      <div class="card-body tight">
        <table class="tbl">
          <thead>
            <tr><th>模型</th><th>阈值</th><th class="r">MAE (h)</th><th class="r">Bias (h)</th><th class="r">RMSE (h)</th></tr>
          </thead>
          <tbody>
            <tr v-for="d in duration" :key="`${d.model}-${d.threshold}`">
              <td>{{ d.model.replace(/\(.*?\)/g, '') }}</td>
              <td class="dimmer">{{ d.threshold }}</td>
              <td class="r">{{ d.maeH.toFixed(2) }}</td>
              <td class="r">{{ d.biasH.toFixed(2) }}</td>
              <td class="r">{{ d.rmseH.toFixed(2) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- 9 基线 ----------------------------------------------------------- -->
  <div class="card">
    <div class="card-head">
      <div>
        <div class="card-title">九个对照模型的逐行说明</div>
        <div class="card-sub">同一划分、同一评价脚本；R² 为窟内 RH 预报的决定系数</div>
      </div>
    </div>
    <div class="card-body">
      <EChart :option="baseOption" height="270px" />
      <SourceNote kind="info">
        图中未画
        <template v-for="(b, i) in baseExcluded" :key="b.model">
          <b>{{ b.model.replace(/\(.*?\)/g, '') }}</b><span v-if="i < baseExcluded.length - 1">、</span>
        </template>
        ——它的 R² = −3.34×10²²，入图会把坐标轴拉到 ±10²² 量级，其余 8 个模型全部被压成贴 0 的细线。
        该行仍完整保留在下表中，发散原因见其「在实验里的角色」一列。
      </SourceNote>
      <div class="hr" />
      <table class="tbl">
        <thead>
          <tr>
            <th>模型</th><th>类别</th><th class="r">RMSE</th><th class="r">R²</th>
            <th class="r">特征数</th><th class="r">拟合秒</th><th>它在实验里的角色</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="b in baselines" :key="b.model" :class="{ hl: b.group === '本作品与消融' && b.model.includes('本作品') }">
            <td class="strong">{{ b.model.replace(/\(.*?\)/g, '') }}</td>
            <td>
              <span class="badge" :class="b.group === '本作品与消融' ? 'info' : b.group === '一阶传递基线' ? 'plain' : 'plain'">
                {{ b.group }}
              </span>
            </td>
            <td class="r">{{ Math.abs(b.RMSE) > 1e6 ? b.RMSE.toExponential(2) : b.RMSE.toFixed(3) }}</td>
            <td class="r">{{ b.R2.toFixed(4) }}</td>
            <td class="r">{{ b.nFeatures ?? '—' }}</td>
            <td class="r">{{ b.fitSeconds?.toFixed(2) ?? '—' }}</td>
            <td class="note-cell">{{ b.note }}</td>
          </tr>
        </tbody>
      </table>
      <SourceNote kind="warn">
        <b>不要把这一列读成「本作品最好」</b>：持续性是所有模型的下限参照，它 R² 最高只是因为它直接把当前窟内湿度外推，
        不含任何室外驱动信息。本表的目的是刻画「室外驱动 → 窟内」这一段可学习部分，
        本作品在这一段上把 R² 从一阶传递基线的 0.226 提升到 0.876。
        递归推演行因传递算子极点接近 1 而数值发散，不可用。
        出处 <span class="src">code/results/derisk01_model_comparison.csv</span>。
      </SourceNote>
    </div>
  </div>

  <!-- 非线性读出 ------------------------------------------------------- -->
  <div class="card">
    <div class="card-head">
      <div>
        <div class="card-title">读出层换成非线性模型会怎样</div>
        <div class="card-sub">同一批 258 维特征，线性岭回归 vs 梯度提升树</div>
      </div>
      <span class="badge watch"><i class="dot" />并非全面更优</span>
    </div>
    <div class="card-body">
      <EChart :option="rcOption" height="240px" />
      <div class="hr" />
      <table class="tbl">
        <thead>
          <tr>
            <th class="r">时效</th><th>读出</th><th class="r">RMSE</th><th class="r">峰值捕捉比</th>
            <th class="r">AUC 62%</th><th class="r">F1 62%</th><th class="r">AUC 75%</th><th class="r">F1 75%</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in readoutCompare" :key="`${r.h}-${r.readout}`">
            <td class="r">{{ r.h }} h</td>
            <td>{{ r.readout }}</td>
            <td class="r">{{ r.RMSE.toFixed(3) }}</td>
            <td class="r">{{ r.peakRatio.toFixed(4) }}</td>
            <td class="r">{{ r.auc62.toFixed(4) }}</td>
            <td class="r" :style="{ color: r.readout.includes('GBDT') && r.f162 < 0.0998 ? CINNABAR : undefined }">{{ r.f162.toFixed(4) }}</td>
            <td class="r">{{ r.auc75.toFixed(4) }}</td>
            <td class="r">{{ r.f175.toFixed(4) }}</td>
          </tr>
        </tbody>
      </table>
      <SourceNote kind="alert">
        非线性读出<b>把 75% 档从完全不可用（F1 = 0）救到了 0.019，AUC 也普遍高 3–12 个百分点</b>；
        但在 24 h / 62% 这一格，它的 F1 = 0.085 <b>反而低于</b>线性岭回归的 0.100，
        48 h / 62% 与 72 h / 62% 也略低。因此结论只能是「非线性读出在极端阈值档更有价值」，
        不能说「全面更优」。出处 <span class="src">code/results/derisk03_readout_compare.csv</span>。
      </SourceNote>
    </div>
  </div>

  <SourceNote>
    本页全部数字来自 <span class="src">code/results/exp03_abc_ablation.csv、exp03_abc_ablation_val.csv、exp03_verdict.csv、
    derisk01_model_comparison.csv、derisk01_duration.csv、derisk02_events.csv、derisk02_leadtime.csv、derisk03_readout_compare.csv</span>，
    由 <span class="src">tools/build_frontend_data.py</span> 自动生成，无手工填写。
  </SourceNote>
</template>
