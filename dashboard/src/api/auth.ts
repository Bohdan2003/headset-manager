import { signalLoggedOut } from './http'
import type { AuthStatus } from './rest.gen'

export async function fetchAuthStatus(): Promise<AuthStatus> {
  const r = await fetch('/api/auth/status')
  if (!r.ok) throw new Error(`server responded ${r.status}`)
  return (await r.json()) as AuthStatus
}

async function submit(path: string, password: string): Promise<void> {
  const r = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password }),
  })
  if (r.ok) return
  const body = (await r.json().catch(() => null)) as { detail?: unknown } | null
  const detail = typeof body?.detail === 'string' ? body.detail : `server responded ${r.status}`
  throw new Error(detail.charAt(0).toUpperCase() + detail.slice(1))
}

export const login = (password: string) => submit('/api/auth/login', password)
export const setupPassword = (password: string) => submit('/api/auth/setup', password)

export async function logout(): Promise<void> {
  await fetch('/api/auth/logout', { method: 'POST' })
  signalLoggedOut()
}
