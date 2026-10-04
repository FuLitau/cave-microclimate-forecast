<script setup lang="ts">
</script>

<template>
  <div class="shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">窟</div>
        <div>
          <div class="brand-name">石窟天盾</div>
          <div class="brand-sub">洞窟微气候风险预警</div>
        </div>
      </div>
      <nav class="nav">
        <router-link class="nav-item" to="/overview"><span class="nav-ico">◉</span> 风险总览</router-link>
        <router-link class="nav-item" to="/forecast"><span class="nav-ico">◍</span> 预报看板</router-link>
        <router-link class="nav-item" to="/compare"><span class="nav-ico">▮▮</span> 模型对比</router-link>
        <router-link class="nav-item" to="/algorithm"><span class="nav-ico">Σ</span> 算法说明</router-link>
      </nav>
      <div class="side-foot">
        窟内无公开实测数据：演示窟序列为文献标定物理模型生成（physics-derived synthetic），并经独立真实洞穴数据外部验证。
      </div>
    </aside>
    <main class="main">
      <router-view />
    </main>
  </div>
</template>
