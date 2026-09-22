import asyncio
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, patch

os.environ['TOGA_BACKEND'] = 'toga_dummy'
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from blogapp import wordpress_api as api
from blogapp.presentation import category_label, ordered_categories
from blogapp.app import BlogApp, main

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
        with patch.object(BlogApp, 'load_categories', new_callable=AsyncMock), patch.object(BlogApp, 'watch_for_new_posts', new_callable=AsyncMock):
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
        with patch('blogapp.app.fetch_posts', return_value={'posts': [post], 'found': 2}) as fetch:
            await app.load_posts(app._request_id, 1)
            self.assertEqual(fetch.call_args.kwargs['category'], category['slug'])
            self.assertEqual(app.posts_box.children[0].text, 'عنوان & مقال')
            self.assertTrue(app.more_button.enabled)
        with patch('blogapp.app.fetch_posts', side_effect=api.WordPressAPIError('offline')):
            await app.load_more(None)
            self.assertEqual(app.page, 1)
            self.assertEqual(app.more_button.text, 'إعادة المحاولة')
        second = dict(post, id=2)
        with patch('blogapp.app.fetch_posts', return_value={'posts': [second], 'found': 2}):
            await app.load_more(None)
            self.assertEqual(app.page, 2)
            self.assertEqual(len(app.posts_cache), 2)
            self.assertFalse(app.more_button.enabled)
        app.open_post_detail(post)
        app.show_home()
        self.assertTrue(app._showing_home)
        self.assertIs(app.body.children[0], app.home_view)
        with patch('webbrowser.open') as browser:
            app.open_link(app.social_links['فيسبوك'])
            browser.assert_called_once_with('https://www.facebook.com/profile.php?id=61565536892612')

if __name__ == '__main__':
    unittest.main()
