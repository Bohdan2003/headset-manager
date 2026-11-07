import { apiFetch } from './http'
import type { CommandCreate, CommandView } from './rest.gen'

export type CommandRequest = Omit<CommandCreate, 'ttlS'> & { ttlS?: number }

/**
 * Отправить команду нескольким шлемам. Ответ — по команде на шлем (sent или failed/offline);
 * дальше статусы приходят через /live.
 */
export async function sendCommand(req: CommandRequest): Promise<CommandView[]> {
  const r = await apiFetch('/api/commands', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ttlS: 10, ...req }),
  })
  if (!r.ok) {
    const text = await r.text()
    throw new Error(`The server rejected the command (${r.status}): ${text.slice(0, 200)}`)
  }
  return (await r.json()) as CommandView[]
}
