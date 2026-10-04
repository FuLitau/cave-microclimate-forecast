import { createRouter, createWebHashHistory } from 'vue-router'
import Overview from './views/Overview.vue'
import Forecast from './views/Forecast.vue'
import Compare from './views/Compare.vue'
import Algorithm from './views/Algorithm.vue'

export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/overview' },
    { path: '/overview', component: Overview, meta: { title: '风险总览' } },
    { path: '/forecast', component: Forecast, meta: { title: '预报看板' } },
    { path: '/compare', component: Compare, meta: { title: '模型对比' } },
    { path: '/algorithm', component: Algorithm, meta: { title: '算法说明' } }
  ]
})
