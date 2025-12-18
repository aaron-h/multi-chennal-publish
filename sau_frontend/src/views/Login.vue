<template>
  <div class="login-page">
    <div class="login-card">
      <div class="brand">
        <img src="/wanqutui-icon.svg" alt="万渠推" class="logo" />
        <div class="title">万渠推 · 后台登录</div>
        <div class="subtitle">Multi-channels publish</div>
      </div>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent>
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="请输入用户名" autocomplete="username" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" placeholder="请输入密码" autocomplete="current-password" show-password />
        </el-form-item>

        <el-button type="primary" :loading="loading" style="width: 100%" @click="onSubmit">
          登录
        </el-button>

        <div class="hint">
          <span>首次启动可用默认管理员：</span>
          <code>admin / admin123</code>
        </div>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { http } from '@/utils/request'

const router = useRouter()
const route = useRoute()

const formRef = ref()
const loading = ref(false)

const form = reactive({
  username: '',
  password: ''
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const onSubmit = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    loading.value = true
    try {
      const res = await http.post('/auth/login', {
        username: form.username,
        password: form.password
      })

      const token = res?.data?.access_token
      if (!token) throw new Error('登录失败：未返回 token')

      localStorage.setItem('token', token)

      ElMessage.success('登录成功')

      const redirect = route.query.redirect
      if (typeof redirect === 'string' && redirect) {
        router.replace(redirect)
      } else {
        router.replace('/')
      }
    } catch (e) {
      ElMessage.error(e?.message || '登录失败')
    } finally {
      loading.value = false
    }
  })
}
</script>

<style lang="scss" scoped>
@use '@/styles/variables.scss' as *;

.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: radial-gradient(1200px 500px at 20% 10%, rgba(34, 197, 94, 0.18), transparent 55%),
    radial-gradient(900px 420px at 80% 20%, rgba(16, 185, 129, 0.14), transparent 60%),
    linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
}

.login-card {
  width: 420px;
  max-width: 100%;
  background: #fff;
  border-radius: 14px;
  box-shadow: 0 20px 60px rgba(2, 6, 23, 0.12);
  padding: 22px 22px 18px;
}

.brand {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 14px;

  .logo {
    width: 44px;
    height: 44px;
    margin-bottom: 10px;
  }

  .title {
    font-size: 18px;
    font-weight: 650;
    color: $text-primary;
    letter-spacing: 0.2px;
    margin-bottom: 4px;
  }

  .subtitle {
    font-size: 12px;
    color: $text-secondary;
  }
}

.hint {
  margin-top: 12px;
  font-size: 12px;
  color: $text-secondary;

  code {
    padding: 2px 6px;
    border-radius: 6px;
    background: #f1f5f9;
    color: #0f172a;
  }
}
</style>
