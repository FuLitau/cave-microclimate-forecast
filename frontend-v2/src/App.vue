<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { DECISION_DISCLAIMER, DEMO_HONEST_NOTE, SYNTHETIC_LABEL_NOTE } from './data/meta'

const route = useRoute()

const NAV = [
  { path: '/', icon: '台', label: '风险指挥台', hint: '预报 → 风险 → 建议' },
  { path: '/compare', icon: '较', label: '效果对照', hint: '用与不用本模型' },
  { path: '/validation', icon: '证', label: '可信度验证', hint: '三条外部证据链' },
  { path: '/method', icon: '法', label: '方法说明', hint: '三层链路与消融' },
]

const title = computed(() => NAV.find((n) => n.path === route.path)?.label ?? '风险指挥台')
</script>

<template>
  <div class="shell">
    <div class="brand">
      <div class="brand-mark">窟</div>
      <div class="col">
        <div class="brand-name">石窟天盾</div>
        <div class="brand-sub">CAVE MICROCLIMATE</div>
      </div>
    </div>

    <header class="topbar">
      <div class="topbar-left">
        <span class="eyebrow">风险对齐的窟内微气候预报</span>
        <span class="badge plain">{{ title }}</span>
      </div>
      <div class="topbar-right">
        <span class="badge watch">备选版 v2</span>
        <span class="badge info"><i class="dot" />离线可演示</span>
        <span class="badge">合成标签</span>
      </div>
    </header>

    <nav class="rail">
      <div class="eyebrow rail-group">分析视图</div>
      <RouterLink
        v-for="n in NAV"
        :key="n.path"
        :to="n.path"
        class="nav-item"
        :class="{ on: route.path === n.path }"
      >
        <span class="nav-icon">{{ n.icon }}</span>
        <span class="nav-label">{{ n.label }}</span>
      </RouterLink>

      <div class="spacer" />

      <div class="nav-note">
        窟内序列由文献标定物理模型合成，非窟内实测。预警结论为辅助建议，供管理人员研判。
      </div>
    </nav>

    <main class="main">
      <RouterView />

      <footer style="margin-top: 26px">
        <div class="card">
          <div class="card-body">
            <div class="eyebrow">口径声明</div>
            <p class="note" style="margin-top: 8px">{{ SYNTHETIC_LABEL_NOTE }}</p>
            <p class="note warn">{{ DEMO_HONEST_NOTE }}</p>
            <p class="note info">{{ DECISION_DISCLAIMER }}</p>
          </div>
        </div>
      </footer>
    </main>
  </div>
</template>
