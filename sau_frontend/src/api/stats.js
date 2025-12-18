import { http } from '@/utils/request'

// very small in-memory cache for summary/trend
const cache = new Map()
const ttlMs = 10_000

function cacheKey(url, params) {
  return `${url}?${JSON.stringify(params || {})}`
}

async function cachedGet(url, params) {
  const key = cacheKey(url, params)
  const now = Date.now()
  const hit = cache.get(key)
  if (hit && now - hit.t < ttlMs) return hit.v

  const v = await http.get(url, params)
  cache.set(key, { t: now, v })
  return v
}

export const statsApi = {
  summary() {
    return cachedGet('/stats/summary')
  },
  uploadsTrend(days = 7) {
    return cachedGet('/stats/uploads_trend', { days })
  }
}
