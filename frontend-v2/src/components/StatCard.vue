<script setup lang="ts">
/** 大数字指标卡。accent 用矿物颜料色名，映射到 CSS 变量。 */
const props = withDefaults(
  defineProps<{
    label: string
    value: string
    sub?: string
    hint?: string
    /** azurite | malachite | ochre | cinnabar | gold | violet | none */
    accent?: string
    /** 口径标签；upper 表示"可部署性上界"口径 */
    scope?: 'end2end' | 'upper' | ''
  }>(),
  { accent: 'none', scope: '', sub: '', hint: '' },
)

const ACCENT: Record<string, string> = {
  azurite: 'var(--azurite)',
  malachite: 'var(--malachite)',
  ochre: 'var(--ochre)',
  cinnabar: 'var(--cinnabar)',
  gold: 'var(--gold)',
  violet: 'var(--violet)',
  none: 'var(--line-2)',
}
</script>

<template>
  <div class="stat" :style="{ '--accent': ACCENT[props.accent] ?? ACCENT.none }">
    <div class="stat-label">
      {{ label }}
      <span v-if="scope === 'upper'" class="scope-tag upper">上界口径</span>
      <span v-else-if="scope === 'end2end'" class="scope-tag">端到端</span>
    </div>
    <div class="stat-value num">{{ value }}</div>
    <div v-if="sub" class="stat-sub">{{ sub }}</div>
    <div v-if="hint" class="stat-hint">{{ hint }}</div>
  </div>
</template>
