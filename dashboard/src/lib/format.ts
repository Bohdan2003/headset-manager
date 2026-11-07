import type { AppInfo, CommandView, HeadsetView } from '../api/protocol.gen'

export type AdbStatus = NonNullable<HeadsetView['adb']>
export type Tone = 'ok' | 'warn' | 'bad' | 'muted'

/** Системные приложения Meta: если открыто одно из них, игрок не в игре. */
const SHELL_APPS: Record<string, string> = {
  'com.oculus.vrshell': 'Meta menu',
  'com.oculus.store': 'Meta Store',
  'com.meta.systemui': 'Meta system window',
  'com.oculus.systemux': 'Meta menu',
  'com.oculus.panelapp.settings': 'Settings',
  'com.oculus.panelapp.library': 'Library',
  'com.arena.agent': 'Arena agent',
}

export function isShellApp(pkg: string): boolean {
  return pkg in SHELL_APPS
}

/**
 * Человеческое название приложения: из списка, который прислал агент; иначе —
 * последняя часть имени пакета (com.Anvio.CityZ → CityZ).
 */
export function appTitle(pkg: string, apps: AppInfo[] = []): string {
  return SHELL_APPS[pkg] ?? apps.find((a) => a.package === pkg)?.title ?? pkg.split('.').pop() ?? pkg
}

/** Пакеты Meta и Android — это не игры, даже если они VR (Horizon Worlds, Guardian и т. п.). */
const SYSTEM_PREFIXES = ['com.oculus.', 'com.meta.', 'com.facebook.', 'com.android.', 'android']

/**
 * Игры шлема: VR-приложения (агент помечает их флагом vr) не от Meta.
 * Если агент старый и флага нет — отсекаем только системные пакеты.
 */
export function games(apps: AppInfo[]): AppInfo[] {
  return apps.filter((a) => a.vr !== false && !SYSTEM_PREFIXES.some((p) => a.package.startsWith(p)))
}

/** Статус локального ADB простыми словами — для оператора, а не для разработчика. */
export const ADB_STATUS: Record<AdbStatus, { label: string; hint?: string; tone: Tone }> = {
  ready: { label: 'Close and restart available', tone: 'ok' },
  waiting_confirmation: {
    label: 'Confirmation needed in headset',
    hint: 'To close, restart or reboot: put on the headset and press “Always allow on this network”',
    tone: 'warn',
  },
  connecting: { label: 'Connecting…', tone: 'muted' },
  no_wifi: { label: 'No Wi-Fi', hint: 'Close, restart and reboot are unavailable', tone: 'warn' },
  key_missing: { label: 'Not set up', hint: 'Needs setup over cable (provision.sh)', tone: 'bad' },
  key_rejected: { label: 'Key rejected', hint: 'The headset forgot the key. Needs setup over cable', tone: 'bad' },
  error: { label: 'ADB error', hint: 'See the agent log for details', tone: 'bad' },
}

export function batteryTone(level: number, charging: boolean | null): Tone {
  if (charging) return 'ok'
  if (level < 20) return 'bad'
  if (level < 40) return 'warn'
  return 'ok'
}

export function timeAgo(iso: string | null, now: number): string {
  if (!iso) return 'never'
  const s = Math.max(0, Math.round((now - Date.parse(iso)) / 1000))
  if (s < 10) return 'just now'
  if (s < 60) return `${s}s ago`
  const m = Math.round(s / 60)
  if (m < 60) return `${m}m ago`
  const h = Math.round(m / 60)
  if (h < 24) return `${h}h ago`
  return `${Math.round(h / 24)}d ago`
}

/** «Шлем 2» раньше «Шлем 10». */
export function byLabel(a: HeadsetView, b: HeadsetView): number {
  return a.label.localeCompare(b.label, 'en', { numeric: true })
}

/** Что за команда — словами оператора. */
export function commandLabel(c: CommandView, apps: AppInfo[]): string {
  const p = c.params as Record<string, unknown>
  switch (c.cmd) {
    case 'launch':
      return `Launch ${appTitle(String(p.pkg), apps)}${p.guard ? ' with Protection' : ''}`
    case 'show_menu':
      return 'Show menu'
    case 'set_sleep':
      return p.disabled ? 'Disable sleep' : 'Enable sleep'
    case 'guard':
      return p.pkg ? `Protect ${appTitle(String(p.pkg), apps)}` : p.current ? 'Protection on' : 'Protection off'
    case 'close_game':
      return p.pkg ? `Close ${appTitle(String(p.pkg), apps)}` : 'Close game'
    case 'restart_game':
      return p.pkg ? `Restart ${appTitle(String(p.pkg), apps)}` : 'Restart game'
    case 'reboot':
      return 'Reboot'
    case 'sleep':
      return 'Sleep'
    case 'power_off':
      return 'Turn off'
    case 'request_access':
      return 'Request access'
    case 'update_agent':
      return 'Update agent'
  }
}

const REASON_TEXT: Record<NonNullable<CommandView['reason']>, string> = {
  offline: 'headset offline',
  asleep: 'headset is asleep',
  timeout: 'no response from headset',
  no_adb: 'confirmation needed in headset',
  not_allowed: 'not available yet',
  failed: 'failed',
  expired: 'expired',
  bad_params: 'invalid parameters',
}

export function commandResult(c: CommandView): { text: string; tone: Tone } {
  switch (c.status) {
    case 'sent':
      return { text: 'in progress…', tone: 'muted' }
    case 'acked':
      return { text: 'done', tone: 'ok' }
    case 'timeout':
      return { text: REASON_TEXT.timeout, tone: 'bad' }
    case 'failed':
      return { text: c.reason ? REASON_TEXT[c.reason] : 'error', tone: 'bad' }
  }
}
