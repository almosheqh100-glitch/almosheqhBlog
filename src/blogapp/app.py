"""Arabic blog reader with a category-first home screen."""
from __future__ import annotations
import asyncio
import html
import json
from pathlib import Path
from functools import partial
from urllib.parse import urlparse
import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW
from . import notifications
from .wordpress_api import WordPressAPIError, fetch_categories, fetch_posts
from .presentation import ordered_categories, category_label, post_label
from .views import fetch_snapshot, parse_snapshot, attach_views

NEW_POST_CHECK_INTERVAL = 30 * 60

class BlogApp(toga.App):
    def startup(self):
        self.current_category = None
        self.current_search = None
        self.posts_cache = []
        self.page = 1
        self._request_id = 0
        self._showing_home = True
        self._loading = False
        self.last_seen_post_id = None
        self.view_counts = {}
        self.views_updated = None
        try:
            snapshot = json.loads((self.paths.data / 'views.json').read_text(encoding='utf-8'))
            self.view_counts, self.views_updated = parse_snapshot(snapshot)
        except (OSError, ValueError, KeyError, TypeError):
            pass
        self.categories = json.loads(Path(__file__).with_name("categories.json").read_text(encoding="utf-8"))
        try:
            self.categories = json.loads((self.paths.data / "categories.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
        self.social_links = json.loads(Path(__file__).with_name("social.json").read_text(encoding="utf-8"))
        self.status_input = toga.MultilineTextInput(readonly=True, style=Pack(height=65, margin=8))
        self.search_input = toga.TextInput(placeholder="ابحث في المدونة...", on_confirm=self.on_search, style=Pack(flex=1))
        search_row = toga.Box(children=[self.search_input, toga.Button("بحث", on_press=self.on_search, style=Pack(margin_left=6))], style=Pack(direction=ROW, margin=8))
        self.category_box = toga.Box(style=Pack(direction=COLUMN, margin=8))
        self.render_categories()
        social_box = toga.Box(style=Pack(direction=COLUMN, margin=8))
        social_box.add(toga.Label("تابعني على", style=Pack(font_weight="bold", margin_bottom=8)))
        for label, url in self.social_links.items():
            social_box.add(toga.Button(label, on_press=partial(self.open_link, url), style=Pack(height=48, margin_bottom=6)))
        home_content = toga.Box(children=[
            toga.Label("مدونة عبدالرحمن المشيقح", style=Pack(font_size=20, font_weight="bold", margin=8)),
            toga.Label("اختر التصنيف الذي تريد تصفحه", style=Pack(margin=8)), self.category_box,
            toga.Button("أحدث المقالات من جميع التصنيفات", on_press=self.show_all_posts, style=Pack(height=48, margin=8)), social_box,
            toga.Button("تحديث التصنيفات والأعداد", on_press=self.refresh_categories, style=Pack(height=48, margin=8)),
        ], style=Pack(direction=COLUMN))
        self.home_view = toga.ScrollContainer(content=home_content, horizontal=False, style=Pack(flex=1))
        self.posts_box = toga.Box(style=Pack(direction=COLUMN, margin=8))
        self.posts_heading = toga.Label("المقالات", style=Pack(font_size=18, font_weight="bold", margin=8))
        self.more_button = toga.Button("تحميل المزيد", on_press=self.load_more, style=Pack(height=48, margin=8))
        self.posts_view = toga.Box(children=[
            toga.Button("العودة إلى التصنيفات", on_press=self.show_home, style=Pack(height=48, margin=8)), self.posts_heading,
            toga.ScrollContainer(content=self.posts_box, horizontal=False, style=Pack(flex=1)), self.more_button,
        ], style=Pack(direction=COLUMN, flex=1))
        self.body = toga.Box(children=[self.home_view], style=Pack(direction=COLUMN, flex=1))
        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = toga.Box(children=[search_row, self.body, self.status_input], style=Pack(direction=COLUMN))
        self.main_window.show()
        self.set_status("الأعداد المحفوظة؛ جارٍ تحديثها من المدونة...")
        self.loop.create_task(self.load_categories())
        self.loop.create_task(self.watch_for_new_posts())

    def set_status(self, text):
        self.status_input.value = text

    def render_categories(self):
        self.category_box.clear()
        for category in ordered_categories(self.categories):
            self.category_box.add(toga.Button(category_label(category), on_press=partial(self.select_category, category), style=Pack(height=54, margin_bottom=8, font_size=17)))

    async def load_categories(self):
        try:
            categories = await asyncio.to_thread(fetch_categories)
        except WordPressAPIError:
            if self._showing_home:
                self.set_status("تعذر تحديث التصنيفات. الأعداد المعروضة هي آخر أعداد محفوظة؛ حاول عند توفر الإنترنت.")
            return
        self.categories = categories
        self.render_categories()
        try:
            self.paths.data.mkdir(parents=True, exist_ok=True)
            (self.paths.data / "categories.json").write_text(json.dumps(categories, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
        if self._showing_home:
            self.set_status("تم تحديث التصنيفات والأعداد من المدونة.")

    async def refresh_categories(self, widget, **kwargs):
        self.set_status("جارٍ تحديث التصنيفات...")
        await self.load_categories()

    def show_home(self, widget=None, **kwargs):
        self._request_id += 1
        self._showing_home = True
        self._loading = False
        self.current_category = None
        self.search_input.value = ""
        self.body.clear()
        self.body.add(self.home_view)
        self.set_status("اختر أحد التصنيفات أو أحد روابط التواصل الاجتماعي.")

    def select_category(self, category, widget=None, **kwargs):
        self.current_category = category
        self.search_input.value = ""
        self.begin_posts()

    def show_all_posts(self, widget=None, **kwargs):
        self.current_category = None
        self.search_input.value = ""
        self.begin_posts()

    def on_search(self, widget=None, **kwargs):
        self.begin_posts(self.search_input.value.strip() or None)

    def begin_posts(self, search=None):
        self._request_id += 1
        self._showing_home = False
        self.current_search = search
        self.posts_cache = []
        self.page = 1
        self.posts_box.clear()
        title = self.current_category["name"] if self.current_category else "جميع المقالات"
        self.posts_heading.text = f"{title} — نتائج البحث" if search else title
        self.body.clear()
        self.body.add(self.posts_view)
        self.loop.create_task(self.load_posts(self._request_id, 1))

    async def load_posts(self, request_id, page):
        if request_id != self._request_id:
            return
        self._loading = True
        self.more_button.enabled = False
        self.set_status("جارٍ تحميل المقالات...")
        category_slug = self.current_category["slug"] if self.current_category else None
        if page == 1:
            await self.refresh_views()
            if request_id != self._request_id:
                return
        try:
            result = await asyncio.to_thread(fetch_posts, category=category_slug, search=self.current_search, number=30, page=page)
        except WordPressAPIError as exc:
            if request_id == self._request_id:
                self._loading = False
                self.more_button.enabled = True
                self.more_button.text = "إعادة المحاولة"
                self.set_status(str(exc))
            return
        if request_id != self._request_id:
            return
        existing = {post["id"] for post in self.posts_cache}
        new_posts = attach_views([post for post in result["posts"] if post["id"] not in existing], self.view_counts)
        self.posts_cache.extend(new_posts)
        for post in new_posts:
            self.posts_box.add(toga.Button(post_label(post), on_press=partial(self.open_post_detail, post), style=Pack(margin_bottom=4, height=72)))
            self.posts_box.add(toga.Label(post["date"].split("T")[0], style=Pack(margin_bottom=12)))
        self.page = page
        self._loading = False
        more = bool(new_posts) and len(self.posts_cache) < result["found"]
        self.more_button.enabled = more
        self.more_button.text = "تحميل المزيد" if more else "لا توجد مقالات أخرى"
        self.set_status(f"عرض {len(self.posts_cache)} من {result['found']} مقالًا." if self.posts_cache else "لا توجد مقالات مطابقة.")
        if self.views_updated:
            stamp = self.views_updated.astimezone().strftime('%Y-%m-%d %H:%M')
            self.set_status(self.status_input.value + f" آخر تحديث للمشاهدات: {stamp}.")

    async def refresh_views(self):
        try:
            snapshot = await asyncio.to_thread(fetch_snapshot)
            counts, updated = parse_snapshot(snapshot)
        except Exception:
            # Stats failure must not block article browsing; retain dated cache.
            return
        self.view_counts, self.views_updated = counts, updated
        try:
            self.paths.data.mkdir(parents=True, exist_ok=True)
            (self.paths.data / 'views.json').write_text(json.dumps(snapshot), encoding='utf-8')
        except OSError:
            pass

    async def load_more(self, widget, **kwargs):
        if not self._loading:
            await self.load_posts(self._request_id, self.page + 1 if self.posts_cache else 1)

    def open_post_detail(self, post, widget=None, **kwargs):
        detail_window = toga.Window(title=html.unescape(post["title"]))
        webview = toga.WebView(style=Pack(flex=1))
        content = f'''<!doctype html><html dir="rtl" lang="ar"><head>
        <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
        <style>body{{font:18px sans-serif;line-height:1.8;padding:12px;overflow-wrap:anywhere}}img,video,iframe{{max-width:100%;height:auto}}</style>
        </head><body><h1>{html.escape(html.unescape(post['title']))}</h1>{post['content']}</body></html>'''
        webview.set_content(post["url"], content)
        detail_window.content = toga.Box(children=[
            toga.Button("العودة إلى المقالات", on_press=lambda w: detail_window.close(), style=Pack(height=48, margin=8)), webview,
            toga.Button("فتح المقال في المتصفح", on_press=partial(self.open_link, post["url"]), style=Pack(height=48, margin=8)),
        ], style=Pack(direction=COLUMN))
        detail_window.show()

    def open_link(self, url, widget=None, **kwargs):
        if urlparse(url).scheme not in {"https", "http"}:
            return
        try:
            from java import jclass
            context = jclass("org.beeware.android.MainActivity").singletonThis
            intent = jclass("android.content.Intent")("android.intent.action.VIEW", jclass("android.net.Uri").parse(url))
            context.startActivity(intent)
        except ImportError:
            import webbrowser
            webbrowser.open(url)
        except Exception:
            self.set_status("تعذر فتح الرابط. تأكد من وجود متصفح على الجهاز.")

    async def watch_for_new_posts(self):
        while True:
            try:
                result = await asyncio.to_thread(fetch_posts, number=1)
                if result["posts"]:
                    latest = result["posts"][0]
                    if self.last_seen_post_id is not None and latest["id"] > self.last_seen_post_id:
                        notifications.notify_new_post(html.unescape(latest["title"]), latest["id"])
                    self.last_seen_post_id = latest["id"]
            except WordPressAPIError:
                pass
            await asyncio.sleep(NEW_POST_CHECK_INTERVAL)

def main():
    return BlogApp(formal_name="مدونة عبدالرحمن المشيقح", app_id="com.abdualrhmanalmosheqh.blogapp")
