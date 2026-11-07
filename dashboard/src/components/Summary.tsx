import type { HeadsetView } from '../api/protocol.gen'
import type { LiveStatus } from '../api/useLive'
import { isShellApp } from '../lib/format'

/** Сводка сверху: на что оператору обратить внимание. */
export function Summary({ headsets }: { headsets: HeadsetView[] }) {
  const online = headsets.filter((h) => h.online)
  const inGame = online.filter((h) => h.currentPkg && !isShellApp(h.currentPkg)).length
  // шлем или любой подключённый контроллер ниже 20 %
  const lowBattery = online.filter(
    (h) =>
      (h.battery != null && h.battery < 20 && !h.charging) ||
      h.controllers.some((c) => c.connected && c.battery != null && c.battery < 20),
  ).length
  const waiting = online.filter((h) => h.adb === 'waiting_confirmation').length
  const broken = online.filter((h) => h.adb === 'key_missing' || h.adb === 'key_rejected').length

  return (
    <dl className="grid grid-cols-2 gap-3 sm:grid-cols-5">
      <Stat label="Online" value={`${online.length} of ${headsets.length}`} />
      <Stat label="In game" value={inGame} />
      <Stat label="Battery < 20%" hint="Headset or any connected controller" value={lowBattery} alert={lowBattery > 0} />
      <Stat label="Awaiting confirmation" value={waiting} alert={waiting > 0} />
      <Stat label="Need setup" value={broken} alert={broken > 0} />
    </dl>
  )
}

function Stat({
  label,
  value,
  hint,
  alert = false,
}: {
  label: string
  value: number | string
  hint?: string
  alert?: boolean
}) {
  return (
    <div
      className={`rounded-xl border px-4 py-3 ${alert ? 'border-amber-300 bg-amber-50' : 'border-slate-200 bg-white'}`}
      title={hint}
    >
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className={`text-2xl font-semibold ${alert ? 'text-amber-900' : 'text-slate-900'}`}>{value}</dd>
    </div>
  )
}

const STATUS_TEXT: Record<LiveStatus, string> = {
  open: 'Connected to server',
  connecting: 'Connecting to server…',
  closed: 'No connection to server',
}

export function ServerStatus({ status }: { status: LiveStatus }) {
  const dot = status === 'open' ? 'bg-emerald-500' : status === 'connecting' ? 'bg-amber-400' : 'bg-red-500'
  return (
    <span className="inline-flex items-center gap-2 text-sm text-slate-600">
      <span className={`size-2.5 rounded-full ${dot}`} />
      {STATUS_TEXT[status]}
    </span>
  )
}
