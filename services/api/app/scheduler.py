from __future__ import annotations

import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .data_providers import DataSyncService
from .settings import Settings


def create_scheduler(settings: Settings, sync_service: DataSyncService) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.app_timezone)
    trigger = CronTrigger.from_crontab(settings.data_sync_cron, timezone=settings.app_timezone)
    scheduler.add_job(
        lambda: asyncio.create_task(sync_service.refresh_watchlist()),
        trigger=trigger,
        id="daily-market-data-refresh",
        replace_existing=True,
        max_instances=1,
    )
    return scheduler
