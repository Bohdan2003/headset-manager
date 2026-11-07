import { useState } from 'react'
import { startSetupJob, updateOverWifi, useSetup } from '../api/setup'
import type { HeadsetView } from '../api/protocol.gen'
import type { FleetHeadset, SetupDevice, SetupJob, SetupRequest } from '../api/rest.gen'
import type { Tone } from '../lib/format'
import { TONE_BADGE } from '../lib/tones'

const STATUS: Record<string, { label: string; tone: Tone; hint?: string }> = {
  not_installed: { label: 'Agent not installed', tone: 'warn' },
  outdated: { label: 'Update available', tone: 'warn' },
  current: { label: 'Up to date', tone: 'ok' },
  newer: { label: 'Newer than this program', tone: 'muted', hint: 'The headset has a newer agent than this program' },
  unauthorized: {
    label: 'Needs permission',
    tone: 'warn',
    hint: 'Put on the headset and allow USB debugging for this computer',
  },
  offline: { label: 'Not responding', tone: 'bad', hint: 'Reconnect the cable' },
}

export function SetupPage({ headsets }: { headsets: HeadsetView[] }) {
  const { result, reload } = useSetup()
  const [error, setError] = useState<string | null>(null)

  if (result.state === 'loading') return <p className="text-slate-500">Loading…</p>
  if (result.state === 'remote') {
    return (
      <Message>Setup is available only on the server computer. Open the dashboard there.</Message>
    )
  }
  if (result.state === 'error') return <Message>Could not read connected headsets: {result.message}</Message>

  const { info } = result
  const job = info.job
  const busy = job?.status === 'running' || job?.status === 'waiting_user'

  const run = async (req: SetupRequest) => {
    setError(null)
    try {
      await startSetupJob(req)
      await reload()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm text-slate-600">
          Connect a headset with a USB cable. This program installs agent{' '}
          <span className="font-medium text-slate-900">{info.bundledVersion}</span>.
        </p>
      </div>

      {error && (
        <p className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>
      )}
      {job && <JobPanel job={job} />}

      <WifiUpdates fleet={info.fleet} live={headsets} bundled={info.bundledVersion} onError={setError} />

      <h2 className="text-sm font-semibold text-slate-900">Connected by cable</h2>
      {info.devices.length === 0 ? (
        <Message>No headsets connected. Connect one with a USB cable.</Message>
      ) : (
        <section className="grid grid-cols-[repeat(auto-fill,minmax(min(26rem,100%),1fr))] gap-4">
          {info.devices.map((d) => (
            <DeviceCard key={d.adbId} device={d} busy={busy} onRun={run} />
          ))}
        </section>
      )}
    </div>
  )
}

const UPDATE_STAGE = {
  starting: () => 'Starting…',
  downloading: (percent: number) => `Downloading ${percent}%`,
  installing: () => 'Installing…',
}

/** Что мешает обновить шлем по Wi-Fi; null — можно обновлять. */
function wifiBlock(h: FleetHeadset, asleep: boolean): string | null {
  if (h.status === 'current') return 'Up to date'
  if (h.status === 'newer') return 'Newer than this program'
  if (h.status === 'needs_cable') return 'Update once with a cable'
  if (h.status !== 'outdated') return 'Version unknown'
  if (!h.online) return 'Offline'
  if (asleep) return 'Asleep'
  if (h.adb !== 'ready') return 'Confirmation needed in headset'
  return null
}

/** Обновление по Wi-Fi: агент сам скачивает новую версию с этого компьютера. */
function WifiUpdates({
  fleet,
  live,
  bundled,
  onError,
}: {
  fleet: FleetHeadset[]
  live: HeadsetView[]
  bundled: string
  onError: (message: string | null) => void
}) {
  // Ход обновления приходит через /live, а не из опроса раз в 3 с: скачивание занимает секунды
  const updateOf = (id: string) => live.find((h) => h.id === id)?.update ?? null
  const running = (id: string) => {
    const u = updateOf(id)
    return u != null && u.stage !== 'failed'
  }
  const asleep = (id: string) => live.find((h) => h.id === id)?.screenOn === false
  const ready = fleet.filter((h) => wifiBlock(h, asleep(h.headsetId)) === null && !running(h.headsetId))

  const update_ = async (ids: string[]) => {
    onError(null)
    try {
      await updateOverWifi(ids)
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-slate-900">Update over Wi-Fi</h2>
        {ready.length > 1 && (
          <Action primary onClick={() => void update_(ready.map((h) => h.headsetId))}>
            Update all ({ready.length})
          </Action>
        )}
      </div>
      {fleet.length === 0 ? (
        <p className="text-sm text-slate-500">No headsets yet.</p>
      ) : (
        <ul className="divide-y divide-slate-100 text-sm">
          {fleet.map((h) => {
            const block = wifiBlock(h, asleep(h.headsetId))
            const update = updateOf(h.headsetId)
            return (
              <li key={h.headsetId} className="py-2">
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                  <span className="min-w-24 font-medium text-slate-900">{h.label}</span>
                  <span className="text-slate-500">
                    {h.agentVersion ?? '—'} → {bundled}
                  </span>
                  <span className="ml-auto flex items-center gap-3">
                    {update && update.stage !== 'failed' ? (
                      <span className="text-slate-700">{UPDATE_STAGE[update.stage](update.percent)}</span>
                    ) : block ? (
                      <span className="text-slate-500">{block}</span>
                    ) : (
                      <Action onClick={() => void update_([h.headsetId])}>
                        {update?.stage === 'failed' ? 'Retry' : 'Update'}
                      </Action>
                    )}
                  </span>
                </div>
                {update && update.stage !== 'failed' && (
                  <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100">
                    <div
                      className="h-full rounded-full bg-sky-600 transition-all"
                      style={{ width: `${update.stage === 'starting' ? 0 : update.percent}%` }}
                    />
                  </div>
                )}
                {update?.stage === 'failed' && (
                  <p className="mt-1 text-xs text-red-700">Update failed: {update.reason || 'unknown error'}</p>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

function DeviceCard({
  device: d,
  busy,
  onRun,
}: {
  device: SetupDevice
  busy: boolean
  onRun: (req: SetupRequest) => Promise<void>
}) {
  const [name, setName] = useState('')
  const status = STATUS[d.status] ?? { label: d.status, tone: 'muted' as Tone }
  const usb = d.transport === 'usb'
  const installed = d.installedVersion != null
  const canInstall = !installed && d.state === 'device'
  const label = name.trim() || d.label || ''

  const remove = () => {
    const msg =
      `Remove the agent from ${d.label ?? d.serial ?? d.adbId}?\n\n` +
      'The headset disappears from control. Its name and statistics stay on the server.'
    if (window.confirm(msg)) void onRun({ kind: 'remove', adbId: d.adbId, label: null })
  }

  return (
    <article className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <header className="flex items-start justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">{d.label ?? d.model ?? 'Headset'}</h2>
          <p className="text-xs text-slate-400">
            {d.serial ?? d.adbId} · {usb ? 'USB' : 'Wi-Fi'}
          </p>
        </div>
        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${TONE_BADGE[status.tone]}`}>
          {status.label}
        </span>
      </header>

      {status.hint && <p className="text-sm text-slate-600">{status.hint}</p>}

      {d.state === 'device' && (
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
          <dt className="text-slate-500">On the headset</dt>
          <dd className="text-slate-900">{d.installedVersion ?? 'not installed'}</dd>
          <dt className="text-slate-500">In this program</dt>
          <dd className="text-slate-900">{d.bundledVersion}</dd>
          {installed && (
            <>
              <dt className="text-slate-500">Permissions</dt>
              <dd className={d.permissionsOk ? 'text-slate-900' : 'text-amber-800'}>
                {d.permissionsOk ? 'OK' : 'Missing. Run Update to fix'}
              </dd>
            </>
          )}
        </dl>
      )}

      {canInstall && (
        <input
          value={name}
          maxLength={64}
          onChange={(e) => setName(e.target.value)}
          placeholder={d.label ?? 'Headset name, e.g. Headset 07'}
          aria-label="Headset name"
          className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
        />
      )}

      {d.state === 'device' && (
        <div className="flex flex-wrap gap-2">
          {canInstall && (
            <Action
              primary
              disabled={busy || !usb || !label}
              title={usb ? undefined : 'First install needs a USB cable'}
              onClick={() => void onRun({ kind: 'install', adbId: d.adbId, label })}
            >
              Install
            </Action>
          )}
          {installed && (
            <Action
              primary={d.status === 'outdated'}
              disabled={busy}
              onClick={() => void onRun({ kind: 'update', adbId: d.adbId, label: null })}
            >
              {d.status === 'outdated' ? 'Update' : 'Reinstall'}
            </Action>
          )}
          {installed && (
            <Action danger disabled={busy} onClick={remove}>
              Remove
            </Action>
          )}
        </div>
      )}
    </article>
  )
}

const JOB_TITLE: Record<SetupJob['kind'], string> = { install: 'Install', update: 'Update', remove: 'Remove' }

function JobPanel({ job }: { job: SetupJob }) {
  const look =
    job.status === 'failed'
      ? 'border-red-200 bg-red-50 text-red-900'
      : job.status === 'waiting_user'
        ? 'border-amber-300 bg-amber-50 text-amber-900'
        : job.status === 'done'
          ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
          : 'border-slate-200 bg-white text-slate-800'
  return (
    <section className={`rounded-xl border px-4 py-3 text-sm ${look}`}>
      <h2 className="font-semibold">
        {JOB_TITLE[job.kind]} · {job.adbId}
        {job.status === 'waiting_user' && ' · action needed in the headset'}
      </h2>
      <ul className="mt-1">
        {job.log.map((line, i) => (
          <li key={i} className={i === job.log.length - 1 ? 'font-medium' : 'opacity-70'}>
            {line}
          </li>
        ))}
      </ul>
      {job.error && <p className="mt-1 font-medium">{job.error}</p>}
    </section>
  )
}

function Message({ children }: { children: React.ReactNode }) {
  return (
    <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center text-slate-500">
      {children}
    </p>
  )
}

function Action({
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
