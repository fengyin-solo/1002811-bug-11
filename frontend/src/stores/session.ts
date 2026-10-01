import { defineStore } from 'pinia'

export type OperatorRole = '管养员' | '巡查员' | '管理员'

export interface Operator {
  name: string
  role: OperatorRole
  department: string
}

/** 预置几位值班身份，方便核对“只有本部门管养员能改动接管信息”的边界。 */
export const OPERATOR_PRESETS: Operator[] = [
  { name: '周敏', role: '管养员', department: '河东管养一班' },
  { name: '李建国', role: '管养员', department: '城中管养班' },
  { name: '赵芳', role: '管养员', department: '南湖管养班' },
  { name: '王强', role: '巡查员', department: '巡查中队' },
  { name: '值班管理员', role: '管理员', department: '调度中心' },
]

const STORAGE_KEY = 'greenery.session.operator'

function loadOperator(): Operator {
  const fallback = OPERATOR_PRESETS[0]
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return fallback
    const parsed = JSON.parse(raw) as Partial<Operator>
    if (parsed && parsed.name && parsed.role && parsed.department) {
      return parsed as Operator
    }
  } catch {
    /* 本地缓存损坏时回退默认身份 */
  }
  return fallback
}

export const useSessionStore = defineStore('session', {
  state: () => ({
    operator: loadOperator(),
    shiftLabel: '白班 08:00-20:00',
    scope: '园林绿化养护管理平台',
  }),
  getters: {
    canOperate: (state) => state.operator.name.length > 0,
    isGardener: (state) => state.operator.role === '管养员',
  },
  actions: {
    setShift(label: string) {
      this.shiftLabel = label
    },
    setOperator(operator: Operator) {
      this.operator = { ...operator }
      try {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(operator))
      } catch {
        /* 隐私模式等场景写不进缓存时，本次会话内仍生效 */
      }
    },
  },
})
