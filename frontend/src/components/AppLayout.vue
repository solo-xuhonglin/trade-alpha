<template>
  <v-app>
    <v-app-bar color="primary" density="compact">
      <v-app-bar-nav-icon @click="drawer = !drawer" class="d-md-none" />
      <v-app-bar-title>Trade-Alpha</v-app-bar-title>
    </v-app-bar>

    <v-navigation-drawer v-model="drawer" :permanent="mdAndUp" :temporary="!mdAndUp" width="200">
      <v-list>
        <v-list-group value="data">
          <template v-slot:activator="{ props }">
            <v-list-item
              v-bind="props"
              prepend-icon="mdi-database"
              title="数据"
            />
          </template>
          <v-list-item
            :to="'/data/list'"
            title="数据列表"
          />
          <v-list-item
            :to="'/data/analysis/manage'"
            title="分析管理"
          />
          <v-list-item
            :to="'/data/analysis/records'"
            title="分析记录"
          />
          <v-list-item
            :to="'/data/trade-calendar'"
            title="交易日历"
          />
        </v-list-group>

        <v-list-group value="config">
          <template v-slot:activator="{ props }">
            <v-list-item
              v-bind="props"
              prepend-icon="mdi-cog"
              title="配置"
            />
          </template>
          <v-list-item
            v-for="item in configItems"
            :key="item.path"
            :to="item.path"
            :title="item.title"
          />
        </v-list-group>

        <v-list-group value="training">
          <template v-slot:activator="{ props }">
            <v-list-item
              v-bind="props"
              prepend-icon="mdi-chart-scatter-plot"
              title="训练"
            />
          </template>
          <v-list-item
            v-for="item in trainingItems"
            :key="item.path"
            :to="item.path"
            :title="item.title"
          />
        </v-list-group>

        <v-list-group value="backtest">
          <template v-slot:activator="{ props }">
            <v-list-item
              v-bind="props"
              prepend-icon="mdi-chart-line"
              title="回测"
            />
          </template>
          <v-list-item
            v-for="item in backtestItems"
            :key="item.path"
            :to="item.path"
            :title="item.title"
          />
        </v-list-group>

        <v-list-group value="livesuggestion">
          <template v-slot:activator="{ props }">
            <v-list-item
              v-bind="props"
              prepend-icon="mdi-finance"
              title="实盘"
            />
          </template>
          <v-list-item
            v-for="item in liveSuggestionItems"
            :key="item.path"
            :to="item.path"
            :title="item.title"
          />
        </v-list-group>
      </v-list>
    </v-navigation-drawer>

    <v-main>
      <v-container fluid>
        <router-view />
      </v-container>
    </v-main>
  </v-app>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useDisplay } from 'vuetify'

const { mdAndUp } = useDisplay()

const drawer = ref(true)

const configItems = [
  { path: '/account-configs', title: '账户配置' },
  { path: '/strategies', title: '策略配置' },
  { path: '/models', title: '模型配置' },
]

const trainingItems = [
  { path: '/trainings/manage', title: '训练管理' },
  { path: '/trainings/records', title: '训练记录' },
]

const backtestItems = [
  { path: '/backtest/manage', title: '回测管理' },
  { path: '/backtest/records', title: '回测记录' },
  { path: '/backtest/trades', title: '交易记录' },
]

const liveSuggestionItems = [
  { path: '/live-suggestion/manage', title: '实盘管理' },
  { path: '/live-suggestion/daily-rankings', title: '每日排名' },
  { path: '/live-suggestion/records', title: '实盘记录' },
]
</script>
