import pathlib,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from blogapp.library import Library
from blogapp.reading import clean_article,reader_document,download_article,offline_description
from blogapp.views import most_viewed
from unittest.mock import patch
import httpx

POST={'id':1,'title':'عنوان &amp; مقال','url':'https://example.com/post','content':'<p>نص المقال</p>','date':'2026-09-24'}

class LibraryTest(unittest.TestCase):
    def test_favorites_settings_resume_and_offline_survive_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            library=Library(directory)
            self.assertTrue(library.favorite(POST))
            library.set_settings(28,True)
            library.mark_reading(POST,.63)
            document={'content':'<p>نسخة محفوظة</p>','saved_images':1,'total_images':2}
            library.save_offline(POST,document)
            again=Library(directory)
            self.assertEqual(again.articles('favorites'),[POST])
            self.assertEqual(again.articles('offline'),[POST])
            self.assertEqual(again.data['settings'],{'font_size':28,'dark':True})
            self.assertEqual(again.position(POST),.63)
            self.assertEqual(again.last_post(),POST)
            self.assertEqual(again.read_offline(POST),document)
            self.assertFalse(again.favorite(POST))
            self.assertEqual(Library(directory).articles('favorites'),[])
            self.assertEqual(Library(directory).articles('offline'),[POST])

    def test_most_viewed_includes_known_zero_before_unknown(self):
        posts=[dict(POST,id=i) for i in (1,2,3,4)]
        self.assertEqual([p['id'] for p in most_viewed(posts,{1:0,2:15,4:100})],[4,2,1,3])

    def test_offline_partial_images_and_no_external_resources(self):
        post=dict(POST,content='<p>Text</p><img src="/good.png"><img src="/missing.png"><script>bad()</script><iframe src="https://other.test"></iframe>')
        transport=httpx.MockTransport(lambda r:httpx.Response(200,headers={'Content-Type':'image/png'},content=b'png') if r.url.path=='/good.png' else httpx.Response(404))
        client=httpx.Client(transport=transport)
        with patch('blogapp.reading.httpx.Client',return_value=client):document=download_article(post)
        self.assertEqual((document['saved_images'],document['total_images']),(1,2))
        self.assertIn('data:image/png;base64,',document['content'])
        self.assertNotIn('src="http',document['content'])
        self.assertNotIn('script',document['content'])
        self.assertNotIn('iframe',document['content'])
        self.assertIn('1 من 2',offline_description(document))
        rendered=reader_document(post,{'font_size':28,'dark':True},document)
        self.assertIn('font:28px',rendered)
        self.assertIn('#121212',rendered)
        self.assertIn("img-src data:",rendered)

    def test_sanitized_reader_keeps_links_but_removes_active_attributes(self):
        post=dict(POST,content='<a href="/other" onclick="bad()">Link</a><img src="/a.png" onerror="bad()"><form>hidden</form><p>Visible</p>')
        text,images=clean_article(post)
        self.assertIn('https://example.com/other',text)
        self.assertNotIn('onclick',text)
        self.assertNotIn('onerror',text)
        self.assertNotIn('hidden',text)
        self.assertIn('Visible',text)
