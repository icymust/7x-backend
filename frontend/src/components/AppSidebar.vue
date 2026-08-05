<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Avatar from 'primevue/avatar'
import { useTheme } from '../composables/useTheme'

const { isDark, toggleTheme } = useTheme()
const route = useRoute()
const router = useRouter()

const STORAGE_KEY = '7x-sidebar-collapsed'
const collapsed = ref(localStorage.getItem(STORAGE_KEY) === '1')

function toggleCollapsed() {
  collapsed.value = !collapsed.value
  localStorage.setItem(STORAGE_KEY, collapsed.value ? '1' : '0')
}

interface NavItem {
  label: string
  icon: string
  to?: string
}

const navItems: NavItem[] = [
  { label: 'Dashboard', icon: 'pi pi-th-large', to: '/' },
  { label: 'Warehouses', icon: 'pi pi-box', to: '/map' },
  { label: 'Notifications', icon: 'pi pi-bell', to: '/notifications' },
  { label: 'Couriers', icon: 'pi pi-users' },
  { label: 'Analytics', icon: 'pi pi-chart-line' },
  { label: 'Settings', icon: 'pi pi-cog' },
]

const activeLabel = ref('Dashboard')

function isActive(item: NavItem) {
  return item.to ? route.path === item.to : item.label === activeLabel.value
}

function selectItem(item: NavItem) {
  if (item.to) {
    router.push(item.to)
  } else {
    activeLabel.value = item.label
  }
}
</script>

<template>
  <aside class="sidebar" :class="{ 'sidebar--collapsed': collapsed }">
    <div class="sidebar__brand">
      <span class="sidebar__mark" aria-hidden="true">
        <svg width="20" height="20" viewBox="0 0 48 48" fill="none">
          <path d="M14 14H34L25.5 24.5H34L20 36L23 25.5H16L14 14Z" fill="#4A7DFF" />
        </svg>
      </span>
      <span v-if="!collapsed" class="sidebar__name">7x <span class="sidebar__name-accent">Workers Demand</span></span>
    </div>

    <nav class="sidebar__nav">
      <button
        v-for="item in navItems"
        :key="item.label"
        type="button"
        class="sidebar__item"
        :class="{ 'sidebar__item--active': isActive(item) }"
        :title="collapsed ? item.label : undefined"
        @click="selectItem(item)"
      >
        <i :class="item.icon" class="sidebar__item-icon" />
        <span v-if="!collapsed" class="sidebar__item-label">{{ item.label }}</span>
      </button>
    </nav>

    <div class="sidebar__footer">
      <button
        type="button"
        class="sidebar__item"
        :title="collapsed ? (isDark ? 'Switch to light theme' : 'Switch to dark theme') : undefined"
        @click="toggleTheme"
      >
        <i class="sidebar__item-icon" :class="isDark ? 'pi pi-sun' : 'pi pi-moon'" />
        <span v-if="!collapsed" class="sidebar__item-label">{{ isDark ? 'Light Mode' : 'Dark Mode' }}</span>
      </button>

      <button type="button" class="sidebar__collapse-toggle" @click="toggleCollapsed">
        <i class="pi" :class="collapsed ? 'pi-angle-right' : 'pi-angle-left'" />
        <span v-if="!collapsed">Collapse</span>
      </button>

      <div class="sidebar__user">
        <Avatar label="AM" shape="circle" class="sidebar__avatar" />
        <div v-if="!collapsed" class="sidebar__user-info">
          <span class="sidebar__user-name">Aisha Al Mansoori</span>
          <span class="sidebar__user-role">Operations Manager</span>
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  position: relative;
  z-index: 20;
  width: 15.5rem;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--brand-navy);
  border-right: 1px solid rgba(255, 255, 255, 0.08);
  transition: width 0.2s ease;
  overflow: hidden;
}

.sidebar--collapsed {
  width: 4.5rem;
}

.sidebar__brand {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 1.1rem;
  flex-shrink: 0;
}

.sidebar__mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 9px;
  background: rgba(74, 125, 255, 0.14);
  flex-shrink: 0;
}

.sidebar__name {
  font-size: 1.05rem;
  font-weight: 700;
  color: #ffffff;
  letter-spacing: -0.01em;
  white-space: nowrap;
}

.sidebar__name-accent {
  font-weight: 500;
  color: rgba(255, 255, 255, 0.72);
}

.sidebar__nav {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  padding: 0.75rem;
  overflow-y: auto;
  overflow-x: hidden;
}

.sidebar__item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  height: 2.5rem;
  padding: 0 0.75rem;
  border: none;
  border-radius: 0.6rem;
  background: transparent;
  color: rgba(255, 255, 255, 0.72);
  font-family: var(--font-sans);
  font-size: 0.88rem;
  cursor: pointer;
  white-space: nowrap;
  text-align: left;
  width: 100%;
}

.sidebar__item:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #ffffff;
}

.sidebar__item--active {
  background: rgba(74, 125, 255, 0.18);
  color: #ffffff;
}

.sidebar__item-icon {
  font-size: 1rem;
  width: 1.1rem;
  flex-shrink: 0;
  text-align: center;
}

.sidebar__item-label {
  overflow: hidden;
  text-overflow: ellipsis;
}

.sidebar__footer {
  margin-top: auto;
  flex-shrink: 0;
  padding: 0.75rem;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.sidebar__collapse-toggle {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  height: 2.3rem;
  padding: 0 0.75rem;
  border: none;
  border-radius: 0.6rem;
  background: transparent;
  color: rgba(255, 255, 255, 0.55);
  font-family: var(--font-sans);
  font-size: 0.82rem;
  cursor: pointer;
  white-space: nowrap;
  text-align: left;
  width: 100%;
}

.sidebar__collapse-toggle:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #ffffff;
}

.sidebar__collapse-toggle .pi {
  font-size: 0.95rem;
  width: 1.1rem;
  flex-shrink: 0;
  text-align: center;
}

.sidebar__user {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  height: 2.75rem;
  padding: 0 0.75rem;
  margin-top: 0.3rem;
}

.sidebar__avatar.p-avatar {
  background: rgba(74, 125, 255, 0.22);
  color: #ffffff;
  font-weight: 700;
  font-size: 0.8rem;
  flex-shrink: 0;
  width: 2.25rem;
  height: 2.25rem;
}

.sidebar__user-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.sidebar__user-name {
  font-size: 0.85rem;
  font-weight: 600;
  color: #ffffff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sidebar__user-role {
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.6);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
