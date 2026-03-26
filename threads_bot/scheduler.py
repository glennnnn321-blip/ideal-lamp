"""APScheduler を使ったスケジュール投稿管理"""
from __future__ import annotations
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
import pytz

from .config import TIMEZONE
from .database import get_session, Post, ScheduledJob
from .threads_client import ThreadsClient
from .generator import generate_post

_scheduler: BackgroundScheduler | None = None


def _get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(timezone=TIMEZONE)
    return _scheduler


# ------------------------------------------------------------------ #
# ジョブ実行関数
# ------------------------------------------------------------------ #

def _publish_post(post_id: int) -> None:
    """DB に保存された投稿を Threads に公開する。"""
    with get_session() as session:
        post = session.get(Post, post_id)
        if post is None or post.status != "pending":
            return
        try:
            client = ThreadsClient()
            threads_id = client.create_text_post(post.content)
            post.threads_post_id = threads_id
            post.status = "published"
            post.published_at = datetime.utcnow()
        except Exception as e:
            post.status = "failed"
            post.error_message = str(e)
        session.commit()


def _generate_and_publish(topic: str, tone: str = "informative") -> None:
    """AI で投稿を生成して即座に公開する。"""
    content = generate_post(topic, tone)
    with get_session() as session:
        post = Post(content=content, topic=topic, status="pending")
        session.add(post)
        session.flush()
        post_id = post.id
        session.commit()
    _publish_post(post_id)


# ------------------------------------------------------------------ #
# スケジュール管理 API
# ------------------------------------------------------------------ #

def schedule_one_time(content: str, run_at: datetime, topic: str = "") -> int:
    """指定日時に1回だけ投稿する。

    Returns:
        DB の post.id
    """
    tz = pytz.timezone(TIMEZONE)
    if run_at.tzinfo is None:
        run_at = tz.localize(run_at)

    with get_session() as session:
        post = Post(content=content, topic=topic, status="pending", scheduled_at=run_at)
        session.add(post)
        session.flush()
        post_id = post.id
        session.commit()

    scheduler = _get_scheduler()
    if not scheduler.running:
        scheduler.start()

    scheduler.add_job(
        _publish_post,
        trigger=DateTrigger(run_date=run_at),
        args=[post_id],
        id=f"post_{post_id}",
        replace_existing=True,
    )
    return post_id


def schedule_recurring(topic: str, cron_expr: str, tone: str = "informative") -> str:
    """cron 式で定期的に AI 投稿を生成・公開する。

    Args:
        topic: 投稿テーマ
        cron_expr: cron 式 (例: "0 9 * * *" = 毎日9時)
        tone: 文体

    Returns:
        ジョブ ID
    """
    parts = cron_expr.split()
    if len(parts) != 5:
        raise ValueError("cron_expr は '分 時 日 月 曜日' の5フィールド形式にしてください。例: '0 9 * * *'")

    minute, hour, day, month, day_of_week = parts
    trigger = CronTrigger(
        minute=minute, hour=hour, day=day,
        month=month, day_of_week=day_of_week,
        timezone=TIMEZONE,
    )

    job_id = f"recurring_{topic[:20]}_{cron_expr.replace(' ', '_')}"
    scheduler = _get_scheduler()
    if not scheduler.running:
        scheduler.start()

    scheduler.add_job(
        _generate_and_publish,
        trigger=trigger,
        kwargs={"topic": topic, "tone": tone},
        id=job_id,
        replace_existing=True,
    )

    with get_session() as session:
        existing = session.query(ScheduledJob).filter_by(job_id=job_id).first()
        if existing:
            existing.active = True
            existing.cron_expr = cron_expr
        else:
            job = ScheduledJob(job_id=job_id, topic=topic, cron_expr=cron_expr)
            session.add(job)
        session.commit()

    return job_id


def remove_recurring(job_id: str) -> bool:
    """定期ジョブを削除する。"""
    scheduler = _get_scheduler()
    try:
        scheduler.remove_job(job_id)
    except Exception:
        pass

    with get_session() as session:
        job = session.query(ScheduledJob).filter_by(job_id=job_id).first()
        if job:
            job.active = False
            session.commit()
            return True
    return False


def list_jobs() -> list[dict]:
    """現在のスケジュールジョブ一覧を返す。"""
    scheduler = _get_scheduler()
    jobs = scheduler.get_jobs() if scheduler.running else []
    return [
        {
            "id": j.id,
            "next_run": str(j.next_run_time),
            "trigger": str(j.trigger),
        }
        for j in jobs
    ]


def start_scheduler() -> None:
    """スケジューラを起動し、DB の定期ジョブを復元する。"""
    scheduler = _get_scheduler()
    if not scheduler.running:
        scheduler.start()

    # DB から有効なジョブを復元
    with get_session() as session:
        active_jobs = session.query(ScheduledJob).filter_by(active=True).all()
        for job in active_jobs:
            parts = job.cron_expr.split()
            if len(parts) != 5:
                continue
            minute, hour, day, month, day_of_week = parts
            trigger = CronTrigger(
                minute=minute, hour=hour, day=day,
                month=month, day_of_week=day_of_week,
                timezone=TIMEZONE,
            )
            scheduler.add_job(
                _generate_and_publish,
                trigger=trigger,
                kwargs={"topic": job.topic},
                id=job.job_id,
                replace_existing=True,
            )


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown()
        _scheduler = None
