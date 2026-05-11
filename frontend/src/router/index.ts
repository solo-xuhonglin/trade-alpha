import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/data'
  },
  {
    path: '/data',
    name: 'Data',
    component: () => import('@/views/DataView.vue')
  },
  {
    path: '/account-configs',
    name: 'AccountConfigs',
    component: () => import('@/views/AccountsPage.vue')
  },
  {
    path: '/strategies',
    name: 'Strategies',
    component: () => import('@/views/StrategyView.vue')
  },
  {
    path: '/models',
    name: 'Models',
    component: () => import('@/views/ModelsView.vue')
  },
  {
    path: '/trainings',
    name: 'Trainings',
    component: () => import('@/views/TrainingsView.vue')
  },
  {
    path: '/backtest',
    name: 'Backtest',
    component: () => import('@/views/BacktestView.vue')
  },
  {
    path: '/trades',
    name: 'Trades',
    component: () => import('@/views/TradeListView.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
