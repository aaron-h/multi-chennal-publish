import { http } from '@/utils/request'

export const publishApi = {
  listTasks(params) {
    return http.get('/publish_tasks', params)
  },
  getTask(taskId) {
    return http.get(`/publish_tasks/${taskId}`)
  }
}
