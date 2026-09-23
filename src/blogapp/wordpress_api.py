"""
طبقة الاتصال بواجهة WordPress.com REST API v1.1 لمدونة
abdualrhmanalmosheqh.com — بدون الحاجة لأي سيرفر خاص.

التوثيق: https://developer.wordpress.com/docs/api/1.1/get/sites/%24site/posts/
"""
from __future__ import annotations

import httpx

SITE = "abdualrhmanalmosheqh.com"
BASE_URL = f"https://public-api.wordpress.com/rest/v1.1/sites/{SITE}"

# مهلة الشبكة بالثواني
TIMEOUT = 15


class WordPressAPIError(Exception):
    """خطأ في الاتصال بواجهة المدونة."""


def _get(path: str, params: dict | None = None) -> dict:
    url = f"{BASE_URL}{path}"
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            response = client.get(url, params=params or {})
            response.raise_for_status()
            return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise WordPressAPIError(f"تعذّر الاتصال بالمدونة: {exc}") from exc


def fetch_categories() -> list[dict]:
    """يرجع قائمة التصنيفات المتاحة في المدونة (الاسم والمعرّف/slug)."""
    data = _get("/categories/")
    categories = data.get("categories", [])
    # استبعاد تصنيفات فارغة أو غير مستخدمة
    return [c for c in categories if c.get("post_count", 0) > 0]


def fetch_posts(
    category: str | None = None,
    search: str | None = None,
    number: int = 20,
    page_handle: str | None = None,
    page: int = 1,
) -> dict:
    """
    يرجع dict فيه:
      - "posts": قائمة المقالات (كل عنصر dict فيه ID, title, date, excerpt,
        content, URL, categories, featured_image)
      - "next_page_handle": مؤشر الصفحة التالية إن وجدت (للتصفح المتدرج)
    """
    params: dict = {"number": number}
    if page > 1:
        params["page"] = page
    if category:
        params["category"] = category
    if search:
        params["search"] = search
    if page_handle:
        params["page_handle"] = page_handle

    data = _get("/posts/", params=params)
    posts = []
    for p in data.get("posts", []):
        posts.append(
            {
                "id": p.get("ID"),
                "title": p.get("title", "بدون عنوان"),
                "date": p.get("date", ""),
                "excerpt": p.get("excerpt", ""),
                "content": p.get("content", ""),
                "url": p.get("URL", ""),
                "categories": list(p.get("categories", {}).keys()),
                "featured_image": p.get("featured_image", ""),
            }
        )
    return {
        "posts": posts,
        "next_page_handle": data.get("meta", {}).get("next_page"),
        "found": data.get("found", len(posts)),
    }


def fetch_latest_post_id() -> int | None:
    """يرجع معرّف أحدث مقال منشور — يُستخدم لفحص وجود مقال جديد."""
    data = _get("/posts/", params={"number": 1})
    posts = data.get("posts", [])
    if posts:
        return posts[0].get("ID")
    return None

def fetch_all_posts() -> list[dict]:
    """Load all published posts before ranking, not just the first page."""
    posts = {}
    page = 1
    while True:
        result = fetch_posts(number=100, page=page)
        previous = len(posts)
        posts.update((p['id'],p) for p in result['posts'])
        if len(posts) >= result['found'] or len(posts) == previous:
            break
        page += 1
    return list(posts.values())
