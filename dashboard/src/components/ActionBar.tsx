import { useMemo, useState } from 'react'
import type { CommandRequest } from '../api/commands'
import type { HeadsetView } from '../api/protocol.gen'
import { games, isShellApp } from '../lib/format'

interface Props {
  selected: HeadsetView[]
  onSend: (req: Omit<CommandRequest, 'headsetIds'>) => Promise<void>
  onClear: () => void
}

type ToggleState = 'on' | 'off' | 'mixed'

/** Состояние переключателя по выбранным шлемам (офлайн не учитываем — их состояние неизвестно). */
function toggleState(headsets: HeadsetView[], isOn: (h: HeadsetView) => boolean): ToggleState {
  const online = headsets.filter((h) => h.online)
  if (online.length === 0) return 'off'
  const on = online.filter(isOn).length
  return on === 0 ? 'off' : on === online.length ? 'on' : 'mixed'
}

/** Панель команд для выбранных шлемов. Видна, пока выбран хотя бы один шлем. */
export function ActionBar({ selected, onSend, onClear }: Props) {
  // Игры, установленные хотя бы на одном выбранном шлеме; у каждой — на скольких она есть
  const options = useMemo(() => {
    const byPkg = new Map<string, { title: string; count: number }>()
    for (const h of selected) {
      for (const g of games(h.apps)) {
        const entry = byPkg.get(g.package) ?? { title: g.title, count: 0 }
        entry.count++
        byPkg.set(g.package, entry)
      }
    }
    return [...byPkg.entries()]
      .map(([pkg, v]) => ({ pkg, ...v }))
      .sort((a, b) => a.title.localeCompare(b.title, 'en'))
  }, [selected])

  const [pkg, setPkg] = useState('')
  const [busy, setBusy] = useState(false)
  const chosen = options.find((o) => o.pkg === pkg)
  const offline = selected.filter((h) => !h.online).length
  // Спящий шлем команд не выполняет, разбудить его с дашборда нельзя
  const asleepCount = selected.filter((h) => h.online && h.screenOn === false).length
  const reachable = selected.filter((h) => h.online && h.screenOn !== false)
  const none = reachable.length === 0
  const adbReady = reachable.filter((h) => h.adb === 'ready').length
  const inGame = reachable.filter((h) => h.currentPkg && !isShellApp(h.currentPkg)).length

  const guard = toggleState(reachable, (h) => h.guardPkg != null)

  const run = async (req: Omit<CommandRequest, 'headsetIds'>) => {
    setBusy(true)
    try {
      await onSend(req)
    } finally {
      setBusy(false)
    }
  }

  const count = selected.length === 1 ? selected[0].label : `${selected.length} headsets`

  return (
    <div className="sticky bottom-0 z-10 border-t border-slate-200 bg-white/95 shadow-[0_-4px_12px_rgba(0,0,0,0.05)] backdrop-blur">
      <div className="mx-auto flex max-w-7xl flex-col gap-3 px-6 py-3">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
          <span className="font-semibold text-slate-900">Selected: {selected.length}</span>
          {offline > 0 && <span className="text-amber-700">offline {offline}</span>}
          {asleepCount > 0 && (
            <span className="text-amber-700">
              asleep {asleepCount}: wake with the power button or by putting on
            </span>
          )}
          <button onClick={onClear} className="text-slate-500 underline hover:text-slate-800">
            clear selection
          </button>
          {!none && adbReady < reachable.length && (
            <>
              <span className="text-xs text-slate-500">
                Close, restart and power commands available on {adbReady} of {reachable.length}
              </span>
              <Button
                disabled={busy || none}
                onClick={() => run({ cmd: 'request_access', params: {} })}
                title="Show the “Allow wireless debugging” window in the headset again. Press “Always allow on this network” there"
              >
                Request access
              </Button>
            </>
          )}
        </div>

        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto]">
          <Group title="Game">
            <select
              value={pkg}
              onChange={(e) => setPkg(e.target.value)}
              className="min-w-0 flex-1 rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm"
            >
              <option value="">— select a game —</option>
              {options.map((o) => (
                <option key={o.pkg} value={o.pkg}>
                  {o.title}
                  {o.count < selected.length ? ` (on ${o.count} of ${selected.length})` : ''}
                </option>
              ))}
            </select>
            <Button
              primary
              disabled={busy || none || !chosen}
              // если защита включена — новая игра сразу под защитой
              onClick={() => run({ cmd: 'launch', params: { pkg, guard: guard === 'on' } })}
            >
              Launch
            </Button>
            <Button
              disabled={busy || none || inGame === 0}
              onClick={() => run({ cmd: 'restart_game', params: {} })}
              title="Close the current game and launch it again right away; Protection stays on"
            >
              Restart
            </Button>
            <Button
              disabled={busy || none}
              onClick={() => run({ cmd: 'close_game', params: {} })}
              title="Fully close the current game and show our menu"
            >
              Close
            </Button>
          </Group>

          <Group title="Protection">
            <Toggle
              label={none ? 'Unavailable' : guard !== 'off' ? 'On' : inGame === 0 ? 'Requires a running game' : 'Off'}
              state={guard}
              disabled={busy || none || (guard === 'off' && inGame === 0)}
              title={
                'While on: the headset does not sleep when taken off; the player returns to the game; a long power press ' +
                'does not turn it off, and a short press restarts the game. Does not work without a connection to the server'
              }
              onChange={(on) => run({ cmd: 'guard', params: on ? { current: true } : {} })}
            />
          </Group>
        </div>

        <Group title="Power">
          <Button disabled={busy || none} onClick={() => run({ cmd: 'sleep', params: {} })} title="Turn off the headset screen. It can only be woken with its power button or by putting it on">
            Sleep
          </Button>
          <Button
            danger
            disabled={busy || none}
            onClick={() => {
              const msg =
                `Reboot ${count}?\n\n` +
                'After the reboot, closing games and power commands will again need ' +
                '“Always allow on this network” in each headset.'
              if (window.confirm(msg)) void run({ cmd: 'reboot', params: {} })
            }}
          >
            Reboot
          </Button>
          <Button
            danger
            disabled={busy || none}
            onClick={() => {
              const msg = `Turn off ${count}?\n\nIt can only be turned back on with the power button on the headset.`
              if (window.confirm(msg)) void run({ cmd: 'power_off', params: {} })
            }}
          >
            Turn off
          </Button>
        </Group>
      </div>
    </div>
  )
}

