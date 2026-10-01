import { defineStore } from 'pinia'

type Role = '管养员' | '巡查员' | '值班管理员'

const STORAGE_KEY = 'session'

type Identity = {
  operator: string
  role: Role
  team: string
  shiftLabel: string
  scope: string
}

const DEFAULT_IDENTITY: Identity = {
  operator: '周敏',
  role: '管养员',
  team: '绿化一班',
  shiftLabel: '白班 08:00-20:00',
  scope: '园林绿化养护管理平台',
}

function loadIdentity(): Identity {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      return { ...DEFAULT_IDENTITY, ...(JSON.parse(raw) as Partial<Identity>) }
    }
  } catch {
    // 本地存储不可用时使用默认值班身份
  }
  return { ...DEFAULT_IDENTITY }
}

export const useSessionStore = defineStore(STORAGE_KEY, {
  state: (): Identity => loadIdentity(),
  getters: {
    canOperate: (state) => state.operator.length > 0,
    isGardener: (state) => state.role === '管养员',
  },
  actions: {
    persist() {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(this.$state))
      } catch {
        // 草稿与身份持久化失败不阻塞页面操作
      }
    },
    setShift(label: string) {
      this.shiftLabel = label
      this.persist()
    },
    setIdentity(payload: { operator: string; role: Role; team: string }) {
      this.operator = payload.operator
      this.role = payload.role
      this.team = payload.team
      this.persist()
    },
  },
})

export type { Role }
