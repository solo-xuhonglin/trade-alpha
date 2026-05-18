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
    component: () => import('@/views/AccountConfigView.vue')
  },
  {
    path: '/strategies',
    name: 'Strategies',
    component: () => import('@/views/StrategyConfigView.vue')
  },
  {
    path: '/models',
    name: 'Models',
    component: () => import('@/views/ModelConfigView.vue')
  },
  {
    path: '/trainings',
    redirect: '/trainings/manage',
    children: [
      {
        path: 'manage',
        name: 'TrainingManage',
        component: () => import('@/views/TrainingManageView.vue')
      },
      {
        path: 'records',
        name: 'TrainingRecords',
        component: () => import('@/views/TrainingRecordsView.vue')
      }
    ]
  },
  {
    path: '/backtest',
    redirect: '/backtest/manage',
    children: [
      {
        path: 'manage',
        name: 'BacktestManage',
        component: () => import('@/views/BacktestManageView.vue')
      },
      {
        path: 'records',
        name: 'BacktestRecords',
        component: () => import('@/views/BacktestRecordsView.vue')
      },
      {
        path: 'trades',
        name: 'BacktestTrades',
        component: () => import('@/views/TradesView.vue')
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