/** Блок панели с подписью: команды одного смысла вместе. */
function Group({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex min-w-0 items-center gap-3 rounded-lg bg-slate-50 px-3 py-2">
      <h3 className="w-16 shrink-0 text-xs font-semibold text-slate-500">{title}</h3>
      <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">{children}</div>
    </section>
  )
}

/** Переключатель «вкл/выкл»; при разном состоянии на выбранных шлемах — «частично», нажатие включает. */
function Toggle({
  label,
  state,
  disabled,
  title,
  onChange,
}: {
  label: string
  state: ToggleState
  disabled?: boolean
  title?: string
  onChange: (on: boolean) => void
}) {
  const on = state === 'on'
  return (
    <label
      className={`flex items-center gap-2 text-sm ${disabled ? 'cursor-not-allowed opacity-40' : 'cursor-pointer'}`}
      title={title}
    >
      <button
        type="button"
        role="switch"
        aria-checked={state === 'mixed' ? 'mixed' : on}
        disabled={disabled}
        onClick={() => onChange(!on)}
        className={`relative h-6 w-11 shrink-0 rounded-full transition ${
          on ? 'bg-sky-600' : state === 'mixed' ? 'bg-sky-300' : 'bg-slate-300'
        }`}
      >
        <span
          className={`absolute top-0.5 size-5 rounded-full bg-white shadow transition-all ${
            on ? 'left-[22px]' : state === 'mixed' ? 'left-[11px]' : 'left-0.5'
          }`}
        />
      </button>
      <span className="text-slate-800">
        {label}
        {state === 'mixed' && <span className="text-slate-500"> · partial</span>}
      </span>
    </label>
  )
}

function Button({
  primary = false,
  danger = false,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { primary?: boolean; danger?: boolean }) {
  const look = primary
    ? 'bg-sky-600 text-white hover:bg-sky-700'
    : danger
      ? 'border border-red-300 bg-white text-red-700 hover:bg-red-50'
      : 'border border-slate-300 bg-white text-slate-800 hover:bg-slate-50'
  return (
    <button
      {...props}
      className={`rounded-lg px-3 py-1.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-40 ${look}`}
    />
  )
}
