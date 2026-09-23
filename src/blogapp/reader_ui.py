"""Library, reader settings, reading progress and explicit sharing screens."""
import asyncio
import html
from functools import partial
import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW
from .library import Library
from .reading import reader_document, download_article, offline_description
from .presentation import post_label
from .wordpress_api import fetch_all_posts
from .views import most_viewed
from . import mobile
from .updates import CURRENT_VERSION

class ReaderFeatures:
    def init_reading(self):
        self.library = Library(self.paths.data)
        self._reader_post = None
        self._reader_generation = 0
        self._reader_ready = False
        self._return_focus = None
        self._library_section = None
        self._saving_offline = set()
        for command in self.commands:
            if getattr(command,'id',None) == toga.Command.ABOUT:
                command.text = 'حول التطبيق'

    def library_home_buttons(self):
        return [
            toga.Button('المفضلة',on_press=partial(self.show_library,'favorites'),style=Pack(height=50,margin=8)),
            toga.Button('المقالات المنزّلة دون إنترنت',on_press=partial(self.show_library,'offline'),style=Pack(height=50,margin=8)),
            toga.Button('متابعة آخر قراءة',on_press=self.continue_reading,style=Pack(height=50,margin=8)),
            toga.Button('الأكثر مشاهدة',on_press=self.show_popular,style=Pack(height=50,margin=8)),
            toga.Button('إعدادات القراءة',on_press=self.show_reading_settings,style=Pack(height=50,margin=8)),
            toga.Button('إعدادات إشعارات المقالات',on_press=self.show_notification_settings,style=Pack(height=50,margin=8)),
        ]

    def about(self, widget=None, **kwargs):
        self.show_auxiliary('حول التطبيق',[
            toga.Label('مدونة عبدالرحمن المشيقح',style=Pack(margin=8)),
            toga.Label('الإصدار '+CURRENT_VERSION,style=Pack(margin=8)),
            toga.Label('تصفح المقالات واحفظها واقرأها بإعداداتك المفضلة.',style=Pack(margin=8)),
        ])

    def show_auxiliary(self, title, children):
        if self._reader_post and self._reader_ready:
            self.loop.create_task(self.capture_position(self._reader_post,self._reader_webview))
        previous=self.body.children[0]
        previous_home=self._showing_home
        self._showing_home=False
        def close(widget=None,**kwargs):
            self.body.clear();self.body.add(previous)
            self._showing_home=previous_home
            if previous is self._detail_view:
                self.render_reader()
        box=toga.Box(children=[toga.Label(title,style=Pack(font_size=20,margin=8))]+children,style=Pack(direction=COLUMN))
        self.body.clear()
        self.body.add(toga.Box(children=[toga.Button('رجوع',on_press=close,style=Pack(height=48,margin=8)),toga.ScrollContainer(content=box,horizontal=False,style=Pack(flex=1))],style=Pack(direction=COLUMN,flex=1)))
        self.set_status(title)

    def show_library(self, section, widget=None, **kwargs):
        self._request_id+=1
        self._reader_generation+=1
        self._reader_post=None
        self._detail_view=None
        self._loading=False
        self._showing_home=False
        self._library_section=section
        title='المفضلة' if section=='favorites' else 'المقالات المنزّلة دون إنترنت'
        posts=self.library.articles(section)
        box=toga.Box(style=Pack(direction=COLUMN,margin=8))
        for post in posts:
            box.add(toga.Button(html.unescape(post['title']),on_press=partial(self.open_post_detail,post),style=Pack(height=72,margin_bottom=8)))
        if not posts: box.add(toga.Label('لا توجد مقالات محفوظة في هذا القسم بعد.',style=Pack(margin=8)))
        self.body.clear()
        self.body.add(toga.Box(children=[toga.Button('العودة إلى الرئيسية',on_press=self.show_home,style=Pack(height=48,margin=8)),toga.Label(title,style=Pack(margin=8,font_size=20)),toga.ScrollContainer(content=box,horizontal=False,style=Pack(flex=1))],style=Pack(direction=COLUMN,flex=1)))
        self.set_status(title+f' — {len(posts)} مقالًا.')

    async def show_popular(self, widget=None, **kwargs):
        self._request_id+=1
        request_id=self._request_id
        self._showing_home=False
        self._library_section=None
        self._detail_view=None
        self._reader_generation+=1
        self._reader_post=None
        self.posts_box.clear()
        self.posts_cache=[]
        self.body.clear();self.body.add(self.posts_view)
        self.posts_heading.text='الأكثر مشاهدة على المدونة'
        self.more_button.enabled=False
        self.set_status('جارٍ ترتيب مقالات المدونة حسب إجمالي المشاهدات...')
        try:
            results = await asyncio.gather(asyncio.to_thread(fetch_all_posts),self.refresh_views())
            if request_id!=self._request_id:return
            posts=results[0]
            self.library.data['catalog']=posts
            self.library.save()
        except Exception:
            if request_id!=self._request_id:return
            posts=self.library.data.get('catalog',[])
            if not posts:
                self.set_status('تعذر تحميل الأكثر مشاهدة. تحقق من الإنترنت وحاول من الرئيسية.');return
        self.posts_cache=most_viewed(posts,self.view_counts)
        for post in self.posts_cache:
            self.posts_box.add(toga.Button(post_label(post),on_press=partial(self.open_post_detail,post),style=Pack(height=72,margin_bottom=4)))
            self.posts_box.add(toga.Label(post['date'].split('T')[0],style=Pack(margin_bottom=12)))
        self.more_button.text='تم عرض جميع المقالات'
        self.set_status('اكتمل ترتيب المقالات. الأعداد غير المتاحة تظهر في النهاية.')
        if self.views_updated:
            self.set_status(self.status_input.value+' آخر تحديث للمشاهدات: '+self.views_updated.astimezone().strftime('%Y-%m-%d %H:%M'))

    def continue_reading(self, widget=None, **kwargs):
        post=self.library.last_post()
        if post:self.open_post_detail(post,widget)
        else:self.set_status('لم تبدأ قراءة مقال بعد.')

    def open_reader(self, post, widget=None):
        self._reader_generation+=1
        self._before_reader=self.body.children[0]
        self._before_reader_home=self._showing_home
        self._showing_home=False
        self._return_focus=widget
        self._reader_post=post
        self._offline_document=self.library.read_offline(post)
        self.library.mark_reading(post)
        self._reader_webview=toga.WebView(on_webview_load=self.reader_loaded,style=Pack(flex=1))
        self._detail_view=toga.Box(children=[
            toga.Button('الرجوع إلى قائمة المقالات',on_press=self.return_to_posts,style=Pack(height=48,margin=8)),
            self._reader_webview,
            toga.Button('خيارات المقال: المفضلة والتنزيل وإعدادات القراءة',on_press=self.show_reader_options,style=Pack(height=54,margin=4)),
            toga.Button('مشاركة المقال',on_press=self.show_share,style=Pack(height=48,margin=4)),
        ],style=Pack(direction=COLUMN,flex=1))
        self.body.clear();self.body.add(self._detail_view)
        self.render_reader()
        self.loop.create_task(self.track_reading(self._reader_generation,post,self._reader_webview))

    def render_reader(self):
        self._reader_ready=False
        self._reader_webview.set_content(self._reader_post['url'],reader_document(self._reader_post,self.library.data['settings'],self._offline_document))
        self.set_status(offline_description(self._offline_document) if self._offline_document else 'جارٍ فتح المقال...')

    async def reader_loaded(self, webview, **kwargs):
        if webview is not self._reader_webview:return
        position=self.library.position(self._reader_post)
        await webview.evaluate_javascript(f'window.scrollTo(0,Math.max(0,document.documentElement.scrollHeight-window.innerHeight)*{position});')
        self._reader_ready=True
        self.set_status('اكتمل تحميل المقال. '+(offline_description(self._offline_document) if self._offline_document else ''))

    async def track_reading(self, generation, post, webview):
        while generation==self._reader_generation:
            await asyncio.sleep(2)
            if generation!=self._reader_generation:return
            if self._reader_ready and self.body.children[0] is self._detail_view:
                await self.capture_position(post,webview)

    async def capture_position(self, post=None, webview=None):
        post=post or self._reader_post
        webview=webview or getattr(self,'_reader_webview',None)
        if not post or not webview or not self._reader_ready:return
        try:
            position=await asyncio.wait_for(webview.evaluate_javascript('Math.min(1,Math.max(0,window.scrollY/Math.max(1,document.documentElement.scrollHeight-window.innerHeight)))'),2)
            if self._reader_post and self._reader_post['id']==post['id'] and type(position) in (float,int) and abs(position-self.library.position(post))>.002:
                self.library.mark_reading(post,position)
        except (Exception,asyncio.CancelledError):pass

    async def close_reader(self, widget=None, **kwargs):
        generation=self._reader_generation
        await self.capture_position()
        if generation!=self._reader_generation:return
        self._reader_generation+=1
        self._reader_post=None
        self.body.clear();self.body.add(self._before_reader)
        self._showing_home=self._before_reader_home
        self._detail_view=None
        self.set_status('تم الرجوع إلى القائمة.')
        await asyncio.sleep(.2)
        mobile.focus(self._return_focus)

    def show_reader_options(self, widget=None, **kwargs):
        self.show_auxiliary('خيارات المقال',[
            toga.Button('إزالة من المفضلة' if self.library.is_favorite(self._reader_post) else 'إضافة إلى المفضلة',on_press=self.toggle_favorite,style=Pack(height=50,margin=8)),
            toga.Button('تنزيل المقال للقراءة دون إنترنت',on_press=self.save_article_offline,style=Pack(height=50,margin=8)),
            toga.Button('إعدادات القراءة',on_press=self.show_reading_settings,style=Pack(height=50,margin=8)),
            toga.Button('فتح المقال في المتصفح',on_press=partial(self.open_link,self._reader_post['url']),style=Pack(height=50,margin=8)),
        ])

    def toggle_favorite(self, widget=None, **kwargs):
        try:
            added=self.library.favorite(self._reader_post)
            if widget:widget.text='إزالة من المفضلة' if added else 'إضافة إلى المفضلة'
            self.set_status('تمت إضافة المقال إلى المفضلة.' if added else 'تمت إزالة المقال من المفضلة.')
        except OSError:self.set_status('تعذر حفظ التغيير؛ تحقق من مساحة الهاتف.')

    async def save_article_offline(self, widget=None, **kwargs):
        post=dict(self._reader_post)
        if post['id'] in self._saving_offline:return
        self._saving_offline.add(post['id'])
        if widget:widget.enabled=False
        self.set_status('جارٍ حفظ النص والصور المتاحة...')
        try:
            document=await asyncio.to_thread(download_article,post)
            self.library.save_offline(post,document)
            if self._reader_post and self._reader_post['id']==post['id']:self._offline_document=document
            self.set_status(offline_description(document))
        except Exception:self.set_status('تعذر حفظ المقال. تحقق من مساحة الهاتف وحاول مرة أخرى.')
        finally:
            self._saving_offline.discard(post['id'])
            if widget:widget.enabled=True

    def show_reading_settings(self, widget=None, **kwargs):
        settings=self.library.data['settings']
        self._font_label=toga.Label(f"حجم الخط: {settings['font_size']}",style=Pack(margin=8))
        self.show_auxiliary('إعدادات القراءة',[
            self._font_label,
            toga.Button('تكبير الخط',on_press=partial(self.change_font,2),style=Pack(height=50,margin=8)),
            toga.Button('تصغير الخط',on_press=partial(self.change_font,-2),style=Pack(height=50,margin=8)),
            toga.Switch('الوضع الليلي للقراءة',value=settings['dark'],on_change=self.change_dark,style=Pack(margin=8)),
            toga.Label('تُحفظ اختياراتك وتُطبق عند العودة إلى المقال.',style=Pack(margin=8)),
        ])

    def change_font(self, delta, widget=None, **kwargs):
        s=self.library.data['settings'];self.library.set_settings(s['font_size']+delta,s['dark'])
        self._font_label.text=f"حجم الخط: {self.library.data['settings']['font_size']}"
        self.set_status(self._font_label.text+' — تم الحفظ.')

    def change_dark(self, widget, **kwargs):
        self.library.set_settings(self.library.data['settings']['font_size'],widget.value)
        self.set_status('تم حفظ الوضع الليلي.' if widget.value else 'تم حفظ الوضع النهاري.')

    def show_share(self, widget=None, **kwargs):
        self.show_auxiliary('مشاركة المقال',[
            toga.Button('مشاركة عبر '+name,on_press=partial(self.share_article,name),style=Pack(height=50,margin=8))
            for name in ('واتساب','فيسبوك','X','إنستجرام')
        ])

    def share_article(self, destination, widget=None, **kwargs):
        self.set_status(mobile.share(self._reader_post,destination,self.open_link))

    def show_notification_settings(self, widget=None, **kwargs):
        from . import notifications
        self.show_auxiliary('إشعارات المقالات',[
            toga.Label(notifications.status(),style=Pack(margin=8)),
            toga.Button('السماح بإشعارات المقالات',on_press=self.enable_notifications,style=Pack(height=50,margin=8)),
        ])

    def enable_notifications(self, widget=None, **kwargs):
        from . import notifications
        notifications.enable(self)
        self.set_status('أكمل السماح بالإشعارات في نافذة أندرويد إن ظهرت.')
