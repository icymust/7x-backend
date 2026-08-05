<script setup lang="ts">
import AppSidebar from './components/AppSidebar.vue'
</script>

<template>
  <AppSidebar />
  <div class="app-main">
    <RouterView />
  </div>
</template>

<style scoped>
.app-main {
  flex: 1;
  min-width: 0;
  height: 100%;
  display: flex;
  flex-direction: row;
  overflow: hidden;
}
</style>
