"""Claude API を使った AI 投稿生成"""
from __future__ import annotations
import anthropic
from .config import ANTHROPIC_API_KEY

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        if not ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY を .env に設定してください。")
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


SYSTEM_PROMPT = """あなたは SNS マーケティングの専門家です。
Threads (Meta) 向けの投稿文を作成します。

ルール:
- 500文字以内 (Threads の制限)
- 読者を惹きつける書き出し
- 自然な日本語 (または指定された言語)
- ハッシュタグは最大3つまで
- 絵文字を適度に使って親しみやすく
- 宣伝・スパムっぽくならないようにする
- 投稿本文のみを返す (説明やコメントは不要)
"""


def generate_post(topic: str, tone: str = "informative", extra_instructions: str = "") -> str:
    """指定したトピックで Threads 投稿文を生成する。

    Args:
        topic: 投稿のテーマ・キーワード
        tone: 文体 (informative / casual / inspiring / humorous)
        extra_instructions: 追加指示

    Returns:
        生成された投稿文
    """
    tone_map = {
        "informative": "役に立つ情報を共有する",
        "casual": "友達に話しかけるようなカジュアルな",
        "inspiring": "読者を鼓舞・インスパイアする",
        "humorous": "ユーモアを交えた",
    }
    tone_desc = tone_map.get(tone, tone)

    user_message = f"トピック: {topic}\n文体: {tone_desc}\n"
    if extra_instructions:
        user_message += f"追加指示: {extra_instructions}\n"
    user_message += "\nThreads 投稿文を作成してください。"

    client = _get_client()
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    return message.content[0].text.strip()


def generate_post_with_analysis(topic: str, high_posts: list, low_posts: list, tone: str = "informative") -> str:
    """過去のパフォーマンスデータを元に投稿を生成する。

    Args:
        topic: 投稿のテーマ
        high_posts: 高パフォーマンス投稿のリスト
        low_posts: 低パフォーマンス投稿のリスト
        tone: 文体

    Returns:
        生成された投稿文
    """
    tone_map = {
        "informative": "役に立つ情報を共有する",
        "casual": "友達に話しかけるようなカジュアルな",
        "inspiring": "読者を鼓舞・インスパイアする",
        "humorous": "ユーモアを交えた",
    }
    tone_desc = tone_map.get(tone, tone)

    high_examples = "\n".join(
        f"- いいね{p['likes']} | {p['text'][:80]}" for p in high_posts[:3]
    ) if high_posts else "（データなし）"

    low_examples = "\n".join(
        f"- いいね{p['likes']} | {p['text'][:80]}" for p in low_posts[:3]
    ) if low_posts else "（データなし）"

    user_message = (
        f"トピック: {topic}\n"
        f"文体: {tone_desc}\n\n"
        f"【反応が良かった投稿例（参考にすべきパターン）】\n{high_examples}\n\n"
        f"【反応が少なかった投稿例（避けるべきパターン）】\n{low_examples}\n\n"
        "上記のデータを分析し、反応が良かった投稿の特徴を活かして、"
        "新しいThreads投稿文を1つ作成してください。"
    )

    client = _get_client()
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    return message.content[0].text.strip()


def generate_post_batch(topic: str, count: int = 5, tone: str = "informative") -> list[str]:
    """複数の投稿案を一度に生成する。"""
    client = _get_client()
    tone_map = {
        "informative": "役に立つ情報を共有する",
        "casual": "友達に話しかけるようなカジュアルな",
        "inspiring": "読者を鼓舞・インスパイアする",
        "humorous": "ユーモアを交えた",
    }
    tone_desc = tone_map.get(tone, tone)

    user_message = (
        f"トピック: {topic}\n"
        f"文体: {tone_desc}\n"
        f"バリエーションを {count} 個作成してください。\n"
        "各投稿を '---' で区切って出力してください。"
    )

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    raw = message.content[0].text.strip()
    posts = [p.strip() for p in raw.split("---") if p.strip()]
    return posts[:count]
