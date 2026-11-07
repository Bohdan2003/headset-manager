"""
Сообщения между агентом, сервером и дашбордом. Это источник истины для протокола:
типы для дашборда генерируются из этих моделей (JSON Schema), агент повторяет тот же JSON.

В JSON поля в camelCase (`headsetId`), в Python — snake_case (`headset_id`).
"""

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator
from pydantic.alias_generators import to_camel


class ProtocolModel(BaseModel):
    # json_schema_serialization_defaults_required: в схеме для дашборда поля со значением
    # по умолчанию обязательные — сервер отправляет их всегда
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        json_schema_serialization_defaults_required=True,
    )

    def to_json(self) -> str:
        return self.model_dump_json(by_alias=True)


AdbStatus = Literal[
    "ready",
    "no_wifi",
    "waiting_confirmation",  # окно «Allow wireless debugging» не подтверждено
    "connecting",
    "key_missing",
    "key_rejected",
    "error",
]

# launch, show_menu, set_sleep, guard — обычными правами (B);
# close_game, restart_game, reboot, sleep, power_off — через локальный ADB (C);
# если он не поднят, агент отвечает no_adb. request_access заново показывает окно подтверждения в шлеме
CommandName = Literal[
    "launch", "show_menu", "set_sleep", "guard", "close_game", "restart_game", "reboot", "sleep", "power_off",
    "request_access",
    "update_agent",
]
AckReason = Literal["no_adb", "not_allowed", "failed", "expired", "bad_params"]
CommandStatus = Literal["sent", "acked", "failed", "timeout"]
# offline и timeout ставит сервер, остальное присылает агент
CommandReason = Literal["offline", "asleep", "timeout", "no_adb", "not_allowed", "failed", "expired", "bad_params"]

PACKAGE_RE = r"^[a-zA-Z0-9_.]+$"


# ---------- агент → сервер ----------


class Hello(ProtocolModel):
    type: Literal["hello"]
    headset_id: str
    token: str
    agent_version: str
    android_id: str | None = None


class ControllerInfo(ProtocolModel):
    side: Literal["left", "right"]
    # Последний известный заряд, %; если контроллер выключен — значение с момента, когда он был на связи
    battery: int | None = Field(default=None, ge=0, le=100)
    connected: bool


class Heartbeat(ProtocolModel):
    type: Literal["heartbeat"]
    battery: int = Field(ge=0, le=100)
    charging: bool
    temp: float | None = None
    current_pkg: str | None = None
    adb: AdbStatus
    sleep_disabled: bool
    adb_timeout_disabled: bool | None = None
    # Игра, в которую агент возвращает игрока (None — охрана выключена)
    guard_pkg: str | None = None
    # Экран включён; False — шлем спит. None — старый агент
    screen_on: bool | None = None
    # Контроллеры; None — агент не смог их прочитать (старый агент, нет прав)
    controllers: list[ControllerInfo] | None = None


class AgentEvent(ProtocolModel):
    """Смена игры, возврат в игру, смена статуса ADB и т. п."""

    type: Literal["event"]
    kind: str
    payload: dict[str, Any] = Field(default_factory=dict)


class AppInfo(ProtocolModel):
    package: str
    title: str
    # VR-приложение (объявляет категорию com.oculus.intent.category.VR). None — агент не сообщил
    vr: bool | None = None


class Apps(ProtocolModel):
    type: Literal["apps"]
    apps: list[AppInfo]


class Ack(ProtocolModel):
    type: Literal["ack"]
    id: str
    ok: bool
    reason: AckReason | None = None
    detail: str | None = None


AgentMessage = Annotated[Hello | Heartbeat | AgentEvent | Apps | Ack, Field(discriminator="type")]
agent_message = TypeAdapter(AgentMessage)


# ---------- сервер → агент ----------


class Welcome(ProtocolModel):
    type: Literal["welcome"] = "welcome"
    server_time: datetime
    heartbeat_interval_s: int
    guard_pkg: str | None = None


class Command(ProtocolModel):
    type: Literal["command"] = "command"
    id: str
    cmd: CommandName
    params: dict[str, Any] = Field(default_factory=dict)
    ttl_s: int = 10


