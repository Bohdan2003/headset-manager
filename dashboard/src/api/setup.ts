import { apiFetch } from './http'
import { useCallback, useEffect, useState } from 'react'
import type { SetupInfo, SetupRequest } from './rest.gen'

export type SetupResult =
  | { state: 'loading' }
  | { state: 'remote' }
  | { state: 'error'; message: string }
  | { state: 'ok'; info: SetupInfo }

/** Подключённые шлемы; обновляется каждые 3 с, пока вкладка открыта. */
export function useSetup() {
  const [result, setResult] = useState<SetupResult>({ state: 'loading' })

  const load = useCallback(async () => {
    try {
      const r = await apiFetch('/api/setup')
      if (r.status === 403) setResult({ state: 'remote' })
      else if (!r.ok) setResult({ state: 'error', message: `server responded ${r.status}` })
      else setResult({ state: 'ok', info: (await r.json()) as SetupInfo })
    } catch (e) {
      setResult({ state: 'error', message: e instanceof Error ? e.message : String(e) })
    }
  }, [])

  useEffect(() => {
    const first = setTimeout(() => void load(), 0)
    const t = setInterval(() => void load(), 3000)
    return () => {
      clearTimeout(first)
      clearInterval(t)
    }
  }, [load])

  return { result, reload: load }
}

export async function startSetupJob(req: SetupRequest): Promise<void> {
  const r = await apiFetch('/api/setup/jobs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!r.ok) {
    const body = (await r.json().catch(() => null)) as { detail?: string } | null
    throw new Error(body?.detail ?? `server responded ${r.status}`)
  }
}

export async function updateOverWifi(headsetIds: string[]): Promise<void> {
  const r = await apiFetch('/api/setup/update-wifi', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ headsetIds }),
  })
  if (!r.ok) throw new Error(`server responded ${r.status}`)
}
