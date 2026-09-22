"""
تطبيق أندرويد لتصفح مدونة عبدالرحمن المشيقح.

مصمم مع مراعاة إمكانية الوصول:
  - واجهة عربية من اليمين لليسار (RTL) بالكامل.
  - عناصر Toga الأصلية تُقرأ تلقائيًا بواسطة TalkBack.
  - اختصار F5 لإعادة قراءة حالة التطبيق الحالية عبر مربع نصي مخصص للقارئ.
  - تنبيه نظام عند نشر مقال جديد (انظر notifications.py).
"""
from __future__ import annotations

import asyncio

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

from . import notifications
from .wordpress_api import WordPressAPIError, fetch_categories, fetch_latest_post_id, fetch_posts

# فترة فحص المقالات الجديدة أثناء تشغيل التطبيق (بالثواني)
NEW_POST_CHECK_INTERVAL = 30 * 60  # 30 دقيقة

ALL_CATEGORIES_LABEL = "كل التصنيفات"


class BlogApp(toga.App):

    def startup(self):
        self.posts_cache: list[dict] = []
        self.current_category: str | None = None
        self.last_seen_post_id: int | None = None
        self._category_slug_by_name = {}

        # --- شريط الأدوات العلوي: بحث + تصنيفات ---
        self.search_input = toga.TextInput(
            placeholder="ابحث في المقالات...",
            style=Pack(flex=1, padding_left=5),
            on_confirm=self.on_search,
        )
        search_button = toga.Button(
            "بحث", on_press=self.on_search, style=Pack(padding_left=5)
        )
        self.category_selection = toga.Selection(
            items=[ALL_CATEGORIES_LABEL],
            on_change=self.on_category_change,
            style=Pack(width=160),
        )
        refresh_button = toga.Button(
            "تحديث", on_press=self.on_refresh, style=Pack(padding_left=5)
        )

        toolbar_box = toga.Box(
            children=[
                self.category_selection,
                self.search_input,
                search_button,
                refresh_button,
            ],
            style=Pack(direction=ROW, padding=8),
        )

        # --- قائمة المقالات ---
        self.posts_table = toga.Table(
            headings=["المقال", "التاريخ"],
            data=[],
            on_activate=self.on_post_selected,
            style=Pack(flex=1, padding=8),
        )

        # --- شريط حالة نصي مخصص لقارئ الشاشة (مثل بقية برامجي) ---
        self.status_input = toga.MultilineTextInput(
            readonly=True,
            style=Pack(height=50, padding=8),
        )
        self.set_status("مرحبًا بك، اضغط F5 لسماع حالة التطبيق في أي وقت.")

        main_box = toga.Box(
            children=[toolbar_box, self.posts_table, self.status_input],
            style=Pack(direction=COLUMN),
        )

        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = main_box

        # اختصارات لوحة المفاتيح (للوحات المفاتيح الخارجية المتصلة بالجهاز)
        self.commands.add(
            toga.Command(
                self.on_refresh,
                text="تحديث المقالات",
                shortcut=toga.Key.MOD_1 + "r",
                group=toga.Group.COMMANDS,
            ),
            toga.Command(
                self.focus_search,
                text="بحث",
                shortcut=toga.Key.MOD_1 + "f",
                group=toga.Group.COMMANDS,
            ),
            toga.Command(
                self.read_status,
                text="قراءة الحالة",
                shortcut=toga.Key.F5,
                group=toga.Group.COMMANDS,
            ),
        )

        self.main_window.show()

        # تحميل أولي: التصنيفات ثم المقالات، وجدولة فحص المقالات الجديدة
        self.loop.create_task(self.load_initial_data())
        self.loop.create_task(self.watch_for_new_posts())

    # ------------------------------------------------------------------
    # مساعدات إمكانية الوصول
    # ------------------------------------------------------------------
    def set_status(self, message: str) -> None:
        """يحدّث نص شريط الحالة (يُقرأ عند التركيز عليه بواسطة TalkBack)."""
        self.status_input.value = message

    def read_status(self, *args, **kwargs) -> None:
        """F5: ينقل التركيز إلى شريط الحالة لإعادة قراءته."""
        self.status_input.focus()

    def focus_search(self, *args, **kwargs) -> None:
        self.search_input.focus()

    # ------------------------------------------------------------------
    # تحميل البيانات
    # ------------------------------------------------------------------
    async def load_initial_data(self, **kwargs):
        await self.load_categories()
        await self.load_posts()

    async def load_categories(self):
        try:
            categories = await asyncio.to_thread(fetch_categories)
        except WordPressAPIError as exc:
            self.set_status(str(exc))
            return

        items = [ALL_CATEGORIES_LABEL] + [c["name"] for c in categories]
        self._category_slug_by_name = {
            c["name"]: c.get("slug", c["name"]) for c in categories
        }
        self.category_selection.items = items

    async def load_posts(self, search: str | None = None):
        self.set_status("جارٍ تحميل المقالات...")
        category_slug = None
        if self.current_category and self.current_category != ALL_CATEGORIES_LABEL:
            category_slug = self._category_slug_by_name.get(self.current_category)

        try:
            result = await asyncio.to_thread(
                fetch_posts, category=category_slug, search=search, number=30
            )
        except WordPressAPIError as exc:
            self.set_status(str(exc))
            return

        self.posts_cache = result["posts"]
        self.posts_table.data = [
            (p["title"], self._format_date(p["date"])) for p in self.posts_cache
        ]

        if self.posts_cache and self.last_seen_post_id is None:
            self.last_seen_post_id = self.posts_cache[0]["id"]

        count = len(self.posts_cache)
        self.set_status(f"تم تحميل {count} مقالًا.")

    @staticmethod
    def _format_date(iso_date: str) -> str:
        # مثال: 2026-08-18T10:00:00+00:00 -> 2026-08-18
        return iso_date.split("T")[0] if iso_date else ""

    # ------------------------------------------------------------------
    # أحداث الواجهة
    # ------------------------------------------------------------------
    def on_search(self, widget, **kwargs):
        term = self.search_input.value.strip()
        self.loop.create_task(self.load_posts(search=term or None))

    def on_category_change(self, widget, **kwargs):
        self.current_category = self.category_selection.value
        if hasattr(self, "status_input"):
            self.loop.create_task(self.load_posts())

    def on_refresh(self, widget=None, **kwargs):
        self.search_input.value = ""
        self.loop.create_task(self.load_posts())

    def on_post_selected(self, widget, row=None, **kwargs):
        if row is None:
            return
        index = self.posts_table.data.index(row)
        post = self.posts_cache[index]
        self.open_post_detail(post)

    def open_post_detail(self, post: dict) -> None:
        detail_window = toga.Window(title=post["title"])

        html = f"""
        <html dir="rtl" lang="ar">
        <head><meta charset="utf-8">
        <style>
            body {{ font-family: sans-serif; font-size: 18px; padding: 12px; }}
            img {{ max-width: 100%; height: auto; }}
        </style>
        </head>
        <body>
            <h1>{post['title']}</h1>
            <p><em>{self._format_date(post['date'])}</em></p>
            {post['content']}
        </body>
        </html>
        """

        webview = toga.WebView(style=Pack(flex=1))
        webview.set_content(post["url"], html)

        open_browser_button = toga.Button(
            "فتح في المتصفح",
            on_press=lambda w: self.open_in_browser(post["url"]),
            style=Pack(padding=8),
        )

        detail_window.content = toga.Box(
            children=[webview, open_browser_button],
            style=Pack(direction=COLUMN),
        )
        detail_window.show()

    def open_in_browser(self, url: str) -> None:
        import webbrowser

        webbrowser.open(url)

    # ------------------------------------------------------------------
    # فحص المقالات الجديدة وإرسال التنبيهات
    # ------------------------------------------------------------------
    async def watch_for_new_posts(self, **kwargs):
        while True:
            await asyncio.sleep(NEW_POST_CHECK_INTERVAL)
            try:
                latest_id = await asyncio.to_thread(fetch_latest_post_id)
            except WordPressAPIError:
                continue

            if latest_id and self.last_seen_post_id and latest_id != self.last_seen_post_id:
                # مقال جديد منذ آخر فحص: أعد تحميل القائمة وأرسل تنبيهًا
                await self.load_posts()
                new_title = self.posts_cache[0]["title"] if self.posts_cache else ""
                notifications.notify_new_post(new_title, latest_id)
                self.set_status(f"مقال جديد: {new_title}")

            if latest_id:
                self.last_seen_post_id = latest_id


def main():
    return BlogApp(
        formal_name="مدونة عبدالرحمن المشيقح",
        app_id="com.abdualrhmanalmosheqh.blogapp",
    )
