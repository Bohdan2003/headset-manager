import type { Tone } from './format'

export const TONE_TEXT: Record<Tone, string> = {
  ok: 'text-emerald-700',
  warn: 'text-amber-700',
  bad: 'text-red-700',
  muted: 'text-slate-500',
}

export const TONE_BAR: Record<Tone, string> = {
  ok: 'bg-emerald-500',
  warn: 'bg-amber-500',
  bad: 'bg-red-500',
  muted: 'bg-slate-400',
}

export const TONE_BADGE: Record<Tone, string> = {
  ok: 'bg-emerald-50 text-emerald-800 ring-emerald-200',
  warn: 'bg-amber-50 text-amber-900 ring-amber-300',
  bad: 'bg-red-50 text-red-800 ring-red-200',
  muted: 'bg-slate-50 text-slate-600 ring-slate-200',
}
