<script setup lang="ts">
/** 口径出处脚注：把"这个数字从哪来"钉在图表下面。 */
withDefaults(defineProps<{ text: string; kind?: 'plain' | 'info' | 'warn' | 'alert' }>(), {
  kind: 'plain',
})
</script>

<template>
  <p class="note" :class="kind === 'plain' ? '' : kind">
    <slot>{{ text }}</slot>
  </p>
</template>
