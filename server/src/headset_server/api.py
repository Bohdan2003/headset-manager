import asyncio
import hmac
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import FileResponse
from sqlalchemy import select

from .db import Headset
from . import paths, setup_tools, stats
from .auth import COOKIE, MIN_PASSWORD, SESSION_S
from .protocol import (
    AuthRequest,
    AuthStatus,
    CommandCreate,
    CommandView,
    FleetHeadset,
    HeadsetCreate,
    HeadsetCredentials,
    HeadsetRename,
    HeadsetView,
    SetupInfo,
    SetupJob,
    SetupRequest,
    WifiUpdateRequest,
    Stats,
    StatsPeriod,
    UpdateProgress,
)
from .security import hash_token, new_token

router = APIRouter()


def require_admin(request: Request, authorization: str = Header(default="")) -> None:
    expected = f"Bearer {request.app.state.settings.admin_token}"
    if not hmac.compare_digest(authorization, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "admin token required")


def require_session(request: Request, authorization: str = Header(default="")) -> None:
    """Дашборд входит по cookie, скрипты настройки — по админскому токену."""
    state = request.app.state
    if not state.settings.auth_enabled:
        return
    if hmac.compare_digest(authorization, f"Bearer {state.settings.admin_token}"):
        return
    if not state.auth.session_valid(request.cookies.get(COOKIE)):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "login required")


def is_local(request: Request) -> bool:
    client = request.client.host if request.client else ""
    # Дашборд на этом же компьютере мог быть открыт по сетевому адресу: тогда адрес клиента равен адресу сервера
    own_address = (request.scope.get("server") or ("",))[0]
    return client in ("127.0.0.1", "::1", "localhost", "testclient", own_address)


def _set_cookie(response: Response, value: str) -> None:
    # Без Secure: сервер в локальной сети арены работает по http
    response.set_cookie(COOKIE, value, max_age=SESSION_S, httponly=True, samesite="strict")


@router.get("/api/auth/status", response_model=AuthStatus, response_model_by_alias=True)
async def auth_status(request: Request) -> AuthStatus:
    auth = request.app.state.auth
    disabled = not request.app.state.settings.auth_enabled
    return AuthStatus(
        configured=disabled or auth.configured,
        authenticated=disabled or auth.session_valid(request.cookies.get(COOKIE)),
        can_setup=is_local(request),
    )


@router.post("/api/auth/setup", status_code=status.HTTP_204_NO_CONTENT)
async def auth_setup(body: AuthRequest, request: Request, response: Response) -> None:
    """Первый запуск: пароль задаётся только с компьютера-сервера и только если его ещё нет."""
    auth = request.app.state.auth
    if not is_local(request):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "set the password on the server computer")
    if auth.configured:
        raise HTTPException(status.HTTP_409_CONFLICT, "password is already set")
    if len(body.password) < MIN_PASSWORD:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"at least {MIN_PASSWORD} characters")
    await asyncio.to_thread(auth.set_password, body.password)
    _set_cookie(response, auth.make_session())


@router.post("/api/auth/login", status_code=status.HTTP_204_NO_CONTENT)
async def auth_login(body: AuthRequest, request: Request, response: Response) -> None:
    auth = request.app.state.auth
    client = request.client.host if request.client else ""
    wait = auth.locked_for(client)
    if wait:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, f"too many attempts, wait {wait} s")
    if not await asyncio.to_thread(auth.verify, body.password):
        auth.record_fail(client)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "wrong password")
    auth.clear_fails(client)
    _set_cookie(response, auth.make_session())


@router.post("/api/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def auth_logout(response: Response) -> None:
    response.delete_cookie(COOKIE)


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get(
    "/api/headsets", response_model=list[HeadsetView], response_model_by_alias=True,
    dependencies=[Depends(require_session)],
)
async def list_headsets(request: Request) -> list[HeadsetView]:
    return request.app.state.registry.snapshot()


@router.post(
    "/api/headsets",
    response_model=HeadsetCredentials,
    response_model_by_alias=True,
    dependencies=[Depends(require_admin)],
)
async def register_headset(body: HeadsetCreate, request: Request) -> HeadsetCredentials:
    """
    Регистрация шлема из provision.sh. Если шлем с таким серийным номером уже есть
    (например, после сброса к заводским), запись сохраняется, а токен выдаётся новый.
    """
    return await register(request.app.state, body.label, body.serial, body.android_id)


async def register(state, label: str, serial: str, android_id: str | None) -> HeadsetCredentials:
    token = new_token()
    async with state.session_factory() as s:
        headset = (await s.execute(select(Headset).where(Headset.serial == serial))).scalar_one_or_none()
        created = headset is None
        if headset is None:
            headset = Headset(id=str(uuid.uuid4()), serial=serial, label=label, token_hash="")
            s.add(headset)
        headset.label = label
        headset.android_id = android_id
        headset.token_hash = hash_token(token)
        await s.commit()
    await state.registry.upsert(headset)
    return HeadsetCredentials(headset_id=headset.id, token=token, created=created)


@router.patch(
    "/api/headsets/{headset_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_session)]
)
async def rename_headset(headset_id: str, body: HeadsetRename, request: Request) -> None:
    """Новое название шлема; дашборды получают его через /live."""
    state = request.app.state
    async with state.session_factory() as s:
        headset = await s.get(Headset, headset_id)
        if headset is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "headset not found")
        headset.label = body.label
        await s.commit()
    await state.registry.upsert(headset)


