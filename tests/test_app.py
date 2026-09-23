import asyncio
import json
import os
from pathlib import Path
import sys
import unittest
import tempfile
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

os.environ['TOGA_BACKEND'] = 'toga_dummy'
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from blogapp import wordpress_api as api
from blogapp.presentation import category_label, ordered_categories
from blogapp.app import BlogApp, main
from blogapp.library import Library

class CategoriesTest(unittest.TestCase):
    def test_order_and_live_counts(self):
        categories = [{'name': 'البرامج', 'post_count': 18}, {'name': 'المقالات', 'post_count': 186}]
        labels = [category_label(c) for c in ordered_categories(categories)]
        self.assertEqual(labels, ['المقالات (186)', 'البرامج (18)'])

    def test_pagination_keeps_filter(self):
        with patch.object(api, '_get', return_value={'posts': [], 'found': 185}) as request:
            api.fetch_posts(category='articles', search='hello', page=2)
            self.assertEqual(request.call_args.kwargs['params'], {'number': 20, 'category': 'articles', 'search': 'hello', 'page': 2})

class InterfaceTest(unittest.IsolatedAsyncioTestCase):
    async def test_home_navigation_loading_retry_and_links(self):
        directory=tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        with patch('blogapp.reader_ui.Library',return_value=Library(directory.name)), patch.object(BlogApp, 'load_categories', new_callable=AsyncMock), patch.object(BlogApp, 'watch_for_new_posts', new_callable=AsyncMock), patch.object(BlogApp, 'check_updates', new_callable=AsyncMock):
            app = main()
            await asyncio.sleep(0)
        self.assertTrue(app._showing_home)
        self.assertEqual(len(app.category_box.children), 5)
        self.assertEqual(app.category_box.children[0].text, 'المقالات (185)')
        self.assertEqual(app.category_box.children[-1].text, 'تطبيقات الآيفون (17)')
        self.assertEqual(app.social_links['تويتر (X)'], 'https://x.com/almosheqh19Aa')
        category = app.categories[0]
        post = {'id': 1, 'title': 'عنوان &amp; مقال', 'date': '2026-09-22', 'url': 'https://example.com', 'content': '<p>Article</p>'}
        app.current_category = category
        app.view_counts = {}
        with patch.object(app, 'refresh_views', new_callable=AsyncMock), patch('blogapp.app.fetch_posts', return_value={'posts': [post], 'found': 2}) as fetch:
            await app.load_posts(app._request_id, 1)
            self.assertEqual(fetch.call_args.kwargs['category'], category['slug'])
            self.assertEqual(app.posts_box.children[0].text, 'عنوان & مقال — عدد المشاهدات غير متاح')
            self.assertTrue(app.more_button.enabled)
        with patch('blogapp.app.fetch_posts', side_effect=api.WordPressAPIError('offline')):
            await app.load_more(None)
            self.assertEqual(app.page, 1)
            self.assertEqual(app.more_button.text, 'إعادة المحاولة')
        second = dict(post, id=2)
        app.view_counts = {2: 1250}
        with patch('blogapp.app.fetch_posts', return_value={'posts': [second], 'found': 2}):
            await app.load_more(None)
            self.assertEqual(app.page, 2)
            self.assertEqual(len(app.posts_cache), 2)
            self.assertFalse(app.more_button.enabled)
            self.assertEqual(app.posts_box.children[2].text, 'عنوان & مقال — 1,250 مشاهدة')
        previous_time = datetime.now(timezone.utc)
        app.views_updated = previous_time
        with patch('blogapp.app.fetch_snapshot', side_effect=OSError('offline')):
            await app.refresh_views()
        self.assertEqual(app.view_counts, {2: 1250})
        self.assertEqual(app.views_updated, previous_time)
        with patch('blogapp.app.fetch_snapshot', return_value={'site_id':0}):
            await app.refresh_views()
        self.assertEqual(app.view_counts, {2: 1250})
        app.body.clear();app.body.add(app.posts_view)
        app._showing_home=False
        with patch('blogapp.app.toga.Window', side_effect=RuntimeError('Secondary windows cannot be created on Android')):
            app.posts_box.children[0].on_press()
        self.assertIs(app.body.children[0], app._detail_view)
        self.assertEqual(len(app.windows), 1)
        await app.return_to_posts()
        self.assertIs(app.body.children[0], app.posts_view)
        self.assertEqual(len(app.posts_cache), 2)
        self.assertEqual(app.library.last_post()['id'],1)
        app.open_post_detail(post)
        with patch.object(app._reader_webview,'evaluate_javascript',new_callable=AsyncMock,return_value=.45):
            await app.reader_loaded(app._reader_webview)
            await app.capture_position()
            self.assertEqual(app.library.position(post),.45)
            app._reader_post=second
            app.library.mark_reading(second)
            await app.capture_position(post,app._reader_webview)
            self.assertEqual(app.library.last_post()['id'],second['id'])
            app._reader_post=post
            app.toggle_favorite()
            self.assertTrue(app.library.is_favorite(post))
            app.show_reading_settings()
            app.change_font(4)
            self.assertEqual(app.library.data['settings']['font_size'],24)
        with patch('blogapp.reader_ui.download_article',return_value={'content':'<p>Offline</p>','saved_images':0,'total_images':1}):
            await app.save_article_offline()
            self.assertEqual(app.library.read_offline(post)['total_images'],1)
        app.show_home()
        self.assertTrue(app._showing_home)
        self.assertIs(app.body.children[0], app.home_view)
        with patch('webbrowser.open') as browser:
            app.open_link(app.social_links['فيسبوك'])
            browser.assert_called_once_with('https://www.facebook.com/profile.php?id=61565536892612')
        release = {'version':'1.4.0','notes':'إصلاح القراءة وتحسين الأداء','url':'https://github.com/almosheqh100-glitch/almosheqhBlog/releases/download/v1.4.0/almosheqhBlog-1.4.0.apk'}
        with patch('blogapp.app.fetch_update', return_value=release), patch('blogapp.app.enqueue_download', return_value=True) as download:
            await app.check_updates()
            download.assert_not_called()
            app.update_banner.children[0].on_press()
            self.assertEqual(app._update_view.children[1].value, release['notes'])
            download.assert_not_called()
            app._update_view.children[2].on_press()
            download.assert_called_once_with(release)
            self.assertFalse(app._update_view.children[2].enabled)
            app.close_update_notes()
            self.assertIs(app.body.children[0], app.home_view)
        with patch.object(app, 'check_updates', new_callable=AsyncMock) as check:
            app.on_foreground(app.main_window)
            await asyncio.sleep(0)
            check.assert_awaited_once()

if __name__ == '__main__':
    unittest.main()
