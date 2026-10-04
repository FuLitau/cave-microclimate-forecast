<script setup lang="ts">
defineProps<{ title: string; cap?: string }>()
</script>

<template>
  <section class="panel">
    <h3 class="panel-title">{{ title }}</h3>
    <div v-if="cap" class="panel-cap">{{ cap }}</div>
    <slot />
  </section>
</template>
