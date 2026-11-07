import { useState } from 'react'
import { useStats, type StatsPeriod } from '../api/stats'
import type { Stats, StatsHeadset } from '../api/rest.gen'

const PERIODS: { value: StatsPeriod; label: string }[] = [
  { value: 'today', label: 'Today' },
  { value: '7d', label: '7 days' },
  { value: '30d', label: '30 days' },
]

/** Один цвет для всех графиков страницы: на каждом одна величина, а не разные серии. */
const BAR = 'bg-sky-600'

function duration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  const m = Math.round(seconds / 60)
  if (m < 60) return `${m}m`
  const h = Math.floor(m / 60)
  const rest = m % 60
  return rest ? `${h}h ${rest}m` : `${h}h`
}

/** Период хранится в адресе (#stats/7d) — чтобы ссылка открывала тот же вид. */
function readPeriod(): StatsPeriod {
  const p = location.hash.split('/')[1]
  return PERIODS.some((x) => x.value === p) ? (p as StatsPeriod) : 'today'
}

export function StatsPage() {
  const [period, setPeriodState] = useState<StatsPeriod>(readPeriod)
  const setPeriod = (p: StatsPeriod) => {
    setPeriodState(p)
    history.replaceState(null, '', p === 'today' ? '#stats' : `#stats/${p}`)
  }
  const { data, error } = useStats(period)

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="inline-flex rounded-lg border border-slate-300 bg-white p-0.5" role="tablist">
          {PERIODS.map((p) => (
            <button
              key={p.value}
              role="tab"
              aria-selected={period === p.value}
              onClick={() => setPeriod(p.value)}
              className={`rounded-md px-3 py-1.5 text-sm font-medium ${
                period === p.value ? 'bg-slate-900 text-white' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
        {data && (
          <p className="text-xs text-slate-500">
            since {new Date(data.from).toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' })} · updates
            every minute
          </p>
        )}
      </div>

      {error && (
        <p className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          Could not load statistics: {error}
        </p>
      )}
      {!data ? (
        !error && <p className="text-slate-500">Loading…</p>
      ) : data.headsets.length === 0 ? (
        <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center text-slate-500">
          No headsets yet.
        </p>
      ) : (
        <>
          <Totals data={data} />
          <section className="grid gap-6 lg:grid-cols-2">
            <HeadsetChart
              data={data}
              title="Connection drops"
              hint="The headset dropped off the network on its own. Sleep, restart and power off are not counted."
              value={(h) => h.disconnects}
              format={(v) => String(v)}
            />
            <HeadsetChart
              data={data}
              title="Charge interruptions"
              hint="Charging stopped before the battery reached 100%."
              value={(h) => h.chargeInterruptions}
              format={(v) => String(v)}
            />
            <HeadsetChart
              data={data}
              title="Battery life on a full charge"
              hint="Estimated from the discharge rate while the headset is awake and not charging."
              value={(h) => h.batteryLifeH}
              format={(v) => `${v}h`}
              detail={(h) => (h.batteryDrainPerHour == null ? '' : `drains ${h.batteryDrainPerHour}%/h`)}
            />
            <HeadsetChart
              data={data}
              title="Play time"
              hint="Total time in games."
              value={(h) => h.playS}
              format={duration}
              detail={(h) => `${h.sessions} sessions`}
            />
          </section>
          <HeadsetsTable data={data} />
          {data.totals.sessions > 0 && (
            <>
              <h2 className="pt-2 text-base font-semibold text-slate-900">Games</h2>
              {data.days.length > 1 ? (
                <div className="grid gap-6 lg:grid-cols-2">
                  <GamesChart data={data} />
                  <DaysChart data={data} />
                </div>
              ) : (
                <GamesChart data={data} />
              )}
              <GamesTable data={data} />
            </>
          )}
        </>
      )}
    </div>
  )
}

function Totals({ data }: { data: Stats }) {
  const known = data.headsets.flatMap((h) => (h.batteryLifeH == null ? [] : [h.batteryLifeH]))
  const life = known.length ? `${(known.reduce((a, b) => a + b, 0) / known.length).toFixed(1)}h` : '—'
  const sum = (pick: (h: StatsHeadset) => number) => data.headsets.reduce((total, h) => total + pick(h), 0)
  return (
    <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <Tile label="Connection drops" value={sum((h) => h.disconnects)} />
      <Tile label="Charge interruptions" value={sum((h) => h.chargeInterruptions)} />
      <Tile label="Average battery life" value={life} hint="Average across headsets with enough data" />
      <Tile label="Play time" value={duration(data.totals.playS)} />
    </dl>
  )
}

function Tile({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3" title={hint}>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="text-2xl font-semibold text-slate-900">{value}</dd>
    </div>
  )
}

function Card({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4">
      <h2 className={`text-sm font-semibold text-slate-900 ${hint ? '' : 'mb-3'}`}>{title}</h2>
      {hint && <p className="mb-3 text-xs text-slate-500">{hint}</p>}
      {children}
    </section>
  )
}

/** Больше столбцов — числа над ними слипаются, остаётся подсказка и таблица. */
const MAX_LABELLED = 12

/**
 * Одна метрика — один график, столбец на шлем. Шлемы во всех графиках в одном порядке
 * (по названию), чтобы один и тот же шлем был на том же месте и его легко было сравнить.
 */
function HeadsetChart({
  data,
  title,
  hint,
  value,
  format,
  detail,
}: {
  data: Stats
  title: string
  hint: string
  value: (h: StatsHeadset) => number | null
  format: (v: number) => string
  detail?: (h: StatsHeadset) => string
}) {
  const [hover, setHover] = useState<string | null>(null)
  const rows = [...data.headsets].sort((a, b) =>
    a.label.localeCompare(b.label, undefined, { numeric: true }),
  )
  const max = Math.max(...rows.map((h) => value(h) ?? 0), 1)
  const shown = rows.find((h) => h.headsetId === hover)
  const text = (h: StatsHeadset) => {
    const v = value(h)
    return v == null ? 'not enough data' : format(v)
  }
  const extra = shown && detail?.(shown)

  return (
    <Card title={title} hint={hint}>
      <p className="mb-1 h-5 text-sm text-slate-700">
        {shown ? (
          <>
            <span className="font-medium">{shown.label}</span> · {text(shown)}
            {extra ? ` · ${extra}` : ''}
          </>
        ) : (
          <span className="text-slate-400">hover over a bar</span>
        )}
      </p>
      <div className="flex h-44 items-end gap-[2px] border-b border-slate-200" onMouseLeave={() => setHover(null)}>
        {rows.map((h) => {
          const v = value(h)
          return (
            <div
              key={h.headsetId}
              className="flex h-full min-w-0 flex-1 cursor-default flex-col items-center justify-end"
              onMouseEnter={() => setHover(h.headsetId)}
              aria-label={`${h.label}: ${text(h)}`}
            >
              {rows.length <= MAX_LABELLED && (
                <span className="mb-1 text-xs tabular-nums text-slate-700">{v == null ? '—' : format(v)}</span>
              )}
              <div
                className={`w-full max-w-6 rounded-t-[4px] ${BAR} ${hover && hover !== h.headsetId ? 'opacity-50' : ''}`}
                // запас сверху — под число над самым высоким столбцом
                style={{ height: v ? `${Math.max((v / max) * 82, 2)}%` : 0 }}
              />
            </div>
          )
        })}
      </div>
      <div className="mt-1 flex gap-[2px] text-xs text-slate-500">
        {rows.map((h) => (
          <span key={h.headsetId} className="min-w-0 flex-1 truncate text-center" title={h.label}>
            {h.label}
          </span>
        ))}
      </div>
    </Card>
  )
}

/** Время игры по играм: горизонтальные столбцы по убыванию, на одной базовой линии. */
function GamesChart({ data }: { data: Stats }) {
  const max = Math.max(...data.games.map((g) => g.playS), 1)
  return (
    <Card title="Play time by game">
      <ul className="flex flex-col gap-2">
        {data.games.map((g) => (
          <li key={g.package} className="grid grid-cols-[minmax(0,10rem)_1fr_auto] items-center gap-3 text-sm">
            <span className="truncate text-slate-700" title={g.package}>
              {g.title}
            </span>
            <span className="h-3 rounded-r-[4px] bg-slate-100">
              <span
                className={`block h-full rounded-r-[4px] ${BAR}`}
                style={{ width: `${(g.playS / max) * 100}%` }}
                title={`${g.title}: ${duration(g.playS)}, ${g.sessions} sessions`}
              />
            </span>
            <span className="min-w-[5.5rem] whitespace-nowrap text-right tabular-nums text-slate-700">
              {duration(g.playS)}
            </span>
          </li>
        ))}
      </ul>
    </Card>
  )
}

/** Время игры по дням: столбцы от общей базовой линии, значение — в подсказке при наведении. */
function DaysChart({ data }: { data: Stats }) {
  const [hover, setHover] = useState<number | null>(null)
  const max = Math.max(...data.days.map((d) => d.playS), 1)
  const fmt = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
  const shown = hover != null ? data.days[hover] : null
  // подписываем не каждый столбец, а края и середину — иначе на 30 днях подписи слипаются
  const labelled = new Set([0, Math.floor((data.days.length - 1) / 2), data.days.length - 1])

  return (
    <Card title="Play time by day">
      <p className="mb-2 h-5 text-sm text-slate-700">
        {shown ? (
          <>
            <span className="font-medium">{fmt(shown.date)}</span> · {duration(shown.playS)}
          </>
        ) : (
          <span className="text-slate-400">hover over a bar</span>
        )}
      </p>
      <div className="flex h-40 items-end gap-[2px] border-b border-slate-200" onMouseLeave={() => setHover(null)}>
        {data.days.map((d, i) => (
          <div
            key={d.date}
            className="flex h-full flex-1 cursor-default items-end"
            onMouseEnter={() => setHover(i)}
            aria-label={`${fmt(d.date)}: ${duration(d.playS)}`}
          >
            <div
              className={`mx-auto w-full max-w-8 rounded-t-[4px] ${BAR} ${hover != null && hover !== i ? 'opacity-50' : ''}`}
              style={{ height: d.playS ? `${Math.max((d.playS / max) * 100, 2)}%` : 0 }}
            />
          </div>
        ))}
      </div>
      <div className="mt-1 flex text-xs text-slate-500">
        {data.days.map((d, i) => (
          <span key={d.date} className="flex-1 text-center">
            {labelled.has(i) ? fmt(d.date) : ''}
          </span>
        ))}
      </div>
    </Card>
  )
}

function GamesTable({ data }: { data: Stats }) {
  return (
    <Card title="By game">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-slate-500">
            <tr className="border-b border-slate-200">
              <th className="py-2 pr-4 font-medium">Game</th>
              <Th>Time</Th>
              <Th>Sessions</Th>
              <Th>Average</Th>
              <Th title="Exits to the Meta menu with a return within a minute">Exits</Th>
              <Th title="How many times Protection returned the player">Protection returns</Th>
              <Th title="The session ended because the player left">Player left</Th>
              <Th title="The operator closed or restarted the game">Ended by operator</Th>
            </tr>
          </thead>
          <tbody>
            {data.games.map((g) => (
              <tr key={g.package} className="border-b border-slate-100 last:border-0">
                <td className="py-2 pr-4 text-slate-900" title={g.package}>
                  {g.title}
                </td>
                <Td>{duration(g.playS)}</Td>
                <Td>{g.sessions}</Td>
                <Td>{duration(g.avgSessionS)}</Td>
                <Td>{g.exits}</Td>
                <Td>{g.guardReturns}</Td>
                <Td>{g.endedByPlayer}</Td>
                <Td>{g.endedByOperator}</Td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

function HeadsetsTable({ data }: { data: Stats }) {
  return (
    <Card title="By headset">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-slate-500">
            <tr className="border-b border-slate-200">
              <th className="py-2 pr-4 font-medium">Headset</th>
              <Th>Play time</Th>
              <Th>Sessions</Th>
              <Th title="The headset dropped off the network on its own. Sleep, restart and power off are not counted">
                Connection drops
              </Th>
              <Th title="Charging stopped before the battery reached 100%">Charge interruptions</Th>
              <Th title="Estimated hours on a full charge while awake and not charging">Battery life</Th>
              <Th title="Average discharge rate while not charging. If it grows over time, the battery is wearing out">
                Drain, %/h
              </Th>
            </tr>
          </thead>
          <tbody>
            {data.headsets.map((h) => (
              <tr key={h.headsetId} className="border-b border-slate-100 last:border-0">
                <td className="py-2 pr-4 text-slate-900">{h.label}</td>
                <Td>{duration(h.playS)}</Td>
                <Td>{h.sessions}</Td>
                <Td>{h.disconnects}</Td>
                <Td>{h.chargeInterruptions}</Td>
                <Td>{h.batteryLifeH == null ? '—' : `${h.batteryLifeH}h`}</Td>
                <Td>{h.batteryDrainPerHour ?? '—'}</Td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

function Th({ children, title }: { children: React.ReactNode; title?: string }) {
  return (
    <th className="py-2 pl-4 text-right font-medium" title={title}>
      {children}
    </th>
  )
}

function Td({ children }: { children: React.ReactNode }) {
  return <td className="whitespace-nowrap py-2 pl-4 text-right tabular-nums text-slate-700">{children}</td>
}
