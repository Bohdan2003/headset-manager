import { useEffect, useState } from 'react'
import { logout } from './api/auth'
import { sendCommand, type CommandRequest } from './api/commands'
import { useLive } from './api/useLive'
import { ActionBar } from './components/ActionBar'
import { HeadsetCard } from './components/HeadsetCard'
import { StatsPage } from './components/StatsPage'
import { SetupPage } from './components/SetupPage'
import { ServerStatus, Summary } from './components/Summary'
import { byLabel } from './lib/format'

/** Текущее время, обновляется раз в 5 с — для «офлайн · 3 мин назад». */
function useNow(intervalMs = 5000) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), intervalMs)
    return () => clearInterval(t)
  }, [intervalMs])
  return now
}

type Tab = 'headsets' | 'stats' | 'setup'

/** Вкладка хранится в адресе (#stats), чтобы на неё можно было дать ссылку. */
function useTab(): [Tab, (t: Tab) => void] {
  const read = (): Tab =>
    location.hash.startsWith('#stats') ? 'stats' : location.hash === '#setup' ? 'setup' : 'headsets'
  const [tab, setTab] = useState<Tab>(read)
  useEffect(() => {
    const onHash = () => setTab(read())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  return [tab, (t) => (location.hash = t === 'headsets' ? '' : t)]
}

export default function App() {
  const { headsets, lastCommand, status, addCommands } = useLive()
  const now = useNow()
  const [tab, setTab] = useTab()
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [error, setError] = useState<string | null>(null)

  const sorted = [...headsets].sort(byLabel)
  const selected = sorted.filter((h) => selectedIds.has(h.id))

  const toggle = (id: string) =>
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  const send = async (req: Omit<CommandRequest, 'headsetIds'>) => {
    setError(null)
    const [first, ...rest] = selected.map((h) => h.id)
    if (!first) return
    try {
      addCommands(await sendCommand({ ...req, headsetIds: [first, ...rest] }))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-6 py-3">
          <div className="flex items-center gap-6">
            <h1 className="text-xl font-semibold text-slate-900">Arena</h1>
            <nav className="flex gap-1">
              {(
                [
                  ['headsets', 'Headsets'],
                  ['stats', 'Statistics'],
                  ['setup', 'Setup'],
                ] as const
              ).map(([value, label]) => (
                <button
                  key={value}
                  onClick={() => setTab(value)}
                  className={`rounded-md px-3 py-1.5 text-sm font-medium ${
                    tab === value ? 'bg-slate-100 text-slate-900' : 'text-slate-500 hover:text-slate-900'
                  }`}
                >
                  {label}
                </button>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-4">
            <ServerStatus status={status} />
            <button onClick={() => void logout()} className="text-sm text-slate-500 hover:text-slate-900">
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-7xl flex-1 flex-col gap-6 px-6 py-6">
        {status === 'closed' && (
          <p className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
            No connection to the server. The data below may be out of date. Reconnecting…
          </p>
        )}
        {tab === 'stats' && <StatsPage />}
        {tab === 'setup' && <SetupPage headsets={headsets} />}
        {tab === 'headsets' && error && (
          <p className="flex justify-between rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
            {error}
            <button onClick={() => setError(null)} className="ml-4 underline">
              dismiss
            </button>
          </p>
        )}

        {tab === 'headsets' && <Summary headsets={headsets} />}

        {tab === 'headsets' && sorted.length > 0 && (
          <div className="flex gap-4 text-sm">
            <button
              onClick={() => setSelectedIds(new Set(sorted.filter((h) => h.online).map((h) => h.id)))}
              className="text-sky-700 underline hover:text-sky-900"
            >
              Select all online
            </button>
            {selectedIds.size > 0 && (
              <button onClick={() => setSelectedIds(new Set())} className="text-slate-500 underline hover:text-slate-800">
                Clear selection
              </button>
            )}
          </div>
        )}

        {tab !== 'headsets' ? null : sorted.length === 0 ? (
          <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center text-slate-500">
            {status === 'open'
              ? 'No headsets yet. A headset appears here after setup with provision.sh.'
              : 'Loading…'}
          </p>
        ) : (
          <section className="grid grid-cols-[repeat(auto-fill,minmax(min(22rem,100%),1fr))] gap-4">
            {sorted.map((h) => (
              <HeadsetCard
                key={h.id}
                headset={h}
                now={now}
                selected={selectedIds.has(h.id)}
                onToggle={() => toggle(h.id)}
                lastCommand={lastCommand[h.id]}
              />
            ))}
          </section>
        )}
      </main>

      {tab === 'headsets' && selected.length > 0 && (
        <ActionBar selected={selected} onSend={send} onClear={() => setSelectedIds(new Set())} />
      )}
    </div>
  )
}
