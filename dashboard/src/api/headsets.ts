import { apiFetch } from './http'
/** Новое название шлема. Обновлённый шлем придёт всем дашбордам через /live. */
export async function renameHeadset(id: string, label: string): Promise<void> {
  const r = await apiFetch(`/api/headsets/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ label }),
  })
  if (!r.ok) throw new Error(`Could not rename the headset (${r.status})`)
}
