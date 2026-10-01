/** 统一请求封装：拼后端地址、带当前值班人身份、抛网络错误。 */
const API_BASE = import.meta.env.VITE_API_BASE ?? ''

const SESSION_KEY = 'session'

function identityHeaders(): Record<string, string> {
  // 从 localStorage 直接读取，避免 api 层与 pinia store 产生循环依赖
  // HTTP 头只允许 ASCII，中文身份字段需做百分号编码（后端解码）
  const encode = (value: string) => encodeURIComponent(value || '')
  try {
    const raw = localStorage.getItem(SESSION_KEY)
    if (raw) {
      const session = JSON.parse(raw) as Record<string, string>
      return {
        'X-Operator-Name': encode(session.operator ?? ''),
        'X-Operator-Role': encode(session.role ?? ''),
        'X-Operator-Team': encode(session.team ?? ''),
      }
    }
  } catch {
    // 本地存储不可用时降级为匿名，后端写操作会返回 403
  }
  return {}
}

export function request(path: string, init?: RequestInit): Promise<Response> {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`
  return fetch(url, {
    headers: { 'Content-Type': 'application/json', ...identityHeaders(), ...(init?.headers ?? {}) },
    ...init,
  }).catch((error: unknown) => {
    const detail = error instanceof Error ? error.message : '请求未送达'
    throw new Error(`接口请求失败：${detail}`)
  })
}

export async function fetchJson<T>(path: string): Promise<T> {
  const response = await request(path)
  if (!response.ok) {
    throw new Error(`接口返回 ${response.status}，数据未更新`)
  }
  return (await response.json()) as T
}
