import { createRouter, createWebHashHistory } from 'vue-router'
import ConsoleView from './views/ConsoleView.vue'
import CompareView from './views/CompareView.vue'
import ValidationView from './views/ValidationView.vue'
import MethodView from './views/MethodView.vue'

/**
 * 用 hash 路由 + vite.config.ts 的 `base: './'`，整个 dist 目录可以直接双击
 * index.html 离线打开，不依赖任何服务器或 CDN —— 比赛演示环境的硬要求。
 */
export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', name: 'console', component: ConsoleView, meta: { title: '风险指挥台' } },
    { path: '/compare', name: 'compare', component: CompareView, meta: { title: '效果对照' } },
    { path: '/validation', name: 'validation', component: ValidationView, meta: { title: '可信度验证' } },
    { path: '/method', name: 'method', component: MethodView, meta: { title: '方法说明' } },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior: () => ({ top: 0 }),
})
