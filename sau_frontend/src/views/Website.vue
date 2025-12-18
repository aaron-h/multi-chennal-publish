<template>
  <div class="website-page">
    <div class="page-header">
      <h1>网站 / 系统</h1>
      <div class="actions">
        <el-button type="danger" plain @click="onLogout">退出登录</el-button>
      </div>
    </div>

    <el-row :gutter="16">
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-title">快速入口</div>
          </template>

          <el-space direction="vertical" alignment="start" :size="10">
            <el-link :underline="false" href="https://github.com/" target="_blank">项目主页（可替换为你的仓库地址）</el-link>
            <el-link :underline="false" href="https://vitejs.dev/" target="_blank">Vite 文档</el-link>
            <el-link :underline="false" href="https://element-plus.org/" target="_blank">Element Plus 文档</el-link>
          </el-space>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-title">系统配置</div>
          </template>

          <el-descriptions :column="1" border>
            <el-descriptions-item label="API Base URL">
              <code>{{ apiBaseUrl }}</code>
            </el-descriptions-item>
            <el-descriptions-item label="前端环境">
              <code>{{ mode }}</code>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :span="24">
        <el-card>
          <template #header>
            <div class="card-title">当前登录用户</div>
          </template>

          <div v-if="loading" class="muted">加载中...</div>
          <el-descriptions v-else :column="3" border>
            <el-descriptions-item label="ID">{{ me?.id ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="用户名">{{ me?.username ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="角色">{{ me?.role ?? '-' }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { authApi } from '@/api/auth'

const router = useRouter()

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5409'
const mode = import.meta.env.MODE

const me = ref(null)
const loading = ref(false)

const fetchMe = async () => {
  loading.value = true
  try {
    const res = await authApi.me()
    me.value = res.data
  } catch (e) {
    // request interceptor will handle 401 redirect
  } finally {
    loading.value = false
  }
}

const onLogout = async () => {
  try {
    await authApi.logout()
  } catch (e) {
    // ignore
  }
  localStorage.removeItem('token')
  ElMessage.success('已退出登录')
  router.replace('/login')
}

onMounted(fetchMe)
</script>

<style lang="scss" scoped>
@use '@/styles/variables.scss' as *;

.website-page {
  .page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;

    h1 {
      font-size: 24px;
      color: $text-primary;
      margin: 0;
    }
  }

  .card-title {
    font-weight: 600;
    color: $text-primary;
  }

  code {
    padding: 2px 6px;
    border-radius: 6px;
    background: #f1f5f9;
    color: #0f172a;
  }

  .muted {
    color: $text-secondary;
  }
}
</style>


