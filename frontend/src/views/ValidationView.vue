<script setup lang="ts">
/**
 * 可信度验证 —— 窟内实测数据无法获取，所以「凭什么相信这个模型」必须由三条独立证据链回答：
 *   ① 物理一致性：合成窟内序列的年变幅/相位落在公开文献报告区间内；
 *   ② 外部迁移：在以色列 ICCP 计划的 8 个真实洞穴逐小时温湿度上做留窟测试；
 *   ③ 驱动真实性：NASA POWER 再分析与敦煌国家站 ISD 实测报文逐小时对照。
 * 三条链都保留对己不利的数字，不做筛选。
 */
import { computed } from 'vue'
import EChart from '../components/EChart.vue'
import StatCard from '../components/StatCard.vue'
import SourceNote from '../components/SourceNote.vue'
import { AZURITE, baseAxis, baseLegend, baseTooltip, CINNABAR, GOLD, INK_2, INK_4, MALACHITE, OCHRE } from '../lib/charts'
import { crosscave, iccp, iccpOpWins, iccpValidCount, isd, metricNames } from '../data/validate'

const passCount = computed(() => crosscave.filter((c) => c.pass).length)

/** 每行的归一化区间：把模型区间与文献区间画在同一根轨道上（单位逐行不同，故按行归一化） */
const ranges = computed(() =>
  crosscave.map((c) => {
    const vals = [c.lo, c.hi, c.litLo, c.litHi]
    const min = Math.min(...vals)
    const max = Math.max(...vals)
    const span = max - min || 1
    const pct = (v: number) => ((v - min) / span) * 100
    return {
      ...c,
      name: metricNames[c.metric] ?? c.metric,
      min,
      max,
      bandLeft: Math.min(pct(c.litLo), pct(c.litHi)),
      bandWidth: Math.abs(pct(c.litHi) - pct(c.litLo)),
      spanLeft: Math.min(pct(c.lo), pct(c.hi)),
      spanWidth: Math.max(Math.abs(pct(c.hi) - pct(c.lo)), 0.8),
    }
  }),
)

const validIc = computed(() => iccp.filter((r) => r.valid))

const iccpOption = computed(() => ({
  grid: { left: 44, right: 18, top: 44, bottom: 54 },
  legend: { ...baseLegend, data: ['初稿一阶传递式', '本作品（输运读出）'] },
  tooltip: {
    ...baseTooltip,
    trigger: 'axis',
    axisPointer: { type: 'shadow' },
    valueFormatter: (v: any) => (typeof v === 'number' ? v.toFixed(4) : '—'),
  },
  xAxis: {
    type: 'category',
    data: validIc.value.map((r) => r.name),
    ...baseAxis,
    axisLabel: { ...baseAxis.axisLabel, interval: 0, rotate: 26 },
  },
  yAxis: { type: 'value', name: 'R²', min: -1.1, max: 1, nameTextStyle: { color: INK_4, fontSize: 11 }, ...baseAxis },
  series: [
    {
      name: '初稿一阶传递式',
      type: 'bar',
      barMaxWidth: 15,
      itemStyle: { color: INK_2, borderRadius: [2, 2, 0, 0] },
      data: validIc.value.map((r) => ({ value: r.plotFot, itemStyle: { color: r.trunc ? CINNABAR : INK_2 } })),
    },
    {
      name: '本作品（输运读出）',
      type: 'bar',
      barMaxWidth: 15,
      itemStyle: { color: AZURITE, borderRadius: [2, 2, 0, 0] },
      data: validIc.value.map((r) => ({ value: r.plotOp, itemStyle: { color: r.trunc ? OCHRE : AZURITE } })),
    },
  ],
}))

