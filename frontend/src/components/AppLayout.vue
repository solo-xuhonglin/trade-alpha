<template>
  <v-app>
    <v-app-bar color="primary" density="comfortable" flat>
      <v-app-bar-nav-icon @click="drawer = !drawer" class="d-md-none" />
      <v-app-bar-title class="text-h6 font-weight-bold">Trade-Alpha</v-app-bar-title>
    </v-app-bar>

    <v-navigation-drawer
      v-model="drawer"
      :permanent="mdAndUp"
      :temporary="!mdAndUp"
      border="0"
      elevation="0"
    >
      <v-list nav density="compact" class="pt-2">
        <v-list-item
          v-for="item in menuItems"
          :key="item.path"
          :to="item.path"
          :prepend-icon="item.icon"
          :title="item.title"
          rounded="xl"
          active-class="bg-primary-light"
          class="mx-2 mb-1"
        />
      </v-list>
    </v-navigation-drawer>

    <v-main>
      <router-view />
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

<style scoped>
:deep(.v-navigation-drawer .v-list-item--active) {
  background-color: rgb(var(--v-theme-primary), 0.12) !important;
  color: rgb(var(--v-theme-primary)) !important;
}
</style>
