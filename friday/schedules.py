"""定时任务 CRUD —— 持久化到 %APPDATA%/Friday/schedules.json。"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from friday.io_utils import atomic_write_json, load_json
from friday.logging_config import get_logger
from friday.paths import get_appdata_dir

_log = get_logger("schedules")

_WEEKDAY_LABELS = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
_RETRY_DELAY_SEC = 300


@dataclass
class ScheduledTask:
    id: str
    title: str
    prompt: str
    frequency: str = "weekly"  # daily | weekly | interval | cron
    day_of_week: int = 4
    hour: int = 9
    minute: int = 0
    cron_expr: str = ""
    interval_hours: int = 6
    enabled: bool = True
    retry_on_failure: bool = True
    max_retries: int = 1
    retry_count: int = 0
    last_run_at: float | None = None
    next_run_at: float | None = None
    last_run_status: str = ""
    last_run_message: str = ""
    created_at: float = field(default_factory=time.time)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScheduledTask:
        return cls(
            id=str(data.get("id", uuid.uuid4().hex[:12])),
            title=str(data.get("title", "未命名任务")),
            prompt=str(data.get("prompt", "")),
            frequency=str(data.get("frequency", "weekly")),
            day_of_week=int(data.get("day_of_week", 4)),
            hour=int(data.get("hour", 9)),
            minute=int(data.get("minute", 0)),
            cron_expr=str(data.get("cron_expr", "")),
            interval_hours=max(1, int(data.get("interval_hours", 6))),
            enabled=bool(data.get("enabled", True)),
            retry_on_failure=bool(data.get("retry_on_failure", True)),
            max_retries=max(0, int(data.get("max_retries", 1))),
            retry_count=max(0, int(data.get("retry_count", 0))),
            last_run_at=data.get("last_run_at"),
            next_run_at=data.get("next_run_at"),
            last_run_status=str(data.get("last_run_status", "")),
            last_run_message=str(data.get("last_run_message", ""))[:500],
            created_at=float(data.get("created_at", time.time())),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def schedule_label(self) -> str:
        time_str = f"{self.hour:02d}:{self.minute:02d}"
        if self.frequency == "cron" and self.cron_expr:
            return f"Cron {self.cron_expr}"
        if self.frequency == "interval":
            return f"每 {self.interval_hours} 小时"
        if self.frequency == "daily":
            return f"每天 {time_str}"
        dow = self.day_of_week
        if 0 <= dow <= 6:
            return f"每{_WEEKDAY_LABELS[dow]} {time_str}"
        return f"每周 {time_str}"


def _store_path() -> Path:
    return get_appdata_dir() / "schedules.json"


def compute_next_run(
    frequency: str,
    hour: int,
    minute: int,
    *,
    day_of_week: int = 4,
    cron_expr: str = "",
    interval_hours: int = 6,
    after: float | None = None,
) -> float:
    """计算下次运行时间戳（本地时区）。"""
    now = datetime.now()
    start = datetime.fromtimestamp(after + 1) if after else now
    start = start.replace(second=0, microsecond=0)
    freq = frequency if frequency in {"daily", "weekly", "interval", "cron"} else "weekly"

    if freq == "cron" and cron_expr.strip():
        try:
            from croniter import croniter

            base = start if after else now
            itr = croniter(cron_expr.strip(), base)
            return float(itr.get_next(float))
        except Exception as exc:
            _log.warning("Cron 表达式无效 | expr=%s error=%s", cron_expr, exc)

    if freq == "interval":
        base_ts = after if after is not None else time.time()
        return base_ts + max(1, interval_hours) * 3600

    cursor = start.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if cursor <= start:
        cursor += timedelta(days=1)

    for _ in range(400):
        if freq == "weekly":
            if cursor.weekday() == day_of_week and cursor > start:
                return cursor.timestamp()
        elif cursor > start:
            return cursor.timestamp()
        cursor += timedelta(days=1)
    return (now + timedelta(days=7)).timestamp()


def _refresh_next_run(task: ScheduledTask) -> ScheduledTask:
    if not task.enabled:
        task.next_run_at = None
        return task
    task.next_run_at = compute_next_run(
        task.frequency,
        task.hour,
        task.minute,
        day_of_week=task.day_of_week,
        cron_expr=task.cron_expr,
        interval_hours=task.interval_hours,
        after=task.last_run_at,
    )
    return task


def _load_tasks() -> list[ScheduledTask]:
    raw = load_json(_store_path())
    if not isinstance(raw, list):
        return []
    return [ScheduledTask.from_dict(item) for item in raw]


def _save_tasks(tasks: list[ScheduledTask]) -> None:
    atomic_write_json(_store_path(), [t.to_dict() for t in tasks])


def list_schedules() -> list[ScheduledTask]:
    tasks = _load_tasks()
    tasks.sort(key=lambda t: t.created_at, reverse=True)
    return tasks


def get_schedule(schedule_id: str) -> ScheduledTask | None:
    for task in _load_tasks():
        if task.id == schedule_id:
            return task
    return None


def create_schedule(payload: dict[str, Any]) -> ScheduledTask:
    task = ScheduledTask.from_dict({
        **payload,
        "id": uuid.uuid4().hex[:12],
        "created_at": time.time(),
        "retry_count": 0,
    })
    task = _refresh_next_run(task)
    tasks = _load_tasks()
    tasks.append(task)
    _save_tasks(tasks)
    _log.info("创建定时任务 | id=%s title=%s", task.id, task.title)
    return task


def update_schedule(schedule_id: str, payload: dict[str, Any]) -> ScheduledTask | None:
    tasks = _load_tasks()
    for idx, task in enumerate(tasks):
        if task.id != schedule_id:
            continue
        merged = task.to_dict()
        for key in (
            "title", "prompt", "frequency", "day_of_week", "hour", "minute",
            "cron_expr", "interval_hours", "enabled", "retry_on_failure", "max_retries",
        ):
            if key in payload and payload[key] is not None:
                merged[key] = payload[key]
        updated = ScheduledTask.from_dict(merged)
        updated = _refresh_next_run(updated)
        tasks[idx] = updated
        _save_tasks(tasks)
        return updated
    return None


def delete_schedule(schedule_id: str) -> bool:
    tasks = _load_tasks()
    new_tasks = [t for t in tasks if t.id != schedule_id]
    if len(new_tasks) == len(tasks):
        return False
    _save_tasks(new_tasks)
    return True


def mark_schedule_run(
    schedule_id: str,
    *,
    status: str,
    message: str,
) -> ScheduledTask | None:
    tasks = _load_tasks()
    now = time.time()
    for idx, task in enumerate(tasks):
        if task.id != schedule_id:
            continue
        task.last_run_at = now
        task.last_run_status = status
        task.last_run_message = message[:500]

        if status == "error" and task.retry_on_failure and task.retry_count < task.max_retries:
            task.retry_count += 1
            task.next_run_at = now + _RETRY_DELAY_SEC
            _log.info(
                "定时任务失败，安排重试 | id=%s retry=%d/%d",
                schedule_id, task.retry_count, task.max_retries,
            )
        else:
            task.retry_count = 0
            task = _refresh_next_run(task)

        tasks[idx] = task
        _save_tasks(tasks)
        return task
    return None


def due_schedules(now: float | None = None) -> list[ScheduledTask]:
    """返回当前应执行且已启用的任务。"""
    ts = now if now is not None else time.time()
    result: list[ScheduledTask] = []
    for task in _load_tasks():
        if not task.enabled or not task.next_run_at:
            continue
        if task.next_run_at <= ts:
            result.append(task)
    return result


def failed_schedules_since(since: float) -> list[ScheduledTask]:
    """返回自某时间以来失败且未重试成功的任务（用于通知）。"""
    return [
        t for t in _load_tasks()
        if t.last_run_status == "error" and (t.last_run_at or 0) >= since
    ]
