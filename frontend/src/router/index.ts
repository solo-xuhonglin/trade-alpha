import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/data/list'
  },
  {
    path: '/data',
    redirect: '/data/list',
    children: [
      {
        path: 'list',
        name: 'DataList',
        component: () => import('@/views/DataListView.vue')
      },
      {
        path: 'analysis/manage',
        name: 'DataAnalysisManage',
        component: () => import('@/views/DataAnalysisManageView.vue')
      },
      {
        path: 'analysis/records',
        name: 'DataAnalysisRecords',
        component: () => import('@/views/DataAnalysisRecordsView.vue')
      },
      {
        path: 'trade-calendar',
        name: 'TradeCalendar',
        component: () => import('@/views/TradeCalendarView.vue')
      }
    ]
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
  },
  {
    path: '/live-suggestion',
    redirect: '/live-suggestion/positions',
    children: [
      {
        path: 'positions',
        name: 'LivePositionManage',
        component: () => import('@/views/LivePositionManageView.vue')
      },
      {
        path: 'manage',
        name: 'LiveSuggestionManage',
        component: () => import('@/views/LiveSuggestionManageView.vue')
      },
      {
        path: 'records',
        name: 'LiveSuggestionRecords',
        component: () => import('@/views/LiveSuggestionRecordsView.vue')
      },
      {
        path: 'daily-rankings',
        name: 'LiveSuggestionDailyRankings',
        component: () => import('@/views/DailyRankingsView.vue')
      },
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
