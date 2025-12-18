<template>
  <div class="data-page">
    <div class="page-header">
      <h1>数据看板</h1>
      <div class="actions">
        <el-button :loading="loadingAll" @click="reloadAll">
          <el-icon style="margin-right: 6px"><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- Summary cards -->
    <el-row :gutter="16">
      <el-col :span="8">
        <el-card class="stat-card">
          <div class="stat-title">账号</div>
          <div class="stat-value">{{ summary?.accounts?.total ?? '-' }}</div>
          <div class="stat-sub">
            正常：{{ summary?.accounts?.normal ?? '-' }} ｜ 异常：{{ summary?.accounts?.abnormal ?? '-' }}
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="stat-card">
          <div class="stat-title">素材</div>
          <div class="stat-value">{{ summary?.materials?.total ?? '-' }}</div>
          <div class="stat-sub">总大小：{{ summary?.materials?.total_size_mb ?? '-' }} MB</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="stat-card">
          <div class="stat-title">发布任务</div>
          <div class="stat-value">{{ summary?.publish_tasks?.total ?? '-' }}</div>
          <div class="stat-sub">
            成功：{{ summary?.publish_tasks?.success ?? '-' }} ｜ 失败：{{ summary?.publish_tasks?.failed ?? '-' }}
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Charts -->
    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :span="14">
        <el-card>
          <template #header>
            <div class="card-header">
              <div class="card-title">素材上传趋势</div>
              <el-radio-group v-model="trendDays" size="small" @change="fetchTrend">
                <el-radio-button :label="7">近7天</el-radio-button>
                <el-radio-button :label="30">近30天</el-radio-button>
              </el-radio-group>
            </div>
          </template>
          <div ref="trendChartEl" class="chart" />
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card>
          <template #header>
            <div class="card-title">发布明细状态</div>
          </template>
          <div ref="statusChartEl" class="chart" />
        </el-card>
      </el-col>
    </el-row>

    <!-- Filters -->
    <el-card style="margin-top: 16px">
      <el-form :inline="true" :model="filters" class="filter-form">
        <el-form-item label="平台">
          <el-select v-model="filters.platform_type" placeholder="全部" clearable style="width: 160px">
            <el-option label="小红书(1)" :value="1" />
            <el-option label="视频号(2)" :value="2" />
            <el-option label="抖音(3)" :value="3" />
            <el-option label="快手(4)" :value="4" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" clearable style="width: 160px">
            <el-option label="running" value="running" />
            <el-option label="success" value="success" />
            <el-option label="failed" value="failed" />
            <el-option label="created" value="created" />
          </el-select>
        </el-form-item>
        <el-form-item label="日期">
          <el-date-picker
            v-model="filters.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始"
            end-placeholder="结束"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
        <el-form-item label="关键词">
          <el-input v-model="filters.keyword" placeholder="标题/标签" clearable style="width: 220px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="onSearch">
            <el-icon style="margin-right: 6px"><Search /></el-icon>
            查询
          </el-button>
          <el-button @click="onReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- Tasks table -->
    <el-card style="margin-top: 16px">
      <el-table :data="taskList" v-loading="loadingTasks" style="width: 100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="platform_type" label="平台" width="110">
          <template #default="scope">
            <el-tag effect="plain">{{ platformName(scope.row.platform_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="240" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="scope">
            <el-tag :type="taskStatusTagType(scope.row.status)" effect="plain">{{ scope.row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="190" />
        <el-table-column label="明细" width="160">
          <template #default="scope">
            <span>{{ scope.row.items_success || 0 }}/{{ scope.row.items_total || 0 }}</span>
            <span class="muted">（失败 {{ scope.row.items_failed || 0 }}）</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="scope">
            <el-button link type="primary" @click="openDetail(scope.row.id)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <el-pagination
          layout="total, prev, pager, next, sizes"
          :total="pager.total"
          :page-size="pager.page_size"
          :current-page="pager.page"
          :page-sizes="[10, 20, 50]"
          @update:current-page="(p) => changePage(p)"
          @update:page-size="(s) => changePageSize(s)"
        />
      </div>
    </el-card>

    <!-- Detail drawer -->
    <el-drawer v-model="drawerVisible" size="60%" :with-header="true" title="任务详情">
      <div v-if="loadingDetail" class="muted">加载中...</div>

      <template v-else>
        <el-descriptions :column="3" border style="margin-bottom: 12px">
          <el-descriptions-item label="ID">{{ detail?.task?.id }}</el-descriptions-item>
          <el-descriptions-item label="平台">{{ platformName(detail?.task?.platform_type) }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="taskStatusTagType(detail?.task?.status)" effect="plain">{{ detail?.task?.status }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="标题" :span="3">{{ detail?.task?.title }}</el-descriptions-item>
        </el-descriptions>

        <el-table :data="detail?.items || []" style="width: 100%">
          <el-table-column prop="file_path" label="素材" min-width="180" show-overflow-tooltip />
          <el-table-column prop="account_file_path" label="账号文件" min-width="180" show-overflow-tooltip />
          <el-table-column prop="status" label="状态" width="120">
            <template #default="scope">
              <el-tag :type="itemStatusTagType(scope.row.status)" effect="plain">{{ scope.row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="scheduled_at" label="计划时间" width="180" />
          <el-table-column prop="started_at" label="开始" width="180" />
          <el-table-column prop="finished_at" label="结束" width="180" />
          <el-table-column prop="result_msg" label="结果/错误" min-width="220" show-overflow-tooltip />
        </el-table>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Search } from '@element-plus/icons-vue'
import { statsApi } from '@/api/stats'
import { publishApi } from '@/api/publish'

const loadingAll = ref(false)
const loadingTasks = ref(false)
const loadingDetail = ref(false)

const summary = ref(null)
const trendDays = ref(7)
const trendRows = ref([])

const filters = reactive({
  platform_type: undefined,
  status: '',
  keyword: '',
  dateRange: []
})

const pager = reactive({
  page: 1,
  page_size: 10,
  total: 0
})

const taskList = ref([])

const drawerVisible = ref(false)
const detail = ref(null)

const trendChartEl = ref()
const statusChartEl = ref()
let trendChart = null
let statusChart = null
let echartsMod = null

const platformName = (t) => {
  const m = { 1: '小红书', 2: '视频号', 3: '抖音', 4: '快手' }
  return m[t] || String(t ?? '-')
}

const taskStatusTagType = (s) => {
  if (s === 'success') return 'success'
  if (s === 'failed') return 'danger'
  if (s === 'running') return 'warning'
  return 'info'
}

const itemStatusTagType = (s) => {
  if (s === 'success') return 'success'
  if (s === 'failed') return 'danger'
  if (s === 'running') return 'warning'
  if (s === 'scheduled') return 'info'
  return 'info'
}

const fetchSummary = async () => {
  const res = await statsApi.summary()
  summary.value = res.data
}

const fetchTrend = async () => {
  const res = await statsApi.uploadsTrend(trendDays.value)
  trendRows.value = res.data || []
}

const buildTaskParams = () => {
  const params = {
    page: pager.page,
    page_size: pager.page_size
  }
  if (filters.platform_type) params.platform_type = filters.platform_type
  if (filters.status) params.status = filters.status
  if (filters.keyword) params.keyword = filters.keyword
  if (Array.isArray(filters.dateRange) && filters.dateRange.length === 2) {
    params.start_date = filters.dateRange[0]
    params.end_date = filters.dateRange[1]
  }
  return params
}

const fetchTasks = async () => {
  loadingTasks.value = true
  try {
    const res = await publishApi.listTasks(buildTaskParams())
    taskList.value = res.data.items || []
    pager.total = res.data.total || 0
  } finally {
    loadingTasks.value = false
  }
}

const reloadAll = async () => {
  loadingAll.value = true
  try {
    await Promise.all([fetchSummary(), fetchTrend(), fetchTasks()])
  } catch (e) {
    ElMessage.error(e?.message || '加载失败')
  } finally {
    loadingAll.value = false
  }
}

const onSearch = () => {
  pager.page = 1
  fetchTasks()
}

const onReset = () => {
  filters.platform_type = undefined
  filters.status = ''
  filters.keyword = ''
  filters.dateRange = []
  pager.page = 1
  fetchTasks()
}

const changePage = (p) => {
  pager.page = p
  fetchTasks()
}

const changePageSize = (s) => {
  pager.page_size = s
  pager.page = 1
  fetchTasks()
}

const openDetail = async (taskId) => {
  drawerVisible.value = true
  loadingDetail.value = true
  detail.value = null
  try {
    const res = await publishApi.getTask(taskId)
    detail.value = res.data
  } finally {
    loadingDetail.value = false
  }
}

const ensureEcharts = async () => {
  if (echartsMod) return echartsMod
  echartsMod = await import('echarts')
  return echartsMod
}

const renderTrendChart = async () => {
  if (!trendChartEl.value) return
  const echarts = await ensureEcharts()
  if (!trendChart) trendChart = echarts.init(trendChartEl.value)

  const days = trendRows.value.map((r) => r.day)
  const counts = trendRows.value.map((r) => r.upload_count)

  trendChart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 36, right: 16, top: 24, bottom: 28 },
    xAxis: { type: 'category', data: days },
    yAxis: { type: 'value' },
    series: [
      {
        type: 'line',
        data: counts,
        smooth: true,
        areaStyle: {}
      }
    ]
  })
}

const renderStatusChart = async () => {
  if (!statusChartEl.value) return
  const echarts = await ensureEcharts()
  if (!statusChart) statusChart = echarts.init(statusChartEl.value)

  const s = summary.value?.publish_items || {}
  const data = [
    { name: 'success', value: s.success || 0 },
    { name: 'failed', value: s.failed || 0 },
    { name: 'running', value: s.running || 0 },
    { name: 'scheduled', value: s.scheduled || 0 }
  ]

  statusChart.setOption({
    tooltip: { trigger: 'item' },
    legend: { bottom: 0 },
    series: [
      {
        type: 'pie',
        radius: ['40%', '68%'],
        avoidLabelOverlap: true,
        data
      }
    ]
  })
}

const renderCharts = async () => {
  await nextTick()
  await Promise.all([renderTrendChart(), renderStatusChart()])
}

watch(trendRows, renderTrendChart)
watch(summary, renderStatusChart)

const onResize = () => {
  if (trendChart) trendChart.resize()
  if (statusChart) statusChart.resize()
}

onMounted(async () => {
  await reloadAll()
  await renderCharts()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  if (trendChart) trendChart.dispose()
  if (statusChart) statusChart.dispose()
})
</script>

<style lang="scss" scoped>
@use '@/styles/variables.scss' as *;

.data-page {
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

  .stat-card {
    .stat-title {
      color: $text-secondary;
      font-size: 13px;
      margin-bottom: 8px;
    }
    .stat-value {
      font-size: 28px;
      font-weight: 700;
      color: $text-primary;
      line-height: 1.1;
      margin-bottom: 6px;
    }
    .stat-sub {
      color: $text-secondary;
      font-size: 13px;
    }
  }

  .card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .card-title {
    font-weight: 600;
    color: $text-primary;
  }

  .chart {
    height: 320px;
    width: 100%;
  }

  .filter-form {
    :deep(.el-form-item) {
      margin-bottom: 10px;
    }
  }

  .pager {
    display: flex;
    justify-content: flex-end;
    margin-top: 12px;
  }

  .muted {
    color: $text-secondary;
  }
}
</style>


