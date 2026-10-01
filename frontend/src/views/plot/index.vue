<template>
  <section class="page" data-module="plot">
    <header class="page-head">
      <div>
        <h2>绿地台账管理</h2>
        <p class="page-desc">围绕接管与移交维护绿地台账：缺项逐项点明，状态只能按 待接管 → 已接管 → 已移交 推进。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记绿地</button>
        <button class="btn" type="button" @click="exportRows">导出绿地台账清单</button>
      </div>
    </header>

    <div class="view-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab"
        :class="{ active: activeTab === tab.key }"
        type="button"
        @click="switchTab(tab.key)"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- 列表视图 -->
    <div v-show="activeTab === 'list'">
      <div class="stat-row">
        <article v-for="item in stats" :key="item.label" class="stat-card">
          <span class="stat-label">{{ item.label }}</span>
          <strong class="stat-value">{{ item.value }}</strong>
        </article>
      </div>

      <form class="filter-bar" @submit.prevent="reload">
        <label class="filter-item">
          <span>绿地编号</span>
          <input v-model="keyword" placeholder="按绿地编号检索" />
        </label>
        <label class="filter-item">
          <span>所属区域</span>
          <input v-model="zoneFilter" placeholder="按所属区域检索" />
        </label>
        <label class="filter-item">
          <span>接管状态</span>
          <select v-model="statusFilter">
            <option value="">全部</option>
            <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
          </select>
        </label>
        <button class="btn" type="submit">查询</button>
        <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
      </form>

      <table class="data-table">
        <thead>
          <tr>
            <th v-for="column in columns" :key="column">{{ column }}</th>
            <th>接管状态</th>
            <th>接管部门/管养员</th>
            <th>可执行动作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="String(row.id)">
            <td v-for="column in columns" :key="column">{{ displayCell(row, column) }}</td>
            <td>
              <span class="status-tag" :data-status="row.status">{{ row.status || '—' }}</span>
            </td>
            <td>{{ ownerText(row) }}</td>
            <td class="row-actions">
              <button class="link" type="button" @click="openEdit(row)">补全信息</button>
              <button
                v-if="row.status === '待接管'"
                class="link"
                type="button"
                :disabled="!store.isGardener"
                :title="store.isGardener ? '' : '仅本部门管养员可接管'"
                @click="runAction('接管登记', row)"
              >
                接管登记
              </button>
              <button
                v-if="row.status === '已接管'"
                class="link"
                type="button"
                :disabled="!canManage(row)"
                :title="canManage(row) ? '' : '仅接管部门的管养员可移交'"
                @click="runAction('确认移交', row)"
              >
                确认移交
              </button>
              <span v-if="row.status === '已移交'" class="muted-text">已移交，不可再接</span>
            </td>
          </tr>
          <tr v-if="!rows.length">
            <td :colspan="columns.length + 3" class="empty-state">暂无符合条件的绿地，可先登记绿地</td>
          </tr>
        </tbody>
      </table>

      <footer class="page-foot">
        <span>共 {{ total }} 条绿地台账记录</span>
        <span v-if="message" :class="messageTone">{{ message }}</span>
      </footer>
    </div>

    <!-- 分区视图 -->
    <div v-show="activeTab === 'zones'">
      <p class="page-desc">各分区面积直接汇总自绿地明细，点「查看明细」可与详情逐项核对。</p>
      <table class="data-table">
        <thead>
          <tr>
            <th v-for="column in zoneColumns" :key="column">{{ column }}</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="zone in zones" :key="String(zone['所属区域'])">
            <td v-for="column in zoneColumns" :key="column">{{ formatZoneCell(zone, column) }}</td>
            <td>
              <button class="link" type="button" @click="openZoneDetail(zone)">查看明细</button>
            </td>
          </tr>
          <tr v-if="!zones.length">
            <td :colspan="zoneColumns.length + 1" class="empty-state">暂无分区数据</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 登记 / 补全弹窗 -->
    <div v-if="formVisible" class="modal-mask" @click.self="closeForm">
      <div class="modal">
        <h3 class="modal-title">{{ formMode === 'create' ? '登记绿地' : `补全信息 · ${form.绿地编号 || ''}` }}</h3>
        <p class="page-desc">
          未提交就退出，已填内容会保留在本机；下次打开同一编号继续填写。
        </p>
        <div v-if="formError" class="form-error">{{ formError }}</div>
        <div class="form-grid">
          <label v-for="field in formFields" :key="field" class="form-item">
            <span>{{ field }}<em v-if="requiredSet.has(field)">*</em></span>
            <input
              v-model="form[field]"
              :type="field === '面积' ? 'text' : 'text'"
              :placeholder="field === '面积' ? '数字，单位平方米' : `请输入${field}`"
            />
          </label>
        </div>
        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="closeForm">稍后再填（保留草稿）</button>
          <button v-if="hasDraft" class="btn" type="button" @click="discardDraft">清除草稿</button>
          <button class="btn primary" type="button" @click="submitForm">
            {{ formMode === 'create' ? '提交登记' : '保存补全' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 分区明细弹窗：面积与列表/详情同源 -->
    <div v-if="zoneDetailVisible" class="modal-mask" @click.self="zoneDetailVisible = false">
      <div class="modal wide">
        <h3 class="modal-title">{{ zoneDetailTitle }}</h3>
        <table class="data-table">
          <thead>
            <tr>
              <th v-for="column in columns" :key="column">{{ column }}</th>
              <th>接管状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in zoneDetailRows" :key="String(row.id)">
              <td v-for="column in columns" :key="column">{{ displayCell(row, column) }}</td>
              <td>{{ row.status || '—' }}</td>
            </tr>
          </tbody>
        </table>
        <p class="reconcile">
          明细面积合计：<strong>{{ formatArea(zoneDetailArea) }}</strong> ㎡，
          分区视图读数：<strong>{{ formatArea(zoneDetailZone?.['面积合计']) }}</strong> ㎡
          <span :class="zoneDetailArea === Number(zoneDetailZone?.['面积合计']) ? 'ok-text' : 'error-text'">
            （{{ zoneDetailArea === Number(zoneDetailZone?.['面积合计']) ? '一致' : '不一致' }}）
          </span>
        </p>
        <div class="modal-actions">
          <button class="btn primary" type="button" @click="zoneDetailVisible = false">关闭</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'
import { useSessionStore } from '@/stores/session'

type Row = Record<string, string | number | null>
type ZoneRow = Record<string, string | number | null>

const ENDPOINT = '/api/plot'
const store = useSessionStore()

const columns = ['绿地编号', '绿地名称', '所属区域', '绿地类型', '面积', '植被群落', '管养等级', '绿地状态']
const formFields = columns
const requiredSet = new Set(['绿地编号', '绿地名称', '所属区域', '绿地类型', '面积', '植被群落', '管养等级'])
const statuses = ['待接管', '已接管', '已移交']
const zoneColumns = ['所属区域', '绿地数量', '待接管', '已接管', '已移交', '面积合计', '在管面积']

const tabs = [
  { key: 'list', label: '接管列表' },
  { key: 'zones', label: '分区视图' },
] as const

type TabKey = (typeof tabs)[number]['key']

const activeTab = ref<TabKey>('list')
const rows = ref<Row[]>([])
const zones = ref<ZoneRow[]>([])
const total = ref(0)
const message = ref('')
const messageTone = ref('muted-text')

const keyword = ref('')
const zoneFilter = ref('')
const statusFilter = ref('')

const stats = computed(() => {
  const summary = { 待接管: 0, 已接管: 0, 已移交: 0 }
  for (const row of rows.value) {
    const status = String(row.status ?? '')
    if (status in summary) summary[status as keyof typeof summary] += 1
  }
  return [
    { label: '待接管绿地', value: summary.待接管 },
    { label: '已接管绿地', value: summary.已接管 },
    { label: '已移交绿地', value: summary.已移交 },
    { label: '当前页在管面积（㎡）', value: formatArea(managedAreaOnPage()) },
  ]
})

function managedAreaOnPage(): number {
  return rows.value
    .filter((row) => row.status === '已接管')
    .reduce((sum, row) => sum + (toNumber(row['面积']) ?? 0), 0)
}

// ---- 表格展示：缺项显示占位，不让整列/整块留白 -----------------------------

function isMissing(value: unknown): boolean {
  return value === null || value === undefined || String(value).trim() === ''
}

function displayCell(row: Row, column: string): string {
  const value = row[column]
  if (isMissing(value)) return '—'
  if (column === '面积') return `${formatArea(value)} ㎡`
  return String(value)
}

function ownerText(row: Row): string {
  const dept = row['接管部门']
  const keeper = row['管养员']
  if (isMissing(dept) && isMissing(keeper)) return '—'
  return `${isMissing(dept) ? '—' : dept} / ${isMissing(keeper) ? '—' : keeper}`
}

function canManage(row: Row): boolean {
  if (!store.isGardener) return false
  const dept = row['接管部门']
  // 待接管时本部门管养员都可操作；已接管后只有接管部门能继续移交。
  return isMissing(dept) || dept === store.operator.department
}

function toNumber(value: unknown): number | null {
  if (value === null || value === undefined || String(value).trim() === '') return null
  const num = Number(String(value).replace(/,/g, ''))
  return Number.isFinite(num) ? num : null
}

function formatArea(value: unknown): string {
  const num = typeof value === 'number' ? value : toNumber(value)
  if (num === null) return '—'
  return num.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}

function formatZoneCell(zone: ZoneRow, column: string): string {
  if (column === '面积合计' || column === '在管面积') {
    return `${formatArea(zone[column])} ㎡`
  }
  return String(zone[column] ?? '—')
}

// ---- 查询 ------------------------------------------------------------------

function resetFilters() {
  keyword.value = ''
  zoneFilter.value = ''
  statusFilter.value = ''
  void reload()
}

async function switchTab(tab: TabKey) {
  activeTab.value = tab
  message.value = ''
  if (tab === 'zones') await loadZones()
  else await reload()
}

async function reload() {
  message.value = ''
  const params = new URLSearchParams()
  if (keyword.value.trim()) params.set('keyword', keyword.value.trim())
  if (zoneFilter.value.trim()) params.set('zone', zoneFilter.value.trim())
  if (statusFilter.value) params.set('status', statusFilter.value)
  try {
    const response = await request(`${ENDPOINT}?${params.toString()}`)
    const payload = await response.json()
    if (!response.ok) throw new Error('绿地列表读取失败')
    rows.value = Array.isArray(payload.items) ? payload.items : []
    total.value = Number(payload.total ?? rows.value.length)
  } catch (error) {
    messageTone.value = 'error-text'
    message.value = error instanceof Error ? error.message : '绿地列表读取失败'
  }
}

async function loadZones() {
  try {
    const response = await request(`${ENDPOINT}/zones`)
    const payload = await response.json()
    if (!response.ok) throw new Error('分区视图读取失败')
    zones.value = Array.isArray(payload.items) ? payload.items : []
  } catch (error) {
    messageTone.value = 'error-text'
    message.value = error instanceof Error ? error.message : '分区视图读取失败'
  }
}

// ---- 动作 ------------------------------------------------------------------

async function runAction(action: string, row: Row) {
  message.value = ''
  if (!store.isGardener) {
    messageTone.value = 'error-text'
    message.value = `当前岗位「${store.operator.role}」无权${action}，仅本部门管养员可操作`
    return
  }
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({
        values: { action, operator: { ...store.operator } },
      }),
    })
    const payload = await response.json()
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.message || '操作未生效')
    }
    await Promise.all([reload(), activeTab.value === 'zones' ? loadZones() : null])
    // 成功提示放在刷新之后设置：reload 开头会清空旧消息。
    messageTone.value = 'ok-text'
    message.value = payload.message
  } catch (error) {
    messageTone.value = 'error-text'
    message.value = error instanceof Error ? error.message : '操作失败'
  }
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