const isdOption = computed(() => ({
  grid: { left: 130, right: 40, top: 20, bottom: 26 },
  tooltip: {
    ...baseTooltip,
    trigger: 'axis',
    axisPointer: { type: 'shadow' },
    formatter: (ps: any) => {
      const p = ps[0]
      const row = isd.find((d) => d.variable === p.name)!
      return `<b>${row.variable}</b><br/>样本 ${row.n.toLocaleString()} h<br/>相关系数 r = ${row.r.toFixed(3)}<br/>偏差 ${row.bias.toFixed(2)} · RMSE ${row.rmse.toFixed(2)} · MAE ${row.mae.toFixed(2)}`
    },
  },
  xAxis: { type: 'value', min: 0, max: 1, name: 'r', nameTextStyle: { color: INK_4, fontSize: 11 }, ...baseAxis },
  yAxis: { type: 'category', data: isd.map((d) => d.variable), ...baseAxis, axisLabel: { color: INK_2, fontSize: 11 } },
  series: [
    {
      type: 'bar',
      barMaxWidth: 22,
      data: isd.map((d) => ({
        value: d.r,
        itemStyle: { color: d.r >= 0.9 ? MALACHITE : d.r >= 0.7 ? OCHRE : CINNABAR, borderRadius: [0, 3, 3, 0] },
      })),
      label: { show: true, position: 'right', color: INK_2, fontSize: 11, formatter: (p: any) => p.value.toFixed(3) },
      markLine: {
        silent: true,
        symbol: 'none',
        label: { formatter: '0.9 参考线', color: INK_4, fontSize: 10.5 },
        lineStyle: { color: GOLD, type: 'dashed', width: 1 },
        data: [{ xAxis: 0.9 }],
      },
    },
  ],
}))
</script>

