import { useState } from 'react'
import { renameHeadset } from '../api/headsets'
import type { AppInfo, CommandView, ControllerInfo, HeadsetView } from '../api/protocol.gen'
import {
  ADB_STATUS,
  appTitle,
  batteryTone,
  commandLabel,
  commandResult,
  isShellApp,
  timeAgo,
} from '../lib/format'
import { TONE_BADGE, TONE_BAR, TONE_TEXT } from '../lib/tones'

interface Props {
  headset: HeadsetView
  now: number
  selected: boolean
  onToggle: () => void
  lastCommand?: CommandView
}

export function HeadsetCard({ headset: h, now, selected, onToggle, lastCommand }: Props) {
  return (
    <article
      className={`flex flex-col gap-3 rounded-xl border bg-white p-4 shadow-sm transition ${
        selected ? 'border-sky-500 ring-2 ring-sky-200' : 'border-slate-200'
      } ${h.online ? '' : 'opacity-60'}`}
    >
      <header className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 flex-1 items-start gap-2.5">
          <input
            type="checkbox"
            checked={selected}
            onChange={onToggle}
            className="mt-1.5 size-4 shrink-0 cursor-pointer accent-sky-600"
            aria-label={`Select ${h.label}`}
          />
          <div className="min-w-0 flex-1">
            <EditableLabel id={h.id} label={h.label} />
            <span className="block text-xs text-slate-400" title="Serial number">
              {h.serial}
            </span>
          </div>
        </div>
        <OnlineBadge online={h.online} asleep={h.online && h.screenOn === false} lastSeen={h.lastSeen} now={now} />
      </header>

      <BatteryBar level={h.battery} charging={h.charging} showCharging />
      {h.controllers.length > 0 && <Controllers controllers={h.controllers} />}
      <CurrentApp pkg={h.currentPkg} online={h.online} apps={h.apps} guardPkg={h.guardPkg} />
      {h.online && h.screenOn === false ? (
        <div className={`rounded-lg px-2.5 py-1.5 text-xs ring-1 ${TONE_BADGE.muted}`}>
          <p className="font-medium">Asleep: commands unavailable</p>
          <p className="mt-0.5 opacity-80">Wake it with the power button or put it on</p>
        </div>
      ) : (
        h.adb && <AdbBadge status={h.adb} />
      )}
      {lastCommand && <LastCommand command={lastCommand} apps={h.apps} now={now} />}

      <footer className="mt-auto flex flex-wrap gap-x-3 gap-y-1 border-t border-slate-100 pt-2 text-xs text-slate-500">
        {h.temp != null && <span title="Battery temperature">{h.temp.toFixed(1)} °C</span>}
        {h.agentVersion && <span title="Agent version">agent {h.agentVersion}</span>}
      </footer>
    </article>
  )
}

/** Название шлема: нажать, чтобы изменить; Enter — сохранить, Esc — отменить. */
function EditableLabel({ id, label }: { id: string; label: string }) {
  const [draft, setDraft] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const save = async () => {
    if (draft == null || saving) return
    const value = draft.trim()
    if (value === '' || value === label) {
      setDraft(null)
      setError(null)
      return
    }
    setSaving(true)
    try {
      await renameHeadset(id, value)
      setDraft(null)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setSaving(false)
    }
  }

  if (draft == null) {
    return (
      <button
        onClick={() => setDraft(label)}
        title="Rename"
        className="group flex max-w-full items-center gap-1.5 text-left"
      >
        <span className="truncate text-lg font-semibold text-slate-900">{label}</span>
        <span aria-hidden className="text-sm text-slate-300 group-hover:text-slate-500">
          ✎
        </span>
      </button>
    )
  }
  return (
    <>
      <input
        autoFocus
        value={draft}
        maxLength={64}
        disabled={saving}
        aria-label="Headset name"
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => void save()}
        onFocus={(e) => e.target.select()}
        onKeyDown={(e) => {
          if (e.key === 'Enter') void save()
          if (e.key === 'Escape') {
            setDraft(null)
            setError(null)
          }
        }}
        className="w-full rounded border border-sky-400 px-1 text-lg font-semibold text-slate-900 outline-none"
      />
      {error && <span className="block text-xs text-red-700">{error}</span>}
    </>
  )
}

