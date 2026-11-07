# dashboard — React + Vite + TypeScript + Tailwind

## Разработка

```bash
# 1. сервер (в другом терминале)
cd ../server && HM_ADMIN_TOKEN=dev-admin uv run headset-server
# 2. по желанию — фейковые шлемы
cd ../server && HM_ADMIN_TOKEN=dev-admin uv run python tools/fake_agent.py --count 3
# 3. дашборд с горячей перезагрузкой
npm run dev        # http://localhost:5173, /api и /live проксируются на :8000
```

Сервер на другой машине: `HM_SERVER=http://192.168.50.74:8000 npm run dev`.

## На арене

`npm run build` → FastAPI сам раздаёт `dist/` на http://<сервер>:8000/ — Node не нужен.

## Типы протокола

`src/api/protocol.gen.ts` генерируется из Pydantic-моделей сервера — руками не править:

```bash
npm run gen:types
```

## Устройство

- `src/api/useLive.ts` — WebSocket `/live`: снимок всех шлемов, затем изменения; автопереподключение.
- `src/lib/format.ts` — названия приложений, статусы ADB простыми словами, «N мин назад».
- `src/components/` — карточка шлема, сводка, статус связи с сервером.
