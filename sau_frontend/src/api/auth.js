import { http } from '@/utils/request'

export const authApi = {
  login(data) {
    return http.post('/auth/login', data)
  },
  register(data) {
    return http.post('/auth/register', data)
  },
  me() {
    return http.get('/auth/me')
  },
  logout() {
    return http.post('/auth/logout')
  }
}
