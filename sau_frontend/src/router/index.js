import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { public: true }
  },
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('../views/Dashboard.vue')
  },
  {
    path: '/account-management',
    name: 'AccountManagement',
    component: () => import('../views/AccountManagement.vue')
  },
  {
    path: '/material-management',
    name: 'MaterialManagement',
    component: () => import('../views/MaterialManagement.vue')
  },
  {
    path: '/publish-center',
    name: 'PublishCenter',
    component: () => import('../views/PublishCenter.vue')
  },
  {
    path: '/about',
    name: 'About',
    component: () => import('../views/About.vue')
  },
  {
    path: '/website',
    name: 'Website',
    component: () => import('../views/Website.vue')
  },
  {
    path: '/data',
    name: 'Data',
    component: () => import('../views/Data.vue')
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

router.beforeEach((to) => {
  if (to.meta && to.meta.public) return true
  const token = localStorage.getItem('token')
  if (token) return true
  return { path: '/login', query: { redirect: to.fullPath } }
})

export default router