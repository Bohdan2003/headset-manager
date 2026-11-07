import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { fetchAuthStatus, login, setupPassword } from '../api/auth'
import { onLoggedOut } from '../api/http'
import type { AuthStatus } from '../api/rest.gen'

const MIN_PASSWORD = 8

/** Дашборд виден только после входа. Новый пароль задаётся один раз, на компьютере-сервере. */
export function AuthGate({ children }: { children: ReactNode }) {
  const [auth, setAuth] = useState<AuthStatus | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    const check = () =>
      fetchAuthStatus().then(
        (s) => {
          setAuth(s)
          setFailed(false)
        },
        () => setFailed(true),
      )
    void check()
    return onLoggedOut(() => void check())
  }, [])

  // Пока сервер перезапускается, проверить нельзя: пробуем снова, а не показываем пустой экран
  useEffect(() => {
    if (!failed) return
    const t = setInterval(() => {
      fetchAuthStatus().then(
        (s) => {
          setAuth(s)
          setFailed(false)
        },
        () => undefined,
      )
    }, 2000)
    return () => clearInterval(t)
  }, [failed])

  if (auth?.authenticated) return children
  if (!auth) return <Shell>{failed ? 'No connection to the server. Retrying…' : 'Loading…'}</Shell>
  if (auth.configured) return <PasswordForm mode="login" onDone={() => setAuth({ ...auth, authenticated: true })} />
  if (auth.canSetup) return <PasswordForm mode="setup" onDone={() => setAuth({ ...auth, configured: true, authenticated: true })} />
  return <Shell>The password has not been set yet. Open the dashboard on the server computer to set it.</Shell>
}

function Shell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-600">
        <h1 className="mb-4 text-xl font-semibold text-slate-900">Arena</h1>
        {children}
      </div>
    </div>
  )
}

function PasswordForm({ mode, onDone }: { mode: 'login' | 'setup'; onDone: () => void }) {
  const [password, setPassword] = useState('')
  const [repeat, setRepeat] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const setup = mode === 'setup'
  const input = 'w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 outline-none focus:border-sky-600'

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (setup && password.length < MIN_PASSWORD) return setError(`Use at least ${MIN_PASSWORD} characters`)
    if (setup && password !== repeat) return setError('The passwords do not match')
    setBusy(true)
    setError(null)
    try {
      await (setup ? setupPassword : login)(password)
      onDone()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setBusy(false)
    }
  }

  return (
    <Shell>
      <form onSubmit={(e) => void submit(e)} className="flex flex-col gap-3">
        {setup && <p>Create a password for the dashboard. Everyone at the arena will use it to sign in.</p>}
        <label className="flex flex-col gap-1">
          Password
          <input
            type="password"
            autoFocus
            autoComplete={setup ? 'new-password' : 'current-password'}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={input}
          />
        </label>
        {setup && (
          <label className="flex flex-col gap-1">
            Repeat password
            <input
              type="password"
              autoComplete="new-password"
              value={repeat}
              onChange={(e) => setRepeat(e.target.value)}
              className={input}
            />
          </label>
        )}
        {error && <p className="text-red-700">{error}</p>}
        <button
          type="submit"
          disabled={busy || !password}
          className="rounded-lg bg-slate-900 px-3 py-2 font-medium text-white disabled:opacity-50"
        >
          {setup ? 'Set password' : 'Sign in'}
        </button>
        {!setup && <p className="text-xs text-slate-500">Forgot it? Press Reset password in the Arena window.</p>}
      </form>
    </Shell>
  )
}