@router.post(
    "/api/commands", response_model=list[CommandView], response_model_by_alias=True,
    dependencies=[Depends(require_session)],
)
async def create_commands(body: CommandCreate, request: Request) -> list[CommandView]:
    """
    Одна команда нескольким шлемам. Ответ — по команде на шлем со статусом sent
    (или failed/offline). Дальнейшие изменения статуса приходят дашборду через /live.
    """
    if body.cmd == "update_agent":  # только через /api/setup/update-wifi: с компьютера-сервера
        raise HTTPException(status.HTTP_403_FORBIDDEN, "use setup to update the agent")
    return await request.app.state.commands.create(body)


@router.get(
    "/api/stats", response_model=Stats, response_model_by_alias=True, dependencies=[Depends(require_session)]
)
async def get_stats(request: Request, period: StatsPeriod = "today") -> Stats:
    """Статистика за сегодня / 7 / 30 дней (от местной полуночи)."""
    return await stats.compute(request.app.state.session_factory, period)


def require_local(request: Request) -> None:
    """Установка и удаление агента — только с самого компьютера-сервера, не из сети арены."""
    if not is_local(request):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "setup is available only on the server computer")


@router.get(
    "/api/setup", response_model=SetupInfo, response_model_by_alias=True, dependencies=[Depends(require_session), Depends(require_local)]
)
async def setup_info(request: Request) -> SetupInfo:
    state = request.app.state
    jobs = state.setup_jobs
    # Во время операции adb не трогаем: при настройке ключа adb-сервер работает с временным ключом,
    # и лишний вызов поднял бы его с ключом компьютера
    if not jobs.busy:
        async with state.session_factory() as s:
            labels = {h.serial: (h.id, h.label) for h in (await s.execute(select(Headset))).scalars()}
        try:
            jobs.last_devices = await setup_tools.list_devices(labels)
        except setup_tools.SetupError as e:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e)) from e
    bundled = paths.bundled_agent()[0]
    fleet = [
        FleetHeadset(
            headset_id=h.id, label=h.label, online=h.online, agent_version=h.agent_version, adb=h.adb,
            status=setup_tools.fleet_status(h.agent_version, bundled),
        )
        for h in state.registry.snapshot()
    ]
    return SetupInfo(bundled_version=bundled, devices=jobs.last_devices, fleet=fleet, job=jobs.current)


@router.post(
    "/api/setup/jobs", response_model=SetupJob, response_model_by_alias=True, dependencies=[Depends(require_session), Depends(require_local)]
)
async def setup_job(body: SetupRequest, request: Request) -> SetupJob:
    try:
        return request.app.state.setup_jobs.start(body.kind, body.adb_id, body.label)
    except setup_tools.SetupError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e


@router.post(
    "/api/setup/update-wifi",
    response_model=list[CommandView],
    response_model_by_alias=True,
    dependencies=[Depends(require_session), Depends(require_local)],
)
async def update_over_wifi(body: WifiUpdateRequest, request: Request) -> list[CommandView]:
    """Агенты сами скачают новую версию с этого сервера и установят её через локальный ADB."""
    _, code = paths.bundled_agent()
    sha256 = await asyncio.to_thread(setup_tools.agent_sha256)
    command = CommandCreate(
        headset_ids=body.headset_ids,
        cmd="update_agent",
        params={"versionCode": code, "sha256": sha256, "path": "/api/agent/apk"},
        ttl_s=60,  # скачивание занимает секунды, ack приходит после него
    )
    views = await request.app.state.commands.create(command)
    for view in views:
        if view.status == "sent":
            await request.app.state.registry.set_update(view.headset_id, UpdateProgress(stage="starting"))
    return views


@router.get("/api/agent/apk")
async def agent_apk() -> FileResponse:
    """В APK нет секретов, а поставить его можно только поверх агента с той же подписью."""
    apk = paths.agent_apk()
    if not apk.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "agent apk is not built")
    return FileResponse(apk, media_type="application/vnd.android.package-archive")