function OnlineBadge({
  online,
  asleep,
  lastSeen,
  now,
}: {
  online: boolean
  asleep: boolean
  lastSeen: string | null
  now: number
}) {
  const look = asleep
    ? { box: 'bg-indigo-50 text-indigo-800', dot: 'bg-indigo-500' }
    : online
      ? { box: 'bg-emerald-50 text-emerald-800', dot: 'bg-emerald-500' }
      : { box: 'bg-slate-100 text-slate-600', dot: 'bg-slate-400' }
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ${look.box}`}
      title={lastSeen ? `Last signal: ${new Date(lastSeen).toLocaleString('en-GB')}` : undefined}
    >
      <span className={`size-2 rounded-full ${look.dot}`} />
      {asleep ? 'asleep' : online ? 'online' : `offline · ${timeAgo(lastSeen, now)}`}
    </span>
  )
}

function BatteryBar({
  label = 'Battery',
  level,
  charging,
  off = false,
  title,
  showCharging = false,
}: {
  label?: string
  level: number | null
  charging: boolean | null
  off?: boolean
  title?: string
  showCharging?: boolean
}) {
  if (level == null) return <p className="text-sm text-slate-400">{label}: no data</p>
  const tone = off ? 'muted' : batteryTone(level, charging)
  return (
    <div title={title}>
      <div className="mb-1 flex justify-between text-sm">
        <span className="text-slate-600">{label}</span>
        <span className={`font-medium ${TONE_TEXT[tone]}`}>
          {level}%{off ? ' · off' : ''}
          {showCharging && (charging ? ' · charging' : ' · not charging')}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-slate-100">
        <div className={`h-full rounded-full ${TONE_BAR[tone]}`} style={{ width: `${level}%` }} />
      </div>
    </div>
  )
}

/** Заряд контроллеров — такие же полоски, как у шлема. Выключенный — серый, с последним известным зарядом. */
function Controllers({ controllers }: { controllers: ControllerInfo[] }) {
  return (
    <>
      {(['left', 'right'] as const).map((side) => {
        const c = controllers.find((x) => x.side === side)
        if (!c) return null
        const name = side === 'left' ? 'Left controller' : 'Right controller'
        return (
          <BatteryBar
            key={side}
            label={name}
            level={c.battery}
            charging={false}
            off={!c.connected}
            title={c.connected ? undefined : `${name} is off or out of range. Showing the last known charge`}
          />
        )
      })}
    </>
  )
}

function CurrentApp({
  pkg,
  online,
  apps,
  guardPkg,
}: {
  pkg: string | null
  online: boolean
  apps: AppInfo[]
  guardPkg: string | null
}) {
  let text: string
  let muted = true
  if (!online) text = '—'
  else if (!pkg) text = 'Unknown'
  else if (isShellApp(pkg)) text = `Not in a game · ${appTitle(pkg)}`
  else {
    text = appTitle(pkg, apps)
    muted = false
  }
  return (
    <p className="text-sm" title={pkg ?? undefined}>
      <span className="text-slate-600">Now: </span>
      <span className={muted ? 'text-slate-500' : 'font-medium text-slate-900'}>{text}</span>
      {online && guardPkg && (
        <span
          className="ml-1.5 font-medium text-sky-800"
          title="Protection is on: the player returns to the game, the headset does not sleep, the power button does not turn it off"
        >
          🛡{guardPkg !== pkg && ` ${appTitle(guardPkg, apps)}`}
        </span>
      )}
    </p>
  )
}

function AdbBadge({ status }: { status: NonNullable<HeadsetView['adb']> }) {
  const s = ADB_STATUS[status]
  return (
    <div className={`rounded-lg px-2.5 py-1.5 text-xs ring-1 ${TONE_BADGE[s.tone]}`} title={`ADB: ${status}`}>
      <p className="font-medium">{s.label}</p>
      {s.hint && <p className="mt-0.5 opacity-80">{s.hint}</p>}
    </div>
  )
}

function LastCommand({ command, apps, now }: { command: CommandView; apps: AppInfo[]; now: number }) {
  const r = commandResult(command)
  return (
    <p className="text-xs text-slate-500" title={command.detail ?? undefined}>
      {commandLabel(command, apps)} · <span className={`font-medium ${TONE_TEXT[r.tone]}`}>{r.text}</span>
      <span className="text-slate-400"> · {timeAgo(command.createdAt, now)}</span>
    </p>
  )
}