// ---- 登记 / 补全表单（含草稿留存） -----------------------------------------

type FormState = Record<string, string>

const DRAFT_PREFIX = 'greenery.plot.draft.'

const formVisible = ref(false)
const formMode = ref<'create' | 'edit'>('create')
const editingId = ref<number | null>(null)
const form = ref<FormState>(emptyForm())
const formError = ref('')
const hasDraft = ref(false)

function emptyForm(): FormState {
  return Object.fromEntries(formFields.map((field) => [field, '']))
}

function draftKey(_code: string, id: number | null): string {
  // 新建草稿固定一个键：哪怕登记时已填了编号，退出再进来也能找回；
  // 补全草稿按记录 id 区分，互不串内容。
  return DRAFT_PREFIX + (formMode.value === 'edit' && id !== null ? `id:${id}` : 'code:new')
}

function scanDraft(code: string, id: number | null): boolean {
  try {
    return window.localStorage.getItem(draftKey(code, id)) !== null
  } catch {
    return false
  }
}

function openCreate() {
  formMode.value = 'create'
  editingId.value = null
  form.value = emptyForm()
  formError.value = ''
  hasDraft.value = scanDraft('', null)
  if (hasDraft.value) hydrateDraft(draftKey('', null))
  formVisible.value = true
}

