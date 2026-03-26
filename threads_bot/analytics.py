"""Threads インサイト取得・レポート生成"""
from datetime import datetime, timedelta
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from .threads_client import ThreadsClient
from .database import get_session, Post

console = Console()


def print_user_report(days: int = 7) -> None:
    """ユーザーレベルのインサイトをコンソールに表示する。"""
    client = ThreadsClient()

    until = int(datetime.now().timestamp())
    since = int((datetime.now() - timedelta(days=days)).timestamp())

    data = client.get_user_insights(since=since, until=until)
    items = data.get("data", [])

    table = Table(title=f"Threads インサイト (過去 {days} 日間)", box=box.ROUNDED)
    table.add_column("指標", style="cyan")
    table.add_column("値", justify="right", style="green")

    label_map = {
        "views": "表示回数",
        "likes": "いいね",
        "replies": "返信",
        "reposts": "リポスト",
        "followers_count": "フォロワー数",
    }

    for item in items:
        name = label_map.get(item.get("name", ""), item.get("name", ""))
        values = item.get("values", [])
        total = sum(v.get("value", 0) for v in values) if values else item.get("total_value", {}).get("value", 0)
        table.add_row(name, f"{total:,}")

    console.print(table)


def print_post_report(limit: int = 10) -> None:
    """最近の投稿パフォーマンスをコンソールに表示する。"""
    client = ThreadsClient()
    posts = client.get_posts(limit=limit)

    table = Table(title=f"最近の投稿パフォーマンス (上位 {limit} 件)", box=box.ROUNDED)
    table.add_column("投稿日時", style="cyan", no_wrap=True)
    table.add_column("本文 (先頭40文字)", style="white")
    table.add_column("いいね", justify="right", style="green")
    table.add_column("返信", justify="right", style="yellow")

    for post in posts:
        text = (post.get("text") or "")[:40]
        ts = post.get("timestamp", "")[:16].replace("T", " ")
        likes = post.get("like_count", 0)
        replies = post.get("replies_count", 0)
        table.add_row(ts, text, str(likes), str(replies))

    console.print(table)


def print_db_report() -> None:
    """ローカル DB の投稿履歴レポートを表示する。"""
    with get_session() as session:
        all_posts = session.query(Post).order_by(Post.created_at.desc()).limit(20).all()

    total = len(all_posts)
    published = sum(1 for p in all_posts if p.status == "published")
    failed = sum(1 for p in all_posts if p.status == "failed")
    pending = sum(1 for p in all_posts if p.status == "pending")

    summary = (
        f"合計: [bold]{total}[/bold]  "
        f"公開済み: [green]{published}[/green]  "
        f"待機中: [yellow]{pending}[/yellow]  "
        f"失敗: [red]{failed}[/red]"
    )
    console.print(Panel(summary, title="投稿ステータス概要", expand=False))

    table = Table(title="直近20件の投稿履歴", box=box.ROUNDED)
    table.add_column("ID", style="dim")
    table.add_column("ステータス")
    table.add_column("トピック")
    table.add_column("本文 (先頭50文字)", style="white")
    table.add_column("作成日時", style="cyan")

    status_style = {"published": "green", "failed": "red", "pending": "yellow"}
    for post in all_posts:
        style = status_style.get(post.status, "white")
        table.add_row(
            str(post.id),
            f"[{style}]{post.status}[/{style}]",
            post.topic or "-",
            (post.content or "")[:50],
            str(post.created_at)[:16],
        )

    console.print(table)