# ---------- сервер → дашборд ----------


class UpdateProgress(ProtocolModel):
    """Как идёт обновление агента по Wi-Fi."""

    stage: Literal["starting", "downloading", "installing", "failed"]
    percent: int = Field(default=0, ge=0, le=100)
    reason: str | None = None


class HeadsetView(ProtocolModel):
    """Шлем, как его видит дашборд."""

    id: str
    label: str
    serial: str
    online: bool = False
    battery: int | None = None
    charging: bool | None = None
    temp: float | None = None
    current_pkg: str | None = None
    adb: AdbStatus | None = None
    sleep_disabled: bool | None = None
    agent_version: str | None = None
    last_seen: datetime | None = None
    guard_pkg: str | None = None
    screen_on: bool | None = None
    update: UpdateProgress | None = None
    controllers: list[ControllerInfo] = Field(default_factory=list)
    apps: list[AppInfo] = Field(default_factory=list)


class CommandView(ProtocolModel):
    """Команда одному шлему и её судьба."""

    id: str
    headset_id: str
    cmd: CommandName
    params: dict[str, Any]
    status: CommandStatus
    reason: CommandReason | None = None
    detail: str | None = None
    created_at: datetime
    acked_at: datetime | None = None


class LiveSnapshot(ProtocolModel):
    """Отправляется дашборду сразу после подключения к /live."""

    type: Literal["snapshot"] = "snapshot"
    headsets: list[HeadsetView]
    # Последняя команда каждому шлему — чтобы после обновления страницы были видны результаты
    commands: list["CommandView"] = Field(default_factory=list)


class LiveHeadset(ProtocolModel):
    """Изменилось состояние одного шлема."""

    type: Literal["headset"] = "headset"
    headset: HeadsetView


class LiveCommand(ProtocolModel):
    """Команда создана или изменился её статус."""

    type: Literal["command"] = "command"
    command: CommandView


LiveMessage = Annotated[LiveSnapshot | LiveHeadset | LiveCommand, Field(discriminator="type")]


# ---------- REST ----------


class HeadsetCreate(ProtocolModel):
    label: str = Field(min_length=1, max_length=64)
    serial: str = Field(min_length=1, max_length=64)
    android_id: str | None = None