function openEdit(row: Row) {
  formMode.value = 'edit'
  editingId.value = Number(row.id)
  form.value = Object.fromEntries(
    formFields.map((field) => [field, row[field] === null || row[field] === undefined ? '' : String(row[field])]),
  )
  formError.value = ''
  hasDraft.value = scanDraft(String(row['绿地编号'] ?? ''), editingId.value)
  if (hasDraft.value) hydrateDraft(draftKey(String(row['绿地编号'] ?? ''), editingId.value))
  formVisible.value = true
}

function hydrateDraft(key: string) {
  try {
    const raw = window.localStorage.getItem(key)
    if (!raw) return
    const draft = JSON.parse(raw) as Partial<FormState>
    for (const field of formFields) {
      if (typeof draft[field] === 'string') form.value[field] = draft[field]
    }
  } catch {
    /* 草稿损坏就忽略 */
  }
}

function saveDraft() {
  const key = draftKey('', editingId.value)
  try {
    window.localStorage.setItem(key, JSON.stringify(form.value))
    hasDraft.value = true
  } catch {
    /* 写不进缓存不阻断关闭 */
  }
}

function discardDraft() {
  try {
    window.localStorage.removeItem(draftKey('', editingId.value))
  } catch {
    /* ignore */
  }
  hasDraft.value = false
  if (formMode.value === 'create') form.value = emptyForm()
}

