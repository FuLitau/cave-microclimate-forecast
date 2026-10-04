<script setup lang="ts">
/**
 * 方法说明 —— 把「室外预报 → 窟内风险」这条链拆开给评委看：
 * 三层结构、258 维特征的来源、读出的可解释性、算子谱模态、以及每一步的消融代价。
 */
import { computed } from 'vue'
import EChart from '../components/EChart.vue'
import SourceNote from '../components/SourceNote.vue'
import { AZURITE, baseAxis, baseLegend, baseTooltip, CINNABAR, GOLD, INK_2, INK_3, INK_4, MALACHITE, OCHRE, VIOLET } from '../lib/charts'
import { layers, readoutWeights, spectrum } from '../data/method'
import { baselines } from '../data/compare'

const FAMILY_COLOR: Record<string, string> = {
  水汽通量: MALACHITE,
  慢变背景: GOLD,
  快变延迟: AZURITE,
  瞬时外场: OCHRE,
  其他: INK_3,
}

/** 特征族权重合计（按 |权重| 归一） */
const familyTotals = computed(() => {
  const acc: Record<string, number> = {}
  for (const r of readoutWeights) acc[r.family] = (acc[r.family] ?? 0) + r.absWeight
  const total = Object.values(acc).reduce((a, b) => a + b, 0) || 1
  return Object.entries(acc)
    .map(([family, w]) => ({ family, pct: (w / total) * 100, color: FAMILY_COLOR[family] ?? INK_3 }))
    .sort((a, b) => b.pct - a.pct)
})

const weightOption = computed(() => ({
  grid: { left: 118, right: 56, top: 14, bottom: 26 },
  tooltip: {
    ...baseTooltip,
    trigger: 'axis',
    axisPointer: { type: 'shadow' },
    formatter: (ps: any) => {
      const p = ps[0]
      const row = readoutWeights.find((r) => r.feature === p.name)!
      return `<b>${row.feature}</b><br/>族：${row.family}<br/>岭回归权重 ${row.weight.toFixed(4)}（|·| 排名）<br/><span style="color:#b3a992">${row.desc}</span>`
    },
  },
  xAxis: { type: 'value', name: '标准化特征上的岭回归权重', nameTextStyle: { color: INK_4, fontSize: 10.5 }, ...baseAxis },
  yAxis: {
    type: 'category',
    data: readoutWeights.map((r) => r.feature).reverse(),
    ...baseAxis,
    axisLabel: { color: INK_2, fontSize: 11, fontFamily: 'monospace' },
  },
  series: [
    {
      type: 'bar',
      barMaxWidth: 13,
      data: readoutWeights
        .map((r) => ({
          value: r.weight,
          itemStyle: { color: FAMILY_COLOR[r.family] ?? INK_3, borderRadius: r.weight >= 0 ? [0, 3, 3, 0] : [3, 0, 0, 3] },
        }))
        .reverse(),
      label: {
        show: true,
        position: 'right',
        color: INK_3,
        fontSize: 10.5,
        formatter: (p: any) => p.value.toFixed(2),
      },
    },
  ],
}))

/**
 * 谱的可视化选择：不画 |λ|。
 * 10 个模态的 |λ| 全在 0.9992~1.0000 之间，画柱状图会得到十根一样高的柱子，
 * 看不出任何信息。真正有信息量的是「衰减时间 τ 有多长」——它直接回答
 * 「这个模态能不能撑过 72 h 的预报窗」。所以这里画 τ（对数轴），并标注 72 h 窗长做参照。
 */
