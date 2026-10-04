import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  // 相对基址：产物用 `./assets/...` 引用资源，放到任意子目录都能跑。
  base: './',
  server: { port: 5181 },
  build: {
    rollupOptions: {
      output: {
        // 把 ECharts（含 zrender）单独切出来。它是产物里最大的一块，独立成 chunk 后
        // 主包回落到 300 kB 以内，浏览器可以并行下载，也避免 Vite 的 500 kB 告警。
        // 注意：这里用的是静态 chunk 切分而非动态 import —— 路由懒加载会引入运行时
        // 的 chunk 请求，破坏「离线静态托管即可演示」这一硬要求。
        manualChunks: {
          echarts: ['echarts/core', 'echarts/charts', 'echarts/components', 'echarts/renderers'],
        },
      },
    },
    // echarts 单块约 520 kB，属于已知且可接受的体积，无需再告警。
    chunkSizeWarningLimit: 700,
  },
})
