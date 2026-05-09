<template>
  <v-app>
    <v-app-bar color="primary" density="compact">
      <v-app-bar-nav-icon @click="drawer = !drawer" class="d-md-none" />
      <v-app-bar-title>Trade-Alpha</v-app-bar-title>
    </v-app-bar>

    <v-navigation-drawer v-model="drawer" :permanent="mdAndUp" :temporary="!mdAndUp">
      <v-list>
        <v-list-item
          v-for="item in menuItems"
          :key="item.path"
          :to="item.path"
          :prepend-icon="item.icon"
          :title="item.title"
        />
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

const menuItems = [
  { path: '/data', title: '数据管理', icon: 'mdi-database' },
  { path: '/portfolios', title: '账户管理', icon: 'mdi-wallet' },
  { path: '/strategies', title: '策略管理', icon: 'mdi-strategy' },
  { path: '/backtest', title: '回测', icon: 'mdi-chart-line' },
  { path: '/trades', title: '交易记录', icon: 'mdi-swap-horizontal' },
]
</script>