const distinctSpectrum = computed(() => {
  const seen = new Set<number>()
  return spectrum.filter((m) => {
    const key = Math.round(m.periodHours)
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
})

const specLabel = (m: { periodHours: number; periodDays: number }) =>
  m.periodDays < 2 ? `${m.periodHours.toFixed(0)} h 周期` : `${m.periodDays.toFixed(1)} d 周期`

const spectrumOption = computed(() => ({
  grid: { left: 118, right: 78, top: 16, bottom: 44 },
  tooltip: {
    ...baseTooltip,
    trigger: 'axis',
    axisPointer: { type: 'shadow' },
    formatter: (ps: any) => {
      const m = distinctSpectrum.value[ps[0].dataIndex]
      return `<b>${specLabel(m)}</b><br/>衰减时间 τ = ${m.tauHours.toFixed(0)} h（${(m.tauHours / 24).toFixed(0)} 天）<br/>离散特征值模 |λ| = ${m.absLambda.toFixed(5)}<br/>（共轭成对出现，谱中占 2 个模态）`
    },
  },
  xAxis: {
    type: 'log',
    name: '衰减时间 τ / 小时（对数轴）',
    nameLocation: 'middle',
    nameGap: 30,
    nameTextStyle: { color: INK_4, fontSize: 10.5 },
    // 下限必须低于 72 h，否则「预报窗 72 h」参考线会被裁掉、看不出模态是否撑得过预报窗。
    min: 50,
    max: 60000,
    ...baseAxis,
    axisLabel: { ...baseAxis.axisLabel, formatter: (v: number) => (v >= 1000 ? `${v / 1000}k` : String(v)) },
  },
  yAxis: {
    type: 'category',
    data: distinctSpectrum.value.map((m) => specLabel(m)).reverse(),
    ...baseAxis,
    axisLabel: { color: INK_2, fontSize: 11 },
  },
  series: [
    {
      type: 'bar',
      barMaxWidth: 22,
      data: distinctSpectrum.value
        .map((m) => ({
          value: m.tauHours,
          itemStyle: {
            color: m.periodHours >= 20 && m.periodHours <= 26 ? AZURITE : m.periodDays > 300 ? GOLD : INK_3,
            borderRadius: [0, 3, 3, 0],
          },
        }))
        .reverse(),
      label: {
        show: true,
        position: 'right',
        color: INK_3,
        fontSize: 10.5,
        formatter: (p: any) => `${Math.round(p.value).toLocaleString()} h`,
      },
      markLine: {
        silent: true,
        symbol: 'none',
        label: { formatter: '预报窗 72 h', color: INK_4, fontSize: 10, position: 'insideEndTop' },
        lineStyle: { color: CINNABAR, type: 'dashed', width: 1 },
        data: [{ xAxis: 72 }],
      },
    },
  ],
}))

/** 特征族消融：以 Operator-Full 的 R² 为基准 */
const full = computed(() => baselines.find((b) => b.model.includes('本作品'))!)
const ablations = computed(() =>
  baselines
    .filter((b) => b.model.startsWith('Ablation'))
    .map((b) => ({ ...b, drop: full.value.R2 - b.R2, short: b.model.replace('Ablation-', '') }))
    .sort((a, b) => b.drop - a.drop),
)

const FEATURE_MIX = [
  { name: '快变延迟', n: 240, desc: '5 个驱动 × 48 小时回溯。刻画窟体热惯性造成的衰减与滞后。', color: AZURITE },
  { name: '慢变滑动均值', n: 12, desc: '5 个驱动的 24/72/168/720/2160/8760 小时滑动均值（RH2M 少一档）。提供季节性背景位。', color: GOLD },
  { name: 'Magnus 比值', n: 6, desc: '由 T、RH、P 导出的饱和水汽压比与露点差等物理量，把外场从"数值"变成"物理状态"。', color: MALACHITE },
]
</script>

<template>
  <section class="view-head">
    <h1>方法说明</h1>
    <p>
      本项目的算法主张只有一句话：<b>把文物保护的业务判据写进损失函数，让预报直接为「会不会越过阈值」服务</b>。
      下面把这条链拆成三层，并逐层给出可解释性证据与消融代价。
    </p>
  </section>

  <!-- 三层链路 --------------------------------------------------------- -->
  <div class="grid g-3">
    <div v-for="l in layers" :key="l.id" class="card" style="margin-top: 0">
      <div class="card-body">
        <div class="row between" style="margin-bottom: 8px">
          <span class="badge info">{{ l.id }}</span>
          <span class="src">{{ l.io }}</span>
        </div>
        <div class="card-title" style="font-size: 15px">{{ l.title }}</div>
        <div class="card-sub" style="margin-bottom: 8px">{{ l.subtitle }}</div>
        <p class="note" style="margin-top: 0">{{ l.detail }}</p>
      </div>
    </div>
  </div>

  <!-- 目标函数 --------------------------------------------------------- -->
  <div class="grid g-2">
    <div class="card">
      <div class="card-head">
        <div>
          <div class="card-title">L3 · 阈值加权风险目标（本作品的核心改动）</div>
          <div class="card-sub">twCRPS = threshold-weighted Continuous Ranked Probability Score</div>
        </div>
        <span class="badge ok">模型级创新</span>
      </div>
      <div class="card-body">
        <div class="callout info" style="font-family: var(--mono); font-size: 12px; line-height: 2">
          twCRPS(F, y) = ∫ w(p) · (F(p) − 1{{ '{' }}y ≤ p{{ '}' }})² dp<br />
          w(p) = 1 + λ · Σ<sub>k</sub> 1{{ '{' }}p ≥ τ<sub>k</sub>{{ '}' }}， τ ∈ {{ '{' }}62%, 67%, 75%{{ '}' }}
        </div>
        <p class="note">
          常规做法在 <b>MSE 目标</b>上训练，等价于假设「所有误差一样贵」。但文物保护不是这样：
          窟内 RH 从 55% 漂到 60% 无所谓，从 60% 冲到 64% 就可能开始潮解。twCRPS 用一个权重函数
          <b>把损失的质量集中到阈值之上</b>，于是训练过程直接惩罚「在阈值附近判错」。
        </p>
        <p class="note warn">
          <b>准确的表述</b>：这是在 MSE 目标上<b>引入</b>阈值加权风险项，不是「用 twCRPS 替代 MSE」。
          消融表里 A 档（纯 MSE）与 B 档（MSE + twCRPS）的差别就来自这一项。
          实现见 <span class="src">code/src/losses/twcrps.py</span>，其中 <span class="src">twcrps_integral()</span>
          是按定义数值积分的参考实现，用于校验向量化版本的数值正确性。
        </p>
      </div>
    </div>

    <div class="card">
      <div class="card-head">
        <div>
          <div class="card-title">L1 · 数据源与真实性约束</div>
          <div class="card-sub">全部为公开数据，无任何私有或不可复现来源</div>
        </div>
      </div>
      <div class="card-body tight">
        <table class="tbl">
          <thead><tr><th>数据</th><th>用途</th><th class="r">规模</th></tr></thead>
          <tbody>
            <tr><td class="strong">NASA POWER 逐小时</td><td>室外气象驱动</td><td class="r">219,144 h · 零缺测</td></tr>
            <tr><td class="strong">NOAA ISD 敦煌站报文</td><td>驱动真实性对照</td><td class="r">23,915 h 配对</td></tr>
            <tr><td class="strong">ICCP 洞穴实测</td><td>跨窟外部验证</td><td class="r">12 洞 · 逐小时</td></tr>
            <tr><td class="strong">公开文献参数</td><td>窟体物理模型标定</td><td class="r">热扩散率 / 换气次数 / 盐害阈值</td></tr>
          </tbody>
        </table>
        <p class="note warn">
          数据链的时间范围：POWER 2001-01-01 – 2025-12-31；ISD 敦煌站 2015-01-01 – 2023-04-28
          （该站此后停止报文，这是数据源本身的限制，不是我们少下了）。
        </p>
      </div>
    </div>
  </div>

  <!-- 特征构成 --------------------------------------------------------- -->
  <div class="card">
    <div class="card-head">
      <div>
        <div class="card-title">L2 · 258 维因果特征的构成</div>
        <div class="card-sub">全部特征严格只用当前时刻及之前的信息；训练/验证/测试按时间切分，不做随机划分</div>
      </div>
      <span class="badge">特征级创新</span>
    </div>
    <div class="card-body">
      <div class="grid g-3">
        <div v-for="f in FEATURE_MIX" :key="f.name" class="callout" :style="{ borderLeftColor: f.color }">
          <div class="row between">
            <b>{{ f.name }}</b>
            <span class="num strong">{{ f.n }} 维</span>
          </div>
          <div class="dimmer" style="margin-top: 4px">{{ f.desc }}</div>
        </div>
      </div>
      <p class="note info">
        读出层是一个<b>岭回归</b>（β 只惩罚斜率、不惩罚截距，且矩阵按样本数归一化）。
        这看起来"简单"，但它是刻意的：参数量 258，CPU 上 5.63 秒拟合完成，不需要 GPU。
        真正的创新不在读出层有多深，而在<b>特征怎么造</b>与<b>目标函数怎么定</b>。
      </p>
    </div>
  </div>

  <div class="grid g-2">
    <div class="card">
      <div class="card-head">
        <div>
          <div class="card-title">读出权重 · 模型在"看"什么</div>
          <div class="card-sub">|权重| 最大的 18 个特征，按特征族着色</div>
        </div>
      </div>
      <div class="card-body">
        <EChart :option="weightOption" height="380px" />
        <div class="legend">
          <span v-for="f in familyTotals" :key="f.family" class="legend-item">
            <i class="legend-swatch box" :style="{ background: f.color }" />{{ f.family }} · {{ f.pct.toFixed(1) }}%
          </span>
        </div>
        <SourceNote>
          权重是<b>标准化特征上的岭回归系数</b>，只说明「哪个特征对读出贡献大」，<b>不是因果效应</b>。
          上表占比按 |权重| 在本页 18 个特征内归一，不等于全模型的特征族重要性。
          完整的 40 项权重见 <span class="src">code/results/derisk02_readout.csv</span>。
        </SourceNote>
      </div>
    </div>

    <div class="card">
      <div class="card-head">
        <div>
          <div class="card-title">算子谱 · 模型学到的周期模态</div>
          <div class="card-sub">按模态的衰减时间 τ 排序（对数轴）；横过 72 h 说明该模态能撑过整个预报窗</div>
        </div>
      </div>
      <div class="card-body">
        <EChart :option="spectrumOption" height="240px" />
        <p class="note">
          谱里出现两个可解释的模态：<b>24 小时</b>（日循环，来自窟体热惯性对昼夜温差的响应）与
          <b>年周期</b>（季节背景）。这两个模态不是我们手工塞进去的，是算子自己从数据里学到的——
          这也是我们说"物理代理"而不是"黑箱拟合"的依据。
        </p>
        <p class="note alert">
          <b>一个重要澄清</b>：我们<b>没有</b>用这个算子去做多步递推（rollout）。早期版本试过，
          实测 72 小时递推的 R² 只有 0.117，而直接读出是 0.429，因为慢变滑动均值是<b>外生汇总量</b>，
          不是算子真正的不变量。算子在这里的角色是「作用在室外轨迹上的可微输运读出」，
          不是「自我演化的动力学系统」。这条负结果写在
          <span class="src">code/results/diag_rollout.csv</span> 与 <span class="src">docs/01_技术路线.md</span> 里。
        </p>
      </div>
    </div>
  </div>

  <!-- 消融 ------------------------------------------------------------- -->
  <div class="card">
    <div class="card-head">
      <div>
        <div class="card-title">特征族消融 · 去掉哪一块最疼</div>
        <div class="card-sub">以 Operator-Full（R² = {{ full.R2.toFixed(4) }}）为基准的 R² 下降</div>
      </div>
    </div>
    <div class="card-body tight">
      <table class="tbl">
        <thead>
          <tr><th>消融</th><th class="r">特征数</th><th class="r">RMSE</th><th class="r">R²</th><th class="r">ΔR²</th><th class="r">拟合秒</th><th>说明</th></tr>
        </thead>
        <tbody>
          <tr class="hl">
            <td class="strong">Operator-Full（本作品）</td>
            <td class="r">{{ full.nFeatures }}</td>
            <td class="r">{{ full.RMSE.toFixed(3) }}</td>
            <td class="r strong">{{ full.R2.toFixed(4) }}</td>
            <td class="r">—</td>
            <td class="r">{{ full.fitSeconds?.toFixed(2) }}</td>
            <td class="note-cell">完整 258 维</td>
          </tr>
          <tr v-for="a in ablations" :key="a.model">
            <td>{{ a.short }}</td>
            <td class="r">{{ a.nFeatures ?? '—' }}</td>
            <td class="r">{{ a.RMSE.toFixed(3) }}</td>
            <td class="r">{{ a.R2.toFixed(4) }}</td>
            <td class="r" :style="{ color: CINNABAR }">−{{ a.drop.toFixed(4) }}</td>
            <td class="r">{{ a.fitSeconds?.toFixed(2) ?? '—' }}</td>
            <td class="note-cell">{{ a.note }}</td>
          </tr>
        </tbody>
      </table>
      <SourceNote kind="warn">
        贡献最大的是<b>慢变滑动均值</b>（去掉后 R² 从 0.876 掉到 0.740，ΔR² = −0.136），
        其次是长延迟记忆（−0.152）与即时外场（−0.246 的反面，见上表）。Magnus 物理比值的边际贡献很小
        （ΔR² ≈ −0.002），说明在现有数据分辨率下，物理比值带来的信息已被延迟与均值特征覆盖。
        出处 <span class="src">code/results/derisk01_model_comparison.csv</span>。
      </SourceNote>
    </div>
  </div>

  <!-- 复现 ------------------------------------------------------------- -->
  <div class="card">
    <div class="card-head">
      <div>
        <div class="card-title">复现路径</div>
        <div class="card-sub">全流程 CPU 可运行，无需 GPU</div>
      </div>
      <span class="badge ok">全流程 CPU</span>
    </div>
    <div class="card-body">
      <div class="callout" style="font-family: var(--mono); font-size: 11.5px; line-height: 2">
        python code/experiments/derisk_01_transport.py &nbsp;&nbsp;# 核心算法与基线对照<br />
        python code/experiments/exp03_risk_aligned.py &nbsp;&nbsp;&nbsp;&nbsp;# A/B/C 目标函数消融<br />
        python code/experiments/validate_crosscave.py &nbsp;&nbsp;&nbsp;&nbsp;# 物理一致性核对<br />
        python code/experiments/validate_iccp.py &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# 真实洞穴迁移<br />
        python code/experiments/check_isd_outdoor.py &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# 驱动真实性对照<br />
        python tools/build_frontend_data.py &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# 重生成本页面的全部数据
      </div>
      <p class="note info">
        本页面<b>没有任何手工填写的数字</b>：所有数值都由
        <span class="src">tools/build_frontend_data.py</span> 从 <span class="src">code/results/*.csv</span>
        读出后生成为 TypeScript 常量。改实验 → 重跑管线 → 前端自动同步，不会出现「文档与结果对不上」。
      </p>
    </div>
  </div>
</template>
