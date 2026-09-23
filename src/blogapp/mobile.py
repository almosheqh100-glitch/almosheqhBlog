"""Small Android integrations, isolated from the reader's portable behavior."""
import html
from urllib.parse import urlencode

def announce(widget, text):
    try: widget._impl.native.announceForAccessibility(text)
    except AttributeError: pass

def focus(widget):
    if widget is None: return
    try:
        native=widget._impl.native
        native.requestFocus()
        native.performAccessibilityAction(64,None)
    except AttributeError:
        widget.focus()

def share(post, destination, open_link):
    text=html.unescape(post['title'])+'\n'+post['url']
    urls={
        'واتساب':'https://wa.me/?'+urlencode({'text':text}),
        'فيسبوك':'https://www.facebook.com/sharer/sharer.php?'+urlencode({'u':post['url']}),
        'X':'https://twitter.com/intent/tweet?'+urlencode({'text':html.unescape(post['title']),'url':post['url']}),
    }
    if destination in urls:
        open_link(urls[destination]);return 'اختر المستلم أو أكمل النشر في التطبيق الذي فتحته.'
    try:
        from java import jclass
        context=jclass('org.beeware.android.MainActivity').singletonThis
        clipboard=context.getSystemService('clipboard')
        clipboard.setPrimaryClip(jclass('android.content.ClipData').newPlainText('رابط المقال',text))
        intent=jclass('android.content.Intent')('android.intent.action.SEND')
        intent.setType('text/plain')
        intent.putExtra('android.intent.extra.TEXT',text)
        if destination=='إنستجرام': intent.setPackage('com.instagram.android')
        try:
            context.startActivity(intent)
            return 'تم نسخ رابط المقال وفتح المشاركة. إذا لم يظهر النص، الصقه في رسالة إنستجرام.'
        except Exception:
            open_link('https://www.instagram.com/')
            return 'تم نسخ رابط المقال؛ الصقه في رسالة إنستجرام. مشاركة النص المباشرة غير متاحة على هذا الجهاز.'
    except ImportError:
        return 'مشاركة إنستجرام متاحة على هاتف أندرويد.'
