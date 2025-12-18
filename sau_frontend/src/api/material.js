import { http } from '@/utils/request'

// 素材管理API
export const materialApi = {
  // 获取所有素材
  getAllMaterials: () => {
    return http.get('/getFiles')
  },
  
  // 上传素材
  uploadMaterial: (formData, onUploadProgress) => {
    // 使用http.upload方法，它已经配置了正确的Content-Type
    return http.upload('/uploadSave', formData, onUploadProgress)
  },
  
  // 删除素材
  deleteMaterial: (id) => {
    return http.get(`/deleteFile?id=${id}`)
  },
  
  // 下载素材
  downloadMaterial: (filePath) => {
    const base = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5409'
    const token = encodeURIComponent(localStorage.getItem('token') || '')
    return `${base}/download/${encodeURIComponent(filePath)}?token=${token}`
  },
  
  // 获取素材预览URL
  getMaterialPreviewUrl: (filename) => {
    const base = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5409'
    const token = encodeURIComponent(localStorage.getItem('token') || '')
    return `${base}/getFile?filename=${encodeURIComponent(filename)}&token=${token}`
  }
}