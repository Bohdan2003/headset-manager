import { useCallback, useEffect, useState } from 'react'
import { signalLoggedOut } from './http'
import type { CommandView, HeadsetView, Live } from './protocol.gen'

export type LiveStatus = 'connecting' | 'open' | 'closed'

export interface LiveState {
  headsets: Record<string, HeadsetView>
  /** Последняя команда каждому шлему — чтобы показать на карточке, чем она кончилась. */
  lastCommand: Record<string, CommandView>
}

const EMPTY: LiveState = { headsets: {}, lastCommand: {} }
const BACKOFF_MS = [1000, 2000, 5000, 10000]

/** Применить сообщение /live к текущему состоянию. */
export function applyLive(state: LiveState, msg: Live): LiveState {
  switch (msg.type) {
    case 'snapshot':
      return {
        headsets: Object.fromEntries(msg.headsets.map((h) => [h.id, h])),
        lastCommand: Object.fromEntries(msg.commands.map((c) => [c.headsetId, c])),
      }
    case 'headset':
      return { ...state, headsets: { ...state.headsets, [msg.headset.id]: msg.headset } }
    case 'command': {
      const c = msg.command
      const prev = state.lastCommand[c.headsetId]
      // Обновление старой команды не должно затирать более новую
      if (prev && prev.id !== c.id && prev.createdAt > c.createdAt) return state
      return { ...state, lastCommand: { ...state.lastCommand, [c.headsetId]: c } }
    }
  }
}

/**
 * Живое состояние с сервера (WebSocket /live).
 * После подключения сервер присылает весь список шлемов, дальше — изменения шлемов и команд.
 * При обрыве переподключается сам; пока связи нет, показываем последние известные данные.
 */
export function useLive() {
  const [state, setState] = useState<LiveState>(EMPTY)
  const [status, setStatus] = useState<LiveStatus>('connecting')

  useEffect(() => {
    let ws: WebSocket | null = null
    let attempt = 0
    let timer: ReturnType<typeof setTimeout> | undefined
    let stopped = false

    const connect = () => {
      setStatus('connecting')
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      ws = new WebSocket(`${proto}://${location.host}/live`)
      ws.onopen = () => {
        attempt = 0
        setStatus('open')
      }
      ws.onmessage = (e) => {
        const msg = JSON.parse(e.data as string) as Live
        setState((prev) => applyLive(prev, msg))
      }
      ws.onclose = (e) => {
        if (stopped) return
        if (e.code === 4401) {
          // Сессии нет или она истекла: показываем вход, а не переподключаемся
          signalLoggedOut()
          return
        }
        setStatus('closed')
        timer = setTimeout(connect, BACKOFF_MS[Math.min(attempt, BACKOFF_MS.length - 1)])
        attempt++
      }
    }

    connect()
    return () => {
      stopped = true
      clearTimeout(timer)
      ws?.close()
    }
  }, [])

  /** Ответ POST /api/commands приходит раньше, чем /live — показываем его сразу. */
  const addCommands = useCallback((commands: CommandView[]) => {
    setState((prev) => commands.reduce((s, command) => applyLive(s, { type: 'command', command }), prev))
  }, [])

  return { headsets: Object.values(state.headsets), lastCommand: state.lastCommand, status, addCommands }
}
