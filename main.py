#!/usr/bin/env python3
"""Threads 自動化 CLI"""
import signal
import sys
import time
from datetime import datetime

import click
from rich.console import Console
from rich.panel import Panel

console = Console()


@click.group()
def cli():
    """Threads アカウント自動化ツール"""
    pass


# ------------------------------------------------------------------ #
# 投稿コマンド
# ------------------------------------------------------------------ #

@cli.command("post")
@click.option("--text", "-t", help="投稿本文 (省略すると AI 生成)")
@click.option("--topic", "-p", default="日常", show_default=True, help="AI 生成時のトピック")
@click.option("--tone", default="informative", show_default=True,
              type=click.Choice(["informative", "casual", "inspiring", "humorous"]),
              help="AI 生成時の文体")
def post_cmd(text, topic, tone):
    """今すぐ Threads に投稿する。"""
    from threads_bot.threads_client import ThreadsClient
    from threads_bot.generator import generate_post

    if not text:
        console.print(f"[cyan]AI で投稿文を生成中... (トピック: {topic})[/cyan]")
        text = generate_post(topic, tone)
        console.print(Panel(text, title="生成された投稿"))
        if not click.confirm("この内容で投稿しますか？"):
            console.print("[yellow]キャンセルしました。[/yellow]")
            return

    client = ThreadsClient()
    post_id = client.create_text_post(text)
    console.print(f"[green]✓ 投稿しました！ Threads ID: {post_id}[/green]")


@cli.command("generate")
@click.option("--topic", "-p", default="日常", show_default=True, help="投稿テーマ")
@click.option("--tone", default="informative", show_default=True,
              type=click.Choice(["informative", "casual", "inspiring", "humorous"]))
@click.option("--count", "-n", default=3, show_default=True, help="生成する案の数")
def generate_cmd(topic, tone, count):
    """AI で投稿案を複数生成して表示する (投稿はしない)。"""
    from threads_bot.generator import generate_post_batch

    console.print(f"[cyan]{count} 件の投稿案を生成中...[/cyan]")
    posts = generate_post_batch(topic, count, tone)
    for i, post in enumerate(posts, 1):
        console.print(Panel(post, title=f"案 {i}/{len(posts)}"))


# ------------------------------------------------------------------ #
# スケジュールコマンド
# ------------------------------------------------------------------ #

@cli.command("schedule")
@click.option("--text", "-t", help="投稿本文 (省略すると AI 生成)")
@click.option("--topic", "-p", default="日常", show_default=True, help="AI 生成時のトピック")
@click.option("--at", required=True, help="投稿日時 (例: '2024-12-31 09:00')")
def schedule_cmd(text, topic, at):
    """指定日時に1回だけ投稿をスケジュールする。"""
    from threads_bot.scheduler import schedule_one_time
    from threads_bot.generator import generate_post

    run_at = datetime.strptime(at, "%Y-%m-%d %H:%M")

    if not text:
        console.print(f"[cyan]AI で投稿文を生成中...[/cyan]")
        text = generate_post(topic)
        console.print(Panel(text, title="生成された投稿"))
        if not click.confirm("この内容でスケジュールしますか？"):
            console.print("[yellow]キャンセルしました。[/yellow]")
            return

    post_id = schedule_one_time(text, run_at, topic=topic)
    console.print(f"[green]✓ スケジュール完了！ 投稿 ID: {post_id}、実行日時: {run_at}[/green]")
    console.print("[yellow]注意: スケジューラーを起動し続けるには 'python main.py run' を実行してください。[/yellow]")


@cli.command("add-recurring")
@click.option("--topic", "-p", required=True, help="投稿テーマ")
@click.option("--cron", "-c", required=True, help="cron 式 (例: '0 9 * * *' = 毎日9時)")
@click.option("--tone", default="informative", show_default=True,
              type=click.Choice(["informative", "casual", "inspiring", "humorous"]))
@click.option("--analyze", is_flag=True, default=False, help="過去の投稿データを分析して投稿を最適化する")
def add_recurring_cmd(topic, cron, tone, analyze):
    """定期的な AI 投稿ジョブを追加する。"""
    from threads_bot.scheduler import schedule_recurring

    job_id = schedule_recurring(topic, cron, tone, use_analysis=analyze)
    console.print(f"[green]✓ 定期ジョブを追加しました！ ジョブ ID: {job_id}[/green]")
    console.print(f"  トピック: {topic}、スケジュール: {cron}")
    if analyze:
        console.print("  [cyan]分析モード: 過去の投稿パフォーマンスを元に最適化します[/cyan]")


@cli.command("remove-recurring")
@click.argument("job_id")
def remove_recurring_cmd(job_id):
    """定期投稿ジョブを削除する。"""
    from threads_bot.scheduler import remove_recurring

    removed = remove_recurring(job_id)
    if removed:
        console.print(f"[green]✓ ジョブ '{job_id}' を削除しました。[/green]")
    else:
        console.print(f"[red]ジョブ '{job_id}' が見つかりませんでした。[/red]")


@cli.command("jobs")
def jobs_cmd():
    """現在のスケジュールジョブ一覧を表示する。"""
    from threads_bot.database import get_session, ScheduledJob
    from rich.table import Table
    from rich import box

    with get_session() as session:
        jobs = session.query(ScheduledJob).filter_by(active=True).all()

    if not jobs:
        console.print("[yellow]有効なスケジュールジョブはありません。[/yellow]")
        return

    table = Table(title="定期投稿ジョブ", box=box.ROUNDED)
    table.add_column("ジョブ ID", style="cyan")
    table.add_column("トピック")
    table.add_column("cron 式")
    table.add_column("作成日時")

    for job in jobs:
        table.add_row(job.job_id, job.topic, job.cron_expr, str(job.created_at)[:16])

    console.print(table)


@cli.command("run")
def run_cmd():
    """スケジューラーをフォアグラウンドで起動する (Ctrl+C で停止)。"""
    from threads_bot.scheduler import start_scheduler, stop_scheduler, list_jobs

    console.print("[bold green]Threads Bot スケジューラーを起動しています...[/bold green]")
    start_scheduler()

    jobs = list_jobs()
    if jobs:
        console.print(f"[cyan]{len(jobs)} 件のジョブを復元しました。[/cyan]")
    else:
        console.print("[yellow]スケジュールされたジョブがありません。'add-recurring' で追加してください。[/yellow]")

    def _shutdown(sig, frame):
        console.print("\n[yellow]シャットダウン中...[/yellow]")
        stop_scheduler()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    console.print("[dim]Ctrl+C で停止します。[/dim]")
    while True:
        time.sleep(1)


# ------------------------------------------------------------------ #
# 分析コマンド
# ------------------------------------------------------------------ #

@cli.command("report")
@click.option("--days", "-d", default=7, show_default=True, help="集計日数")
@click.option("--posts", "-p", default=10, show_default=True, help="表示する投稿数")
@click.option("--local", "local_only", is_flag=True, help="ローカル DB のみ表示")
def report_cmd(days, posts, local_only):
    """インサイトレポートを表示する。"""
    from threads_bot.analytics import print_user_report, print_post_report, print_db_report

    print_db_report()

    if not local_only:
        try:
            print_user_report(days)
            print_post_report(posts)
        except Exception as e:
            console.print(f"[red]Threads API からのデータ取得に失敗しました: {e}[/red]")
            console.print("[dim]--local フラグを使うとローカル DB のみ表示できます。[/dim]")


if __name__ == "__main__":
    cli()
