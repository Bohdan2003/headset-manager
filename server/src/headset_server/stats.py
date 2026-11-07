"""Статистика за период: время игры, сессии, выходы, возвраты охраной, батарея, обрывы связи."""

from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from .db import Event, GameSession, Headset, HeadsetApp, utcnow
from .protocol import Stats, StatsDay, StatsGame, StatsHeadset, StatsPeriod, StatsTotals

DAYS = {"today": 1, "7d": 7, "30d": 30}
OPERATOR_REASONS = {"closed", "menu", "restarted"}
# Обрыв — шлем пропал сам. Не считаются: сон, перезагрузка и выключение, остановка сервера
DROP_REASONS = {"dropped", "error", "timeout"}
# Между двумя замерами батареи дольше этого — шлем, скорее всего, спал; такой участок не считаем
MAX_BATTERY_GAP = timedelta(minutes=30)
MIN_BATTERY_SPAN = timedelta(minutes=10)


def period_bounds(period: StatsPeriod, now: datetime | None = None) -> tuple[datetime, datetime]:
    """Начало периода — местная полночь (сервер стоит на арене, его часовой пояс — пояс арены)."""
    now = now or utcnow()
    local_now = now.astimezone()
    start_local = local_now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=DAYS[period] - 1)
    return start_local.astimezone(UTC), now


async def compute(session_factory: async_sessionmaker, period: StatsPeriod) -> Stats:
    start, end = period_bounds(period)
    async with session_factory() as s:
        headsets = {h.id: h.label for h in (await s.execute(select(Headset))).scalars()}
        titles = {a.package: a.title for a in (await s.execute(select(HeadsetApp))).scalars()}
        sessions = (
            await s.execute(
                select(GameSession).where(
                    GameSession.started_at < end,
                    or_(GameSession.ended_at.is_(None), GameSession.ended_at > start),
                )
            )
        ).scalars().all()
        events = (
            await s.execute(
                select(Event)
                .where(Event.ts >= start, Event.ts <= end, Event.type.in_(("battery", "disconnect", "charging")))
                .order_by(Event.headset_id, Event.ts)
            )
        ).scalars().all()

    games: dict[str, dict] = defaultdict(lambda: defaultdict(int))
    per_headset: dict[str, dict] = defaultdict(lambda: defaultdict(int))
    per_day: dict[str, float] = defaultdict(float)

    for row in sessions:
        s_start = max(_utc(row.started_at), start)
        s_end = min(_utc(row.ended_at) if row.ended_at else end, end)
        if s_end <= s_start:
            continue
        play = (s_end - s_start).total_seconds()
        g = games[row.package]
        g["play_s"] += play
        g["sessions"] += 1
        g["exits"] += row.exits
        g["guard_returns"] += row.guard_returns
        if row.end_reason == "exited":
            g["ended_by_player"] += 1
        elif row.end_reason in OPERATOR_REASONS:
            g["ended_by_operator"] += 1
        h = per_headset[row.headset_id]
        h["play_s"] += play
        h["sessions"] += 1
        _split_by_day(s_start, s_end, per_day)

    drain: dict[str, tuple[float, float]] = defaultdict(lambda: (0.0, 0.0))  # (сколько %, сколько секунд)
    prev: Event | None = None
    for ev in events:
        if ev.type == "disconnect":
            # Записи без screenOn — старые: в них нельзя отличить обрыв от сна, поэтому не считаем
            if ev.payload.get("reason") in DROP_REASONS and "screenOn" in ev.payload:
                per_headset[ev.headset_id]["disconnects"] += 1
            continue
        if ev.type == "charging":
            level = ev.payload.get("level")
            if not ev.payload.get("charging") and isinstance(level, int) and level < 100:
                per_headset[ev.headset_id]["charge_interruptions"] += 1
            continue
        if prev is not None and prev.headset_id == ev.headset_id:
            gap = _utc(ev.ts) - _utc(prev.ts)
            p_level, level = prev.payload.get("level"), ev.payload.get("level")
            if (
                not prev.payload.get("charging") and not ev.payload.get("charging")
                and isinstance(p_level, int) and isinstance(level, int)
                and level <= p_level and gap <= MAX_BATTERY_GAP
                # во сне батарея почти не тратится: такие участки завысили бы время работы
                and prev.payload.get("screenOn") is not False and ev.payload.get("screenOn") is not False
            ):
                dropped, seconds = drain[ev.headset_id]
                drain[ev.headset_id] = (dropped + p_level - level, seconds + gap.total_seconds())
        prev = ev

    def drain_rate(headset_id: str) -> float | None:
        dropped, seconds = drain.get(headset_id, (0.0, 0.0))
        if seconds < MIN_BATTERY_SPAN.total_seconds():
            return None
        return round(dropped / (seconds / 3600), 1)

    def life(rate: float | None) -> float | None:
        return round(100 / rate, 1) if rate else None

    game_list = sorted(
        (
            StatsGame(
                package=pkg,
                title=titles.get(pkg, pkg.rsplit(".", 1)[-1]),
                play_s=int(g["play_s"]),
                sessions=g["sessions"],
                avg_session_s=int(g["play_s"] / g["sessions"]) if g["sessions"] else 0,
                exits=g["exits"],
                guard_returns=g["guard_returns"],
                ended_by_player=g["ended_by_player"],
                ended_by_operator=g["ended_by_operator"],
            )
            for pkg, g in games.items()
        ),
        key=lambda g: -g.play_s,
    )
    headset_list = sorted(
        (
            StatsHeadset(
                headset_id=hid,
                label=label,
                play_s=int(per_headset[hid]["play_s"]),
                sessions=per_headset[hid]["sessions"],
                disconnects=per_headset[hid]["disconnects"],
                charge_interruptions=per_headset[hid]["charge_interruptions"],
                battery_drain_per_hour=drain_rate(hid),
                battery_life_h=life(drain_rate(hid)),
            )
            for hid, label in headsets.items()
        ),
        key=lambda h: h.label,
    )
    day_list = []
    day = start.astimezone().date()
    while day <= end.astimezone().date():
        day_list.append(StatsDay(date=day.isoformat(), play_s=int(per_day.get(day.isoformat(), 0))))
        day += timedelta(days=1)

    return Stats(
        period=period,
        from_=start,
        to=end,
        totals=StatsTotals(
            play_s=sum(g.play_s for g in game_list),
            sessions=sum(g.sessions for g in game_list),
            exits=sum(g.exits for g in game_list),
            guard_returns=sum(g.guard_returns for g in game_list),
        ),
        games=game_list,
        headsets=headset_list,
        days=day_list,
    )


def _split_by_day(start: datetime, end: datetime, out: dict[str, float]) -> None:
    """Сессия через полночь делится между днями (по местному времени)."""
    cur = start.astimezone()
    end_local = end.astimezone()
    while cur < end_local:
        next_midnight = (cur + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        chunk_end = min(next_midnight, end_local)
        out[cur.date().isoformat()] += (chunk_end - cur).total_seconds()
        cur = chunk_end


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value
