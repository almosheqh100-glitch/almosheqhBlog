"""Clean article HTML and make self-contained offline copies with bounded images."""
import base64
import html
from html.parser import HTMLParser
import time
from urllib.parse import urljoin, urlparse
import httpx

ALLOWED = set('p br h1 h2 h3 h4 h5 h6 strong b em i u ul ol li blockquote pre code a img figure figcaption table thead tbody tr td th hr div span'.split())
VOID = {'br','img','hr'}
BLOCKED = {'script','style','iframe','object','embed','form','svg','video','audio'}

class ArticleHTML(HTMLParser):
    def __init__(self, base, images=None):
        super().__init__(convert_charrefs=True)
        self.base, self.images = base, images
        self.output, self.urls, self.blocked = [], [], 0

    def handle_starttag(self, tag, attrs):
        if tag in BLOCKED:
            if tag not in {'embed'}: self.blocked += 1
            return
        if self.blocked or tag not in ALLOWED: return
        attrs = dict(attrs)
        extra = ''
        if tag == 'a':
            url = urljoin(self.base, attrs.get('href') or '')
            if urlparse(url).scheme in {'https','http'}:
                extra = ' href="' + html.escape(url,quote=True) + '"'
        elif tag == 'img':
            url = urljoin(self.base, attrs.get('src') or attrs.get('data-src') or '')
            alt = html.escape(attrs.get('alt') or 'صورة المقال',quote=True)
            if urlparse(url).scheme not in {'https','http'}: return
            self.urls.append(url)
            if self.images is not None:
                url = self.images.get(url)
                if not url:
                    self.output.append('<p>[صورة غير محفوظة: '+alt+']</p>')
                    return
            extra = ' src="'+html.escape(url,quote=True)+'" alt="'+alt+'"'
        self.output.append('<'+tag+extra+'>')

    def handle_endtag(self, tag):
        if tag in BLOCKED:
            self.blocked = max(0,self.blocked-1)
        elif not self.blocked and tag in ALLOWED and tag not in VOID:
            self.output.append('</'+tag+'>')

    def handle_data(self, data):
        if not self.blocked: self.output.append(html.escape(data))

def clean_article(post, images=None):
    parser = ArticleHTML(post['url'], images)
    parser.feed(post.get('content',''))
    return ''.join(parser.output), parser.urls

def download_article(post):
    _, urls = clean_article(post)
    images = {}
    total_bytes = 0
    deadline = time.monotonic() + 40
    with httpx.Client(timeout=8, follow_redirects=True) as client:
        for url in dict.fromkeys(urls):
            if time.monotonic()>deadline or total_bytes>=2*1024*1024: break
            try:
                with client.stream('GET',url) as response:
                    response.raise_for_status()
                    mime=response.headers.get('content-type','').split(';')[0].lower()
                    if mime not in {'image/jpeg','image/png','image/gif','image/webp'}: continue
                    content=bytearray()
                    for chunk in response.iter_bytes():
                        content.extend(chunk)
                        if len(content)>512*1024 or total_bytes+len(content)>2*1024*1024 or time.monotonic()>deadline:
                            raise ValueError('Image limit')
                images[url]='data:'+mime+';base64,'+base64.b64encode(content).decode()
                total_bytes+=len(content)
            except (httpx.HTTPError,ValueError):
                continue
    content,_=clean_article(post,images)
    return {'content':content,'saved_images':sum(url in images for url in urls),'total_images':len(urls)}

def reader_document(post, settings, offline=None):
    content = offline['content'] if offline else clean_article(post)[0]
    bg, fg, link = ('#121212','#f5f5f5','#8ecbff') if settings['dark'] else ('#ffffff','#111111','#0059a8')
    # A saved document cannot fetch images, media, fonts, or scripts from the network.
    policy = "default-src 'none'; img-src data:; style-src 'unsafe-inline'" if offline else "default-src 'none'; img-src https: http: data:; style-src 'unsafe-inline'"
    return f'''<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <meta http-equiv="Content-Security-Policy" content="{policy}">
    <style>html,body{{background:{bg};color:{fg};}}body{{font:{settings['font_size']}px sans-serif;line-height:1.9;padding:12px;overflow-wrap:anywhere}}a{{color:{link}}}img{{max-width:100%;height:auto}}pre,table{{max-width:100%;overflow:auto}}h1{{font-size:1.4em}}</style>
    </head><body><h1>{html.escape(html.unescape(post['title']))}</h1>{content}</body></html>'''

def offline_description(document):
    if document['total_images']==0: return 'النص محفوظ دون إنترنت؛ لا توجد صور في المقال.'
    return f"النص محفوظ دون إنترنت؛ الصور المحفوظة {document['saved_images']} من {document['total_images']}. الفيديو والمحتوى الخارجي يحتاجان الإنترنت."
