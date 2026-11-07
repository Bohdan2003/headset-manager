import { apiFetch } from './http'
import { useEffect, useState } from 'react'
import type { Stats } from './rest.gen'

export type StatsPeriod = Stats['period']

/** Статистика за период; обновляется раз в минуту, пока страница открыта. */
export function useStats(period: StatsPeriod) {
  const [data, setData] = useState<Stats | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const r = await apiFetch(`/api/stats?period=${period}`)
        if (!r.ok) throw new Error(`server responded ${r.status}`)
        const json = (await r.json()) as Stats
        if (!cancelled) {
          setData(json)
          setError(null)
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e))
      }
    }
    void load()
    const t = setInterval(load, 60_000)
    return () => {
      cancelled = true
      clearInterval(t)
    }
  }, [period])

  return { data, error }
}
