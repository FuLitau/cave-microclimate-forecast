<script setup lang="ts">
/**
 * ECharts 容器：负责实例生命周期与尺寸自适应。
 * option 由父组件传入，变更时整体 setOption（notMerge=true，避免残留旧系列）。
 */
import { onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { echarts, type ChartOption } from '../lib/charts'

const props = withDefaults(defineProps<{ option: ChartOption; height?: string }>(), {
  height: '260px',
})

const el = ref<HTMLDivElement | null>(null)
const inst = shallowRef<echarts.ECharts | null>(null)
let ro: ResizeObserver | null = null

function render() {
  if (!inst.value) return
  inst.value.setOption(props.option, true)
}

onMounted(() => {
  if (!el.value) return
  inst.value = echarts.init(el.value, undefined, { renderer: 'canvas' })
  render()
  ro = new ResizeObserver(() => inst.value?.resize())
  ro.observe(el.value)
})

onBeforeUnmount(() => {
  ro?.disconnect()
  inst.value?.dispose()
  inst.value = null
})

watch(() => props.option, render, { deep: false })
</script>

<template>
  <div ref="el" class="chart" :style="{ height }" />
</template>
