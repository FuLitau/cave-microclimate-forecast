<script setup lang="ts">
import Panel from '../components/Panel.vue'
</script>

<template>
  <div class="page-head">
    <div class="page-title">算法说明</div>
    <div class="page-cap">三层人工智能技术路线：从"预测得准"到"预警得准"</div>
  </div>

  <Panel title="三层管线" cap="公开室外气象是唯一入模驱动数据；窟内侧由物理代理标签承担训练监督">
    <div class="pipe">
      <div class="pipe-stage">
        <span class="pipe-tag">L1 · 外场预报</span>
        <div class="pipe-name">多时效概率预报网络</div>
        <div class="pipe-io">X(168h) → Q(72h × 5要素 × 分位)</div>
        <div class="pipe-desc">
          MLP 神经网络直接输出分位数轨迹而非单点，保留不确定性；
          端到端评测时外场为<b style="color:var(--text)">预报值而非真值</b>，已含 L1 预报误差。
        </div>
      </div>
      <div class="pipe-arrow">→</div>
      <div class="pipe-stage">
        <span class="pipe-tag">L2 · 微气候输运</span>
        <div class="pipe-name">延迟嵌入输运算子</div>
        <div class="pipe-io">室外轨迹 → Ψ(258 维) → 窟内风险</div>
        <div class="pipe-desc">
          借鉴 Koopman/EDMD 思想，把室外气象延迟嵌入到高维可观测量空间，
          用<b style="color:var(--text)">岭回归闭式解</b>学习线性输运算子——全流程无梯度下降、纯 CPU 可运行、系数可解释。
        </div>
      </div>
      <div class="pipe-arrow">→</div>
      <div class="pipe-stage">
        <span class="pipe-tag">L3 · 风险对齐</span>
        <div class="pipe-name">风险对齐训练</div>
        <div class="pipe-io">min L = MSE + λ · twCRPS</div>
        <div class="pipe-desc">
          在 MSE 目标上引入阈值加权风险项，权重集中于 62/67/75% 三档阈值附近与持续超阈时段，
          使优化方向与"超阈 + 持续"的文保损伤判据一致。
        </div>
      </div>
    </div>
  </Panel>

  <div class="grid-2">
    <Panel title="输运算子与闭式解" cap="延迟嵌入把「室外驱动 + 窟内记忆」装进同一个线性空间">
      <div class="formula">
        Ψ(t) = [ x(t−k…t), &nbsp;MA<sub>slow</sub>(x), &nbsp;Magnus(T,RH) ]
        <small>三族特征共 258 维：快变延迟 240 / 慢变滑动均值 12 / Magnus 温湿耦合 6</small>
      </div>
      <div class="formula">
        W* = ( ΨᵀΨ + βI )<sup>−1</sup> ΨᵀY
        <small>岭回归闭式解：一次矩阵求逆得到输运算子，可复现、可解释、秒级训练</small>
      </div>
      <div class="formula">
        L = MSE( ŷ, y ) + λ · twCRPS<sub>62,67,75</sub>( F, y )
        <small>阈值加权的连续排序概率评分：只有落在风险阈值附近与持续超阈时段的误差被重罚</small>
      </div>
      <table class="tb" style="margin-top: 8px">
        <thead><tr><th>特征族</th><th>维数</th><th>物理含义</th></tr></thead>
        <tbody>
          <tr><td>快变延迟</td><td class="num">240</td><td>门体开启后的快速换气响应（小时级）</td></tr>
          <tr><td>慢变滑动均值</td><td class="num">12</td><td>围岩热湿惯性的多尺度记忆（天~周级）</td></tr>
          <tr><td>Magnus 温湿耦合</td><td class="num">6</td><td>温度决定饱和水汽压，同湿度下风险随温度变化</td></tr>
        </tbody>
      </table>
    </Panel>

    <div>
      <Panel title="为什么要「风险对齐」">
        <p class="para">
          <b>场景中的问题。</b>壁画盐害由相对湿度超阈后的<b>持续时长与反复次数</b>驱动，而不是瞬时数值本身；
          一个整体 RMSE 很小的模型，完全可能把资源全部用在占 98% 的安全时段，而在真正需要预警的尾部事件上漏报殆尽。
        </p>
        <p class="para">
          <b>现有方法的不足。</b>既有洞窟微环境研究普遍以均方误差为训练目标。我们实验测得：MSE 训练的点预报
          R² 达 0.585，但超阈召回率仅 0.047——"预测数值看起来较准，需要预警的事件几乎全部漏报"。
        </p>
        <p class="para">
          <b>我们的方法。</b>把文保损伤判据直接写进训练目标：引入阈值加权风险项后，超阈 F1 由 0.072 提升至 0.164、
          AUC 由 0.862 提升至 0.903，且点精度不降反升——风险对齐不是用精度换预警，而是让模型把注意力放到业务真正关心的地方。
        </p>
      </Panel>

      <Panel title="方案是怎么选出来的" cap="关键结构均经消融实验比较后确定">
        <p class="para">
          <b>多步演化 vs 直接读出。</b>我们首先尝试让学到的算子沿时间逐步滚动演化（K^h 闭式 rollout），
          系统比较后发现其在 6–72 h 全部时效上劣于"一步映射 + 直接读出"——慢变滑动均值是外生汇总量，
          不适合作为演化对象。因此保留延迟嵌入思想，采用直接读出结构。
        </p>
        <p class="para">
          <b>非线性读出 vs 线性读出。</b>在相同特征下比较了梯度提升与岭回归：小样本、尾部事件场景中，
          线性读出在阈值处的检出与极值捕捉更稳，最终采用线性闭式解。
        </p>
        <p class="para">
          <b>固定阈值权重 vs 内生权重。</b>风险项权重由算子内生导出的强化版本经 18 格点消融（验证/测试 × 时效 × 阈值）
          仅 1 格占优，无稳定增益；最终保留固定阈值权重的简洁形式，并把该消融作为创新点边界的诚实依据。
        </p>
      </Panel>
    </div>
  </div>

  <Panel title="标签与外部验证" cap="没有公开窟内实测，如何避免「模型只认识自己的标签」">
    <p class="para">
      窟内连续实测数据不由公开渠道提供。本作品以文献参数化的热湿物理模型生成<b>合成标签</b>（显式声明，不作实测），
      并以三层独立证据约束其可信度：<b>文献同窟同期对照</b>（第 71 窟 2019–2021 实测统计量，温度统计量从未参与标定）、
      <b>跨窟留一验证</b>（用第 87 窟参数预测第 71 窟，月尺度统计量通过检验）、
      <b>独立真实洞穴外部验证</b>（ICCP 12 个岩溶洞穴逐小时观测，输运算子在绝大多数洞窟优于一阶传递形式）。
      三者共同支持方法层面的有效性结论；莫高窟现场传感器的最终监督验证是下一阶段工作。
    </p>
  </Panel>
</template>
