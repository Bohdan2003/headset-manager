from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON, datetime: DateTime(timezone=True)}


class Headset(Base):
    __tablename__ = "headsets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    label: Mapped[str] = mapped_column(String(64))
    # Серийный номер не меняется даже после сброса к заводским — по нему находим шлем при повторной настройке
    serial: Mapped[str] = mapped_column(String(64), unique=True)
    android_id: Mapped[str | None] = mapped_column(String(32))
    token_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class HeadsetState(Base):
    """Последнее известное состояние шлема (снимок того, что держит в памяти Registry)."""

    __tablename__ = "headset_state"

    headset_id: Mapped[str] = mapped_column(ForeignKey("headsets.id"), primary_key=True)
    online: Mapped[bool] = mapped_column(Boolean, default=False)
    battery: Mapped[int | None] = mapped_column(Integer)
    charging: Mapped[bool | None] = mapped_column(Boolean)
    temp: Mapped[float | None] = mapped_column(Float)
    current_pkg: Mapped[str | None] = mapped_column(String(255))
    adb: Mapped[str | None] = mapped_column(String(32))
    sleep_disabled: Mapped[bool | None] = mapped_column(Boolean)
    agent_version: Mapped[str | None] = mapped_column(String(32))
    last_seen: Mapped[datetime | None]
    guard_pkg: Mapped[str | None] = mapped_column(String(255))


class HeadsetApp(Base):
    """Игры и приложения, установленные на шлеме (присылает агент)."""

    __tablename__ = "headset_apps"

    headset_id: Mapped[str] = mapped_column(ForeignKey("headsets.id"), primary_key=True)
    package: Mapped[str] = mapped_column(String(255), primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    vr: Mapped[bool | None] = mapped_column(Boolean)


class CommandRow(Base):
    """Каждая команда шлему и её результат — для истории и разбора проблем."""

    __tablename__ = "commands"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    headset_id: Mapped[str] = mapped_column(ForeignKey("headsets.id"), index=True)
    cmd: Mapped[str] = mapped_column(String(32))
    params: Mapped[dict[str, Any]] = mapped_column(default=dict)
    status: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str | None] = mapped_column(String(32))
    detail: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    acked_at: Mapped[datetime | None]


class GameSession(Base):
    """
    Сессия игры: пока игра на переднем плане. Короткий выход в меню Meta с возвратом
    в ту же игру (сам или охраной) — та же сессия, но exits/guard_returns растут.
    """

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    headset_id: Mapped[str] = mapped_column(ForeignKey("headsets.id"), index=True)
    package: Mapped[str] = mapped_column(String(255), index=True)
    started_at: Mapped[datetime] = mapped_column(index=True)
    ended_at: Mapped[datetime | None]
    # exited — игрок вышел сам; closed — оператор закрыл игру; restarted — оператор перезапустил игру;
    # menu — оператор вывел в меню; power_button — кнопка питания под защитой, игра перезапущена;
    # switched — запущена другая игра; offline — шлем пропал из сети; server_restart / server_shutdown
    end_reason: Mapped[str | None] = mapped_column(String(32))
    exits: Mapped[int] = mapped_column(Integer, default=0)
    guard_returns: Mapped[int] = mapped_column(Integer, default=0)


class Event(Base):
    """Журнал событий — из него потом считается статистика."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    headset_id: Mapped[str] = mapped_column(ForeignKey("headsets.id"), index=True)
    ts: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    type: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict[str, Any]] = mapped_column(default=dict)


def make_engine(url: str) -> AsyncEngine:
    return create_async_engine(url)


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(engine, expire_on_commit=False)
