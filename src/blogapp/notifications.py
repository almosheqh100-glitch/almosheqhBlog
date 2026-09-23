"""Native Firebase push delivery, independent of the Python UI loop."""
def _native():
    from java import jclass
    return jclass('com.abdualrhmanalmosheqh.blogapp.BlogPushService'),jclass('org.beeware.android.MainActivity').singletonThis

def schedule():
    try:
        worker,context=_native()
        worker.schedule(context)
    except ImportError:
        pass

def enable(app):
    try:
        from java import jclass
        worker,context=_native()
        worker.schedule(context)
        if jclass('android.os.Build$VERSION').SDK_INT>=33:
            permission='android.permission.POST_NOTIFICATIONS'
            if context.checkSelfPermission(permission)!=0:
                app._impl.request_permissions([permission],lambda permissions,grants:app.set_status('تم السماح بالإشعارات.' if grants and grants[0]==0 else 'لم يُسمح بالإشعارات؛ يمكنك السماح بها من إعدادات الهاتف.'))
                return
        if not worker.enabled(context):
            intent=jclass('android.content.Intent')('android.settings.APP_NOTIFICATION_SETTINGS')
            intent.putExtra('android.provider.extra.APP_PACKAGE',context.getPackageName())
            context.startActivity(intent)
        else:app.set_status('إشعارات المقالات مفعلة.')
    except ImportError:app.set_status('الإشعارات متاحة على هاتف أندرويد.')

def status():
    try:
        worker,context=_native()
        active='الإشعارات مفعلة. ' if worker.enabled(context) else 'يلزم السماح بالإشعارات من الهاتف. '
        active+= 'تم ربط استقبال الإشعارات. ' if worker.subscribed(context) else 'جارٍ ربط استقبال الإشعارات؛ يلزم الاتصال بالإنترنت وخدمات Google Play. '
    except ImportError:active=''
    return active+'تُرسل الإشعارات عند نشر المقالات. يتطلب وصولها الإنترنت، وقد تتأخر بسبب قيود الهاتف. بعد فرض إيقاف التطبيق من الإعدادات يلزم فتحه مجددًا.'
