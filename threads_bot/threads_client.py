"""Threads Graph API クライアント"""
import time
import requests
from .config import THREADS_API_BASE, THREADS_ACCESS_TOKEN, THREADS_USER_ID


class ThreadsAPIError(Exception):
    pass


class ThreadsClient:
    def __init__(self, access_token: str = THREADS_ACCESS_TOKEN, user_id: str = THREADS_USER_ID):
        if not access_token or not user_id:
            raise ThreadsAPIError(
                "THREADS_ACCESS_TOKEN と THREADS_USER_ID を .env に設定してください。"
            )
        self.access_token = access_token
        self.user_id = user_id
        self.base = THREADS_API_BASE

    def _get(self, path: str, params: dict | None = None) -> dict:
        params = params or {}
        params["access_token"] = self.access_token
        resp = requests.get(f"{self.base}/{path}", params=params, timeout=30)
        self._raise_for_status(resp)
        return resp.json()

    def _post(self, path: str, data: dict) -> dict:
        data["access_token"] = self.access_token
        resp = requests.post(f"{self.base}/{path}", data=data, timeout=30)
        self._raise_for_status(resp)
        return resp.json()

    @staticmethod
    def _raise_for_status(resp: requests.Response) -> None:
        if not resp.ok:
            try:
                err = resp.json().get("error", {})
                msg = err.get("message", resp.text)
            except Exception:
                msg = resp.text
            raise ThreadsAPIError(f"Threads API エラー ({resp.status_code}): {msg}")

    # ------------------------------------------------------------------ #
    # 投稿
    # ------------------------------------------------------------------ #

    def create_text_post(self, text: str) -> str:
        """テキスト投稿を作成して投稿IDを返す。"""
        # Step 1: メディアコンテナ作成
        container = self._post(
            f"{self.user_id}/threads",
            {"media_type": "TEXT", "text": text},
        )
        container_id = container.get("id")
        if not container_id:
            raise ThreadsAPIError(f"コンテナ作成失敗: {container}")

        # Step 2: 公開 (少し待機してから)
        time.sleep(2)
        result = self._post(
            f"{self.user_id}/threads_publish",
            {"creation_id": container_id},
        )
        post_id = result.get("id")
        if not post_id:
            raise ThreadsAPIError(f"公開失敗: {result}")
        return post_id

    # ------------------------------------------------------------------ #
    # インサイト (分析)
    # ------------------------------------------------------------------ #

    def get_user_insights(self, metrics: list[str] | None = None, since: int | None = None, until: int | None = None) -> dict:
        """ユーザーレベルのインサイトを取得する。"""
        default_metrics = ["views", "likes", "replies", "reposts", "followers_count"]
        params: dict = {"metric": ",".join(metrics or default_metrics)}
        if since:
            params["since"] = since
        if until:
            params["until"] = until
        return self._get(f"{self.user_id}/threads_insights", params)

    def get_post_insights(self, post_id: str) -> dict:
        """投稿ごとのインサイトを取得する。"""
        metrics = "views,likes,replies,reposts,quotes"
        return self._get(f"{post_id}/insights", {"metric": metrics})

    def get_posts(self, limit: int = 10) -> list[dict]:
        """最近の投稿一覧を取得する。"""
        data = self._get(
            f"{self.user_id}/threads",
            {"fields": "id,text,timestamp,like_count,replies_count", "limit": limit},
        )
        return data.get("data", [])
