<template>
  <section class="page" data-module="plot">
    <header class="page-head">
      <div>
        <h2>绿地台账管理</h2>
        <p class="page-desc">接管与移交按 待接管 → 已接管 → 已移交 依次推进；只有本部门管养员、且为本班组接管的绿地才能改动。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">接管登记</button>
        <button class="btn" type="button" @click="exportRows">导出绿地台账清单</button>
      </div>
    </header>

    <!-- 当前值班身份：切换班组/角色验证接管权限 -->
    <div class="identity-bar">
      <span>当前值班：{{ session.operator }}（{{ session.role }} · {{ session.team }}）</span>
      <label>
        切换身份
        <select
          :value="`${session.role}|${session.team}|${session.operator}`"
          @change="switchIdentity(($event.target as HTMLSelectElement).value)"
        >
          <option value="管养员|绿化一班|周敏">周敏 · 管养员 · 绿化一班</option>
          <option value="管养员|绿化二班|吴磊">吴磊 · 管养员 · 绿化二班</option>
          <option value="巡查员|绿化一班|陈静">陈静 · 巡查员 · 绿化一班</option>
        </select>
      </label>
    </div>

    <div class="stat-row">
      <article class="stat-card">
        <span class="stat-label">待接管</span>
        <strong class="stat-value">{{ stats['待接管'] ?? 0 }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">已接管</span>
        <strong class="stat-value">{{ stats['已接管'] ?? 0 }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">已移交</span>
        <strong class="stat-value">{{ stats['已移交'] ?? 0 }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">在管面积（㎡）</span>
        <strong class="stat-value">{{ formatArea(stats['在管面积']) }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>绿地编号</span>
        <input v-model="filters.keyword" placeholder="按绿地编号检索" />
      </label>
      <label class="filter-item">
        <span>所属区域</span>
        <input v-model="filters.zone" placeholder="按所属区域检索" />
      </label>
      <label class="filter-item">
        <span>接管状态</span>
        <select v-model="filters.status">
          <option value="">全部</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
      <div class="view-switch">
        <button type="button" :class="['btn', viewMode === 'list' ? 'primary' : '']" @click="viewMode = 'list'">列表视图</button>
        <button type="button" :class="['btn', viewMode === 'zones' ? 'primary' : '']" @click="viewMode = 'zones'">分区视图</button>
      </div>
    </form>

    <table v-if="viewMode === 'list'" class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>管养班组</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">
            <template v-if="column === '面积'">{{ formatArea(row[column]) }}</template>
            <template v-else-if="column === '绿地编号'">
              <button class="link" type="button" @click="showDetail(row)">{{ display(row[column]) }}</button>
            </template>
            <template v-else>{{ display(row[column]) }}</template>
          </td>
          <td>{{ display(row['管养班组']) }}</td>
          <td class="row-actions">
            <template v-if="nextAction(row)">
              <button
                class="link"
                type="button"
                :disabled="!canRunAction(row)"
                :title="actionBlockReason(row)"
                @click="runAction(nextAction(row)!, row)"
              >
                {{ nextAction(row) }}
              </button>
            </template>
            <span v-else class="muted-text">已移交，不可再接</span>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 2" class="empty-state">暂无绿地台账数据，可先做接管登记</td>
        </tr>
      </tbody>
    </table>

    <table v-else class="data-table">
      <thead>
        <tr>
          <th>所属区域</th>
          <th>绿地数量</th>
          <th>在管数量</th>
          <th>面积合计（㎡）</th>
          <th>区域明细</th>
        </tr>
      </thead>
      <tbody>
        <template v-for="zone in zones" :key="zone['所属区域']">
          <tr>
            <td>{{ zone['所属区域'] }}</td>
            <td>{{ zone['绿地数量'] }}</td>
            <td>{{ zone['在管数量'] }}</td>
            <td>{{ formatArea(zone['面积合计']) }}</td>
            <td class="row-actions">
              <button class="link" type="button" @click="toggleZone(zone['所属区域'])">
                {{ expandedZones.includes(zone['所属区域']) ? '收起明细' : '查看明细' }}
              </button>
            </td>
          </tr>
          <tr v-for="item in expandedZoneItems(zone)" :key="`${zone['所属区域']}-${item.id}`" class="zone-detail-row">
            <td colspan="5">
              {{ item['绿地编号'] }} · {{ item['绿地名称'] }} · {{ item['绿地状态'] }} ·
              面积 {{ formatArea(item['面积']) }} ㎡ · 植被群落：{{ display(item['植被群落']) }}
            </td>
          </tr>
        </template>
        <tr v-if="!zones.length">
          <td colspan="5" class="empty-state">当前过滤条件下没有分区数据</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条绿地台账记录</span>
      <span v-if="message" :class="messageOk ? 'ok-text' : 'error-text'">{{ message }}</span>
    </footer>

    <!-- 接管登记表单：缺项在表单内逐项标红，提交被后端拦下时显示具体缺项 -->
    <div v-if="formOpen" class="modal-mask" @click.self="closeCreate">
      <div class="modal">
        <h3>接管登记</h3>
        <p class="page-desc">带 * 为必填；未填完退出后，再次打开会恢复之前填写的内容。</p>
        <div class="form-grid">
          <label v-for="field in formFields" :key="field" class="form-item">
            <span>{{ field }}<i v-if="field !== '管养班组'">*</i></span>
            <input v-model="form[field]" :placeholder="`请输入${field}`" />
            <em v-if="fieldErrors.includes(field)" class="error-text">缺少{{ field }}</em>
          </label>
        </div>
        <footer class="modal-foot">
          <button class="btn ghost" type="button" @click="clearDraft">清空草稿</button>
          <button class="btn" type="button" @click="closeCreate">退出暂存</button>
          <button class="btn primary" type="button" @click="submitCreate">提交接管登记</button>
        </footer>
      </div>
    </div>

    <!-- 绿地详情：面积、植被群落等字段与列表行同源 -->
    <div v-if="detail" class="modal-mask" @click.self="detail = null">
      <div class="modal">
        <h3>绿地详情 · {{ detail['绿地编号'] }}</h3>
        <dl class="detail-grid">
          <template v-for="field in detailFields" :key="field">
            <dt>{{ field }}</dt>
            <dd v-if="field === '面积'">{{ formatArea(detail[field]) }} ㎡</dd>
            <dd v-else>{{ display(detail[field]) }}</dd>
          </template>
        </dl>
        <footer class="modal-foot">
          <button class="btn primary" type="button" @click="detail = null">关闭</button>
        </footer>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'

import { request } from '@/api/client'
import { useSessionStore, type Role } from '@/stores/session'

type Row = Record<string, string | number | null>
type ZoneBucket = {
  所属区域: string
  绿地数量: number
  在管数量: number
  面积合计: number
  items: Row[]
}
type FormState = Record<string, string>

const ENDPOINT = '/api/plot'
const columns = ['绿地编号', '绿地名称', '所属区域', '绿地类型', '面积', '植被群落', '管养等级', '绿地状态']
const formFields = ['绿地编号', '绿地名称', '所属区域', '绿地类型', '面积', '植被群落', '管养等级', '管养班组']
const detailFields = [...formFields, '绿地状态', '接管人', '接管日期', '移交人', '移交日期']
const statuses = ['待接管', '已接管', '已移交']
const DRAFT_KEY = 'plot:takeover:draft'

const session = useSessionStore()

const rows = ref<Row[]>([])
const zones = ref<ZoneBucket[]>([])
const expandedZones = ref<string[]>([])
const total = ref(0)
const message = ref('')
const messageOk = ref(false)
const viewMode = ref<'list' | 'zones'>('list')
const filters = reactive({ keyword: '', zone: '', status: '' })

const stats = ref<Record<string, number>>({})

const formOpen = ref(false)
const form = reactive<FormState>({})
const fieldErrors = ref<string[]>([])
const detail = ref<Row | null>(null)

function display(value: unknown): string {
  return value === null || value === undefined || String(value).trim() === '' ? '—' : String(value)
}

function formatArea(value: unknown): string {
  const area = typeof value === 'number' ? value : Number.parseFloat(String(value ?? ''))
  if (!Number.isFinite(area)) {
    return '—'
  }
  return Number.isInteger(area) ? String(area) : area.toFixed(2)
}

function nextAction(row: Row): string | null {
  switch (row['绿地状态']) {
    case '待接管':
      return '接管登记'
    case '已接管':
      return '办理移交'
    default:
      return null
  }
}

function canRunAction(row: Row): boolean {
  return session.isGardener && session.team === String(row['管养班组'] ?? '')
}

function actionBlockReason(row: Row): string {
  if (!session.isGardener) {
    return '只有本部门管养员才能改动接管信息'
  }
  if (session.team !== String(row['管养班组'] ?? '')) {
    return `该绿地由${row['管养班组']}接管，其他班组无权改动`
  }
  return ''
}

function resetFilters() {
  filters.keyword = ''
  filters.zone = ''
  filters.status = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function switchIdentity(token: string) {
  const [role, team, operator] = token.split('|')
  session.setIdentity({ role: role as Role, team, operator })
  flash(`已切换为 ${operator}（${role} · ${team}）`, true)
}

// ---------- 接管登记表单 + 草稿暂存 ----------
function emptyForm(): FormState {
  return Object.fromEntries(formFields.map((field) => [field, '']))
}

function saveDraft() {
  if (!formOpen.value) {
    return
  }
  try {
    localStorage.setItem(DRAFT_KEY, JSON.stringify(form))
  } catch {
    // 草稿写不进本地存储时不影响正常提交
  }
}

watch(form, saveDraft, { deep: true })

function openCreate() {
  fieldErrors.value = []
  const draft = emptyForm()
  try {
    const raw = localStorage.getItem(DRAFT_KEY)
    if (raw) {
      Object.assign(draft, JSON.parse(raw) as Partial<FormState>)
    }
  } catch {
    // 草稿损坏时从空表单开始
  }
  Object.keys(form).forEach((key) => delete form[key])
  Object.assign(form, draft)
  formOpen.value = true
}

function closeCreate() {
  formOpen.value = false
}

function clearDraft() {
  Object.assign(form, emptyForm())
  fieldErrors.value = []
  try {
    localStorage.removeItem(DRAFT_KEY)
  } catch {
    // 忽略本地存储异常
  }
}

async function submitCreate() {
  fieldErrors.value = formFields
    .filter((field) => field !== '管养班组' && !String(form[field] ?? '').trim())
  if (fieldErrors.value.length) {
    flash(`请先补齐：${fieldErrors.value.join('、')}`, false)
    return
  }
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: { ...form } }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      const detailText: string = payload?.detail ?? payload?.message ?? '接管登记未生效'
      markMissingFromMessage(String(detailText))
      flash(String(detailText), false)
      return
    }
    clearDraft()
    formOpen.value = false
    flash(payload.message ?? '接管登记已提交', true)
    await reload()
  } catch (error) {
    flash(error instanceof Error ? error.message : '接管登记失败', false)
  }
}

function markMissingFromMessage(text: string) {
  if (!text.startsWith('缺少必填字段')) {
    return
  }
  fieldErrors.value = formFields.filter((field) => text.includes(field))
}

// ---------- 列表 / 分区 / 统计 ----------
function buildQuery(): string {
  const params = new URLSearchParams()
  if (filters.keyword) {
    params.set('keyword', filters.keyword)
  }
  if (filters.zone) {
    params.set('zone', filters.zone)
  }
  if (filters.status) {
    params.set('status', filters.status)
  }
  return params.toString()
}

async function reload() {
  message.value = ''
  const query = buildQuery()
  try {
    const [listResponse, statsResponse] = await Promise.all([
      request(`${ENDPOINT}?${query}`),
      request(`${ENDPOINT}/stats`),
    ])
    if (!listResponse.ok) {
      throw new Error('绿地列表读取失败')
    }
    const payload = await listResponse.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    if (statsResponse.ok) {
      stats.value = await statsResponse.json()
    }
    if (viewMode.value === 'zones') {
      await reloadZones()
    }
  } catch (error) {
    flash(error instanceof Error ? error.message : '绿地台账列表读取失败', false)
  }
}

async function reloadZones() {
  const params = new URLSearchParams()
  if (filters.keyword) {
    params.set('keyword', filters.keyword)
  }
  try {
    const response = await request(`${ENDPOINT}/zones?${params.toString()}`)
    if (!response.ok) {
      throw new Error('分区数据读取失败')
    }
    const payload = await response.json()
    zones.value = payload.zones ?? []
  } catch (error) {
    flash(error instanceof Error ? error.message : '分区视图读取失败', false)
  }
}

watch(viewMode, (mode) => {
  if (mode === 'zones') {
    void reloadZones()
  }
})

function toggleZone(zoneName: string) {
  if (expandedZones.value.includes(zoneName)) {
    expandedZones.value = expandedZones.value.filter((name) => name !== zoneName)
  } else {
    expandedZones.value = [...expandedZones.value, zoneName]
  }
}

function expandedZoneItems(zone: ZoneBucket): Row[] {
  // 分区明细直接用接口返回的同一批行，面积与详情不会串位
  return expandedZones.value.includes(zone['所属区域']) ? zone.items : []
}

async function showDetail(row: Row) {
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) {
      const payload = await response.json().catch(() => null)
      throw new Error(payload?.detail ?? '绿地详情读取失败')
    }
    detail.value = await response.json()
  } catch (error) {
    flash(error instanceof Error ? error.message : '绿地详情读取失败', false)
  }
}

async function runAction(action: string, row: Row) {
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok || !payload?.ok) {
      flash(payload?.detail ?? payload?.message ?? '接管动作未生效，请稍后重试', false)
      return
    }
    flash(payload.message ?? '操作成功', true)
    await reload()
  } catch (error) {
    flash(error instanceof Error ? error.message : '绿地台账操作失败', false)
  }
}

function flash(text: string, ok: boolean) {
  message.value = text
  messageOk.value = ok
}

onMounted(reload)
</script>
