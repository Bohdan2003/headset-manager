const LOGGED_OUT = 'arena:logged-out'

export function signalLoggedOut() {
  window.dispatchEvent(new Event(LOGGED_OUT))
}

export function onLoggedOut(handler: () => void) {
  window.addEventListener(LOGGED_OUT, handler)
  return () => window.removeEventListener(LOGGED_OUT, handler)
}

/** Обычный fetch, но ответ 401 (сессия кончилась, пароль сброшен) возвращает на экран входа. */
export async function apiFetch(input: string, init?: RequestInit): Promise<Response> {
  const r = await fetch(input, init)
  if (r.status === 401) signalLoggedOut()
  return r
}