function closeForm() {
  // 中途退出：把已填内容留在本机，回来还能接着填。
  saveDraft()
  formVisible.value = false
}

async function submitForm() {
  formError.value = ''
  const missing = formFields.filter((field) => requiredSet.has(field) && !form.value[field].trim())
  if (missing.length) {
    formError.value = `还缺以下必填项：${missing.join('、')}`
    return
  }

  // 植被群落等字段在移交环节丢失，本质是提交时没带上：表单始终提交全字段。
  const values: Record<string, unknown> = Object.fromEntries(
    formFields.map((field) => [field, form.value[field].trim()]),
  )
  if (formMode.value === 'edit') {
    // 修改接管信息要带操作人，后端按岗位与部门鉴权。
    values.operator = { ...store.operator }
  }
  const url = formMode.value === 'edit' ? `${ENDPOINT}/${editingId.value}` : ENDPOINT
  const method = formMode.value === 'edit' ? 'PUT' : 'POST'

  try {
    const response = await request(url, { method, body: JSON.stringify({ values }) })
    const payload = await response.json()
    if (!response.ok || payload.ok === false) {
      formError.value = payload.message || '提交失败'
      return
    }
    // 提交成功后清掉对应草稿（含重复编号场景返回已有记录的情况）。
    discardDraft()
    formVisible.value = false
    await Promise.all([reload(), activeTab.value === 'zones' ? loadZones() : null])
    messageTone.value = 'ok-text'
    message.value = payload.message
  } catch (error) {
    formError.value = error instanceof Error ? error.message : '提交失败，请稍后重试'
  }
}

// ---- 分区明细核对 ----------------------------------------------------------

const zoneDetailVisible = ref(false)
const zoneDetailRows = ref<Row[]>([])
const zoneDetailZone = ref<ZoneRow | null>(null)

const zoneDetailTitle = computed(() =>
  zoneDetailZone.value ? `${zoneDetailZone.value['所属区域']} · 绿地明细` : '',
)
const zoneDetailArea = computed(() =>
  Number(
    zoneDetailRows.value
      .reduce((sum, row) => sum + (toNumber(row['面积']) ?? 0), 0)
      .toFixed(2),
  ),
)

async function openZoneDetail(zone: ZoneRow) {
  zoneDetailZone.value = zone
  zoneDetailRows.value = []
  const params = new URLSearchParams({ zone: String(zone['所属区域']) })
  const response = await request(`${ENDPOINT}?${params.toString()}&size=200`)
  const payload = await response.json()
  zoneDetailRows.value = Array.isArray(payload.items) ? payload.items : []
  zoneDetailVisible.value = true
}

onMounted(reload)
</script>

<style scoped>
.view-tabs { display: flex; gap: 4px; margin-bottom: 12px; }
.tab { border: 1px solid var(--border); background: #fff; padding: 6px 16px; cursor: pointer; border-radius: 6px 6px 0 0; }
.tab.active { background: var(--brand); color: #fff; border-color: var(--brand); }
.muted-text { color: var(--muted); font-size: 12px; }
.ok-text { color: #15803d; font-size: 12px; }
.status-tag { padding: 1px 8px; border-radius: 10px; font-size: 12px; }
.status-tag[data-status='待接管'] { background: #fef3c7; color: #92400e; }
.status-tag[data-status='已接管'] { background: #dcfce7; color: #166534; }
.status-tag[data-status='已移交'] { background: #e2e8f0; color: #475569; }
.link:disabled { color: #94a3b8; cursor: not-allowed; }

.modal-mask { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.45); display: flex; align-items: center; justify-content: center; z-index: 20; }
.modal { background: #fff; border-radius: 10px; padding: 20px 24px; width: 680px; max-height: 86vh; overflow: auto; }
.modal.wide { width: 960px; }
.modal-title { margin: 0 0 8px; font-size: 16px; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 16px; margin-top: 12px; }
.form-item span { display: block; font-size: 12px; color: var(--muted); margin-bottom: 4px; }
.form-item em { color: #b42318; font-style: normal; margin-left: 2px; }
.form-item input { width: 100%; padding: 6px 8px; border: 1px solid var(--border); border-radius: 6px; }
.form-error { margin-top: 10px; background: #fef2f2; border: 1px solid #fecaca; color: #b42318; padding: 8px 10px; border-radius: 6px; font-size: 13px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
.reconcile { font-size: 13px; color: var(--muted); margin-top: 10px; }
</style>