class HeadsetRename(ProtocolModel):
    label: str = Field(min_length=1, max_length=64)

    @field_validator("label", mode="before")
    @classmethod
    def _strip(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class LaunchParams(ProtocolModel):
    pkg: str = Field(pattern=PACKAGE_RE)
    # Сразу включить охрану: возвращать игрока в эту игру
    guard: bool = False


class SetSleepParams(ProtocolModel):
    disabled: bool


class GuardParams(ProtocolModel):
    """pkg — охранять эту игру; current — охранять игру, которая сейчас идёт на шлеме; ничего — выключить."""

    pkg: str | None = Field(default=None, pattern=PACKAGE_RE)
    current: bool = False

    @model_validator(mode="after")
    def _one_of(self) -> "GuardParams":
        if self.pkg and self.current:
            raise ValueError("pkg and current are mutually exclusive")
        return self


class CloseGameParams(ProtocolModel):
    # Какую игру закрыть; без pkg агент закрывает текущее приложение (если это не оболочка Meta)
    pkg: str | None = Field(default=None, pattern=PACKAGE_RE)


class UpdateAgentParams(ProtocolModel):
    """Обновление по Wi-Fi: агент сам скачивает APK с сервера. Заполняет сервер, не дашборд."""

    version_code: int
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    path: str


class EmptyParams(ProtocolModel):
    model_config = ConfigDict(extra="forbid")


PARAMS_BY_CMD: dict[str, type[ProtocolModel]] = {
    "launch": LaunchParams,
    "set_sleep": SetSleepParams,
    "guard": GuardParams,
    "show_menu": EmptyParams,
    "close_game": CloseGameParams,
    "restart_game": CloseGameParams,
    "reboot": EmptyParams,
    "sleep": EmptyParams,
    "power_off": EmptyParams,
    "request_access": EmptyParams,
    "update_agent": UpdateAgentParams,
}


class CommandCreate(ProtocolModel):
    """Запрос дашборда: одна команда нескольким шлемам."""

    headset_ids: list[str] = Field(min_length=1, max_length=200)
    cmd: CommandName
    params: dict[str, Any] = Field(default_factory=dict)
    ttl_s: int = Field(default=10, ge=1, le=60)

    @model_validator(mode="after")
    def _check_params(self) -> "CommandCreate":
        # Проверяем параметры на сервере: в агента уходит только то, что он умеет разобрать
        parsed = PARAMS_BY_CMD[self.cmd].model_validate(self.params)
        self.params = parsed.model_dump(by_alias=True)
        return self


class HeadsetCredentials(ProtocolModel):
    """Ответ на регистрацию: это передаётся агенту при настройке. Токен показывается один раз."""

    headset_id: str
    token: str
    created: bool


# ---------- статистика ----------

StatsPeriod = Literal["today", "7d", "30d"]


class StatsTotals(ProtocolModel):
    play_s: int
    sessions: int
    exits: int
    guard_returns: int


class StatsGame(ProtocolModel):
    package: str
    title: str
    play_s: int
    sessions: int
    avg_session_s: int
    # Сколько раз игроки выходили из игры (и возвращались в течение минуты) / сколько раз вернула охрана
    exits: int
    guard_returns: int
    # Чем кончались сессии: exited — сам, closed/menu — оператор, остальное — переключение, обрыв
    ended_by_player: int
    ended_by_operator: int


class StatsHeadset(ProtocolModel):
    headset_id: str
    label: str
    play_s: int
    sessions: int
    # Шлем пропал из сети сам: сон, перезагрузка и выключение не считаются
    disconnects: int
    # Зарядка прекратилась, не дойдя до 100 %
    charge_interruptions: int
    # Средняя скорость разряда без зарядки, % в час; None — мало данных
    battery_drain_per_hour: float | None
    # На сколько часов работы хватает полного заряда при такой скорости
    battery_life_h: float | None


class StatsDay(ProtocolModel):
    date: str  # YYYY-MM-DD, по местному времени сервера
    play_s: int


class Stats(ProtocolModel):
    period: StatsPeriod
    from_: datetime = Field(alias="from")
    to: datetime
    totals: StatsTotals
    games: list[StatsGame]
    headsets: list[StatsHeadset]
    days: list[StatsDay]


# ---------- установка агента ----------

class SetupDevice(ProtocolModel):
    adb_id: str  # как шлем виден в adb: серийный номер или ip:порт
    transport: Literal["usb", "wifi"]
    state: str
    status: str
    bundled_version: str
    serial: str | None = None
    model: str | None = None
    installed_version: str | None = None
    permissions_ok: bool | None = None
    headset_id: str | None = None
    label: str | None = None


class SetupJob(ProtocolModel):
    id: str
    kind: Literal["install", "update", "remove"]
    adb_id: str
    status: Literal["running", "waiting_user", "done", "failed"]
    log: list[str] = Field(default_factory=list)
    error: str | None = None


class FleetHeadset(ProtocolModel):
    """Шлем в базе: можно ли обновить его по Wi-Fi."""

    headset_id: str
    label: str
    online: bool
    agent_version: str | None
    adb: AdbStatus | None
    # current · outdated · newer · unknown · needs_cable (агент слишком старый для обновления по Wi-Fi)
    status: str


class SetupInfo(ProtocolModel):
    bundled_version: str
    devices: list[SetupDevice]
    fleet: list[FleetHeadset] = Field(default_factory=list)
    job: SetupJob | None = None


class WifiUpdateRequest(ProtocolModel):
    headset_ids: list[str] = Field(min_length=1, max_length=200)


class SetupRequest(ProtocolModel):
    kind: Literal["install", "update", "remove"]
    adb_id: str = Field(min_length=1, max_length=64)
    label: str | None = Field(default=None, max_length=64)


# ---------- вход на дашборд ----------


class AuthStatus(ProtocolModel):
    configured: bool  # пароль уже задан
    authenticated: bool
    can_setup: bool  # задать пароль можно только с компьютера-сервера


class AuthRequest(ProtocolModel):
    password: str = Field(min_length=1, max_length=200)