<template>
  <section class="view-head">
    <h1>可信度验证</h1>
    <p>
      窟内温湿度实测数据在莫高窟及国内石窟实质不可获得，所以「模型凭什么可信」不能靠自有标签自证。
      我们改用三条彼此独立的外部证据链来约束模型：物理一致性、真实洞穴迁移、驱动数据真实性。
    </p>
  </section>

  <div class="grid g-4">
    <StatCard
      label="物理一致性核对"
      :value="`${passCount} / ${crosscave.length}`"
      sub="年变幅与相位落在文献报告区间内"
      hint="含 1 项未通过：窟外月均 RH 年变幅偏窄"
      accent="malachite"
    />
    <StatCard
      label="真实洞穴迁移"
      :value="`${iccpOpWins} / ${iccpValidCount}`"
      sub="ICCP 计划 8 个有效洞穴上优于初稿传递式"
      hint="第 12 洞 target_sd=0（常数序列）已按门限剔除"
      accent="azurite"
    />
    <StatCard
      label="驱动数据真实性"
      value="0.955"
      sub="气温与敦煌国家站 ISD 实测的相关系数"
      hint="23,915 个逐小时配对样本；湿度相关仅 0.576，已披露"
      accent="ochre"
    />
    <StatCard
      label="外部数据来源"
      value="3 条"
      sub="NASA POWER · NOAA ISD · Zenodo ICCP"
      hint="全部为公开可复现数据，无任何私有数据依赖"
      accent="gold"
    />
  </div>

  <!-- 证据链 ① --------------------------------------------------------- -->
  <div class="card">
    <div class="card-head">
      <div>
        <div class="card-title">证据链 ① · 合成窟内序列的物理一致性</div>
        <div class="card-sub">
          模型输出的年变幅 / 年相位 / 日相位与公开文献报告区间的对照。绿带 = 文献区间，蓝条 = 本模型区间。
        </div>
      </div>
      <span class="badge" :class="passCount === crosscave.length ? 'ok' : 'watch'">
        <i class="dot" />{{ passCount }} / {{ crosscave.length }} 落入文献区间
      </span>
    </div>
    <div class="card-body tight">
      <table class="tbl">
        <thead>
          <tr>
            <th style="width: 240px">指标</th>
            <th class="r" style="width: 120px">本模型区间</th>
            <th class="r" style="width: 120px">文献区间</th>
            <th>区间对照</th>
            <th class="c" style="width: 80px">结论</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in ranges" :key="r.metric">
            <td class="strong">{{ r.name }}</td>
            <td class="r">{{ r.lo.toFixed(2) }} ~ {{ r.hi.toFixed(2) }}</td>
            <td class="r dim">{{ r.litLo.toFixed(2) }} ~ {{ r.litHi.toFixed(2) }}</td>
            <td>
              <div class="rangebar">
                <div class="rangebar-track">
                  <div class="rangebar-band" :style="{ left: r.bandLeft + '%', width: Math.max(r.bandWidth, 1) + '%' }" />
                  <div class="rangebar-span" :class="{ fail: !r.pass }" :style="{ left: r.spanLeft + '%', width: r.spanWidth + '%' }" />
                </div>
              </div>
              <div class="rangebar-legend">
                <span>该行量程 {{ r.min.toFixed(1) }} ~ {{ r.max.toFixed(1) }}</span>
              </div>
            </td>
            <td class="c">
              <span class="badge" :class="r.pass ? 'ok' : 'alert'">{{ r.pass ? '通过' : '未通过' }}</span>
            </td>
          </tr>
        </tbody>
      </table>
      <SourceNote kind="warn">
        <b>未通过的那一项照实列出</b>：窟外月均 RH 年变幅为 22.84 ~ 39.30%，文献报告区间是 16.3 ~ 47.4%。
        本模型输出的变幅落在文献区间内部，但比文献的<b>包络更窄</b>——因为物理模型用的是单一等效气团，
        不会重现极端年份。其余五项（窟内外气温年变幅、窟内 RH 年变幅、气温年相位滞后、日温滞后极值）全部通过。
        出处 <span class="src">code/results/validate_crosscave.csv</span>。
      </SourceNote>
    </div>
  </div>

  <!-- 证据链 ② --------------------------------------------------------- -->
  <div class="card">
    <div class="card-head">
      <div>
        <div class="card-title">证据链 ② · 真实洞穴留窟迁移（ICCP 计划）</div>
        <div class="card-sub">
          以色列洞穴气候计划（ICCP, Zenodo 10.5281/zenodo.17505739, CC-BY-4.0）12 个岩溶洞穴的逐小时 T/RH，
          含荒漠气候带，2019–2021。留窟测试：每个洞只用自己的室外场做输入。
        </div>
      </div>
      <span class="badge info">独立外部数据</span>
    </div>
    <div class="card-body">
      <EChart :option="iccpOption" height="290px" />
      <div class="hr" />
      <table class="tbl">
        <thead>
          <tr>
            <th class="r">洞号</th><th>洞穴名</th><th class="r">测试样本</th><th class="r">目标标准差</th>
            <th class="r">持续性参照 R²</th><th class="r">初稿传递式 R²</th><th class="r">本作品 R²</th><th class="c">更优</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in iccp" :key="r.cave" :class="{ 'dim-row': !r.valid }">
            <td class="r">{{ r.cave }}</td>
            <td class="strong">{{ r.name }}</td>
            <td class="r">{{ r.nTest.toLocaleString() }}</td>
            <td class="r">{{ r.targetSd.toFixed(3) }}</td>
            <td class="r">{{ Math.abs(r.r2Persist) > 1e4 ? r.r2Persist.toExponential(2) : r.r2Persist.toFixed(4) }}</td>
            <td class="r">{{ r.trunc ? r.r2Fot.toFixed(2) : r.r2Fot.toFixed(4) }}</td>
            <td class="r">{{ r.trunc ? r.r2Op.toFixed(2) : r.r2Op.toFixed(4) }}</td>
            <td class="c">
              <span v-if="!r.valid" class="badge plain">不评估</span>
              <span v-else class="badge" :class="r.r2Op > r.r2Fot ? 'ok' : 'alert'">{{ r.r2Op > r.r2Fot ? '是' : '否' }}</span>
            </td>
          </tr>
        </tbody>
      </table>
      <SourceNote kind="alert">
        <b>三条必须一起说的限制</b>：
        ① 第 12 洞 Te'omim 的目标序列标准差为 0.000（常数序列），任何模型的 R² 都会变成 ±1e25 量级的噪声，
        按管线门限剔除、不参与统计；
        ② Sela'、Murabba'at 2、Har Sifsof 三洞本作品 R² 仍为负，说明<b>模型并非在所有洞穴上可用</b>，
        Har Sifsof 还是唯一一个本作品劣于初稿传递式的洞（−0.654 vs −0.020）；
        ③ 图表中截断到 −1 的柱子（红/赭色）表示原始 R² 已超出坐标轴，真实值见右表。
        出处 <span class="src">code/results/iccp_transfer.csv</span>。
      </SourceNote>
    </div>
  </div>

  <!-- 证据链 ③ --------------------------------------------------------- -->
  <div class="card">
    <div class="card-head">
      <div>
        <div class="card-title">证据链 ③ · 驱动数据的真实性（NASA POWER vs NOAA ISD 实测报文）</div>
        <div class="card-sub">
          模型用的是再分析产品 NASA POWER。这里把它与敦煌国家站（USAF 524180）的逐小时地面观测报文逐时配对，
          检验再分析在莫高窟是否可信。配对窗口 2015-01-01 – 2023-04-28（该站此后停止报文）。
        </div>
      </div>
      <span class="badge info">独立观测源</span>
    </div>
    <div class="card-body">
      <EChart :option="isdOption" height="160px" />
      <div class="hr" />
      <table class="tbl">
        <thead>
          <tr><th>变量</th><th class="r">配对小时数</th><th class="r">相关系数 r</th><th class="r">偏差</th><th class="r">RMSE</th><th class="r">MAE</th><th>判读</th></tr>
        </thead>
        <tbody>
          <tr v-for="d in isd" :key="d.variable">
            <td class="strong">{{ d.variable }}</td>
            <td class="r">{{ d.n.toLocaleString() }}</td>
            <td class="r">{{ d.r.toFixed(3) }}</td>
            <td class="r">{{ d.bias.toFixed(3) }}</td>
            <td class="r">{{ d.rmse.toFixed(3) }}</td>
            <td class="r">{{ d.mae.toFixed(3) }}</td>
            <td class="note-cell">
              <span v-if="d.r >= 0.9">再分析与实测高度一致，可作为驱动源</span>
              <span v-else>相关偏弱：{{ d.variable }} 的再分析值只能提供粗分辨率的背景</span>
            </td>
          </tr>
        </tbody>
      </table>
      <SourceNote kind="alert">
        <b>湿度是这条链上最弱的一环</b>：气温 r = 0.955、气压 r = 0.939，但相对湿度只有 r = 0.576，
        偏差 +9.16 个百分点、RMSE 19.56。原因有两个——再分析是约 50 km 网格的平均，而敦煌站是单点；
        并且 RH 本身由气温与比湿导出，误差被放大。
        <b>这直接决定了模型的分辨率上限</b>：驱动里湿度只有粗略信息，窟内 RH 的峰值预报不可能很准，
        这正是演示窗口出现漏报的物理来源之一。我们把它写进材料而不是隐藏。
        出处 <span class="src">code/results/isd_vs_power.csv</span>。
      </SourceNote>
    </div>
  </div>

  <SourceNote>
    本页全部数字来自 <span class="src">code/results/validate_crosscave.csv、iccp_transfer.csv、iccp_harmonics.csv、iccp_damping.csv、isd_vs_power.csv</span>，
    由 <span class="src">tools/build_frontend_data.py</span> 自动生成。
    ICCP 数据采用 CC-BY-4.0 许可，引用见 <span class="src">docs/06_佐证材料.md</span>。
  </SourceNote>
</template>
