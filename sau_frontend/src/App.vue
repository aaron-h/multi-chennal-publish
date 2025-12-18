<template>
  <div id="app">
    <router-view v-if="!showLayout" />
    <el-container v-else>
      <el-aside :width="isCollapse ? '64px' : '200px'">
        <div class="sidebar">
          <div class="logo">
            <img src="/wanqutui-icon.svg" alt="万渠推" class="logo-img">
            <h2 v-show="!isCollapse">万渠推</h2>
          </div>
          <el-menu
            :router="true"
            :default-active="activeMenu"
            :collapse="isCollapse"
            class="sidebar-menu"
            background-color="#053d2a"
            text-color="rgba(255, 255, 255, 0.88)"
            active-text-color="#22c55e"
          >
            <el-menu-item index="/">
              <el-icon><HomeFilled /></el-icon>
              <span>首页</span>
            </el-menu-item>
            <el-menu-item index="/account-management">
              <el-icon><User /></el-icon>
              <span>账号管理</span>
            </el-menu-item>
            <el-menu-item index="/material-management">
              <el-icon><Picture /></el-icon>
              <span>素材管理</span>
            </el-menu-item>
            <el-menu-item index="/publish-center">
              <el-icon><Upload /></el-icon>
              <span>发布中心</span>
            </el-menu-item>
            <el-menu-item index="/website">
              <el-icon><Monitor /></el-icon>
              <span>网站</span>
            </el-menu-item>
            <el-menu-item index="/data">
              <el-icon><DataAnalysis /></el-icon>
              <span>数据</span>
            </el-menu-item>
          </el-menu>
        </div>
      </el-aside>
      <el-container>
        <el-header>
          <div class="header-content">
            <div class="header-left">
              <el-icon class="toggle-sidebar" @click="toggleSidebar"><Fold /></el-icon>
            </div>
            <div class="header-right">
              <!-- 账号信息已移除 -->
            </div>
          </div>
        </el-header>
        <el-main>
          <router-view />
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { 
  HomeFilled, User, Monitor, DataAnalysis, 
  Fold, Picture, Upload
} from '@element-plus/icons-vue'

const route = useRoute()

const showLayout = computed(() => route.path !== '/login')

// 当前激活的菜单项
const activeMenu = computed(() => {
  return route.path
})

// 侧边栏折叠状态
const isCollapse = ref(false)

// 切换侧边栏折叠状态
const toggleSidebar = () => {
  isCollapse.value = !isCollapse.value
}
</script>

<style lang="scss" scoped>
@use '@/styles/variables.scss' as *;

#app {
  min-height: 100vh;
}

.el-container {
  height: 100vh;
}

.el-aside {
  background: linear-gradient(180deg, var(--wqt-sidebar-bg-2) 0%, var(--wqt-sidebar-bg) 100%);
  color: #fff;
  height: 100vh;
  overflow: hidden;
  transition: width 0.3s;
  
  .sidebar {
    display: flex;
    flex-direction: column;
    height: 100%;
    
    .logo {
      height: 60px;
      padding: 0 16px;
      display: flex;
      align-items: center;
      background: linear-gradient(180deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.02) 100%);
      overflow: hidden;
      
      .logo-img {
        width: 32px;
        height: 32px;
        margin-right: 12px;
      }
      
      h2 {
        color: #fff;
        font-size: 16px;
        font-weight: 600;
        white-space: nowrap;
        margin: 0;
      }
    }
    
    .sidebar-menu {
      border-right: none;
      flex: 1;

      /* Element Plus menu is rendered by a child component; use :deep */
      :deep(.el-menu) {
        background: transparent !important;
        border-right: none;
      }

      :deep(.el-menu-item) {
        display: flex;
        align-items: center;
        color: var(--wqt-sidebar-text) !important;
      }

      :deep(.el-menu-item:hover) {
        background-color: rgba(255, 255, 255, 0.06) !important;
      }

      :deep(.el-menu-item.is-active) {
        background-color: var(--wqt-sidebar-active-bg) !important;
        color: var(--wqt-sidebar-active) !important;
      }

      :deep(.el-menu-item .el-icon) {
        margin-right: 10px;
        font-size: 18px;
        color: inherit;
      }
    }
  }
}

.el-header {
  background-color: #fff;
  box-shadow: 0 1px 6px rgba(34, 197, 94, 0.10);
  padding: 0;
  height: 60px;
  
  .header-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
    height: 100%;
    padding: 0 16px;
    
    .header-left {
      .toggle-sidebar {
        font-size: 20px;
        cursor: pointer;
        color: $text-regular;
        
        &:hover {
          color: $primary-color;
        }
      }
    }
    
    .header-right {
      .user-dropdown {
        display: flex;
        align-items: center;
        cursor: pointer;
        
        .username {
          margin: 0 8px;
          color: $text-regular;
        }
        
        .el-icon {
          font-size: 12px;
          color: $text-secondary;
        }
      }
    }
  }
}

.el-main {
  background-color: $bg-color-page;
  padding: 20px;
  overflow-y: auto;
}
</style>
