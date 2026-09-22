"""
إرسال إشعار نظام أندرويد عند اكتشاف مقال جديد في المدونة.

يعتمد على rubicon-java للوصول لواجهات أندرويد الأصلية مباشرة من بايثون —
نفس الأسلوب المستخدم سابقًا في برنامج تسجيل الشاشة (Java glue).

ملاحظة مهمة: هذا الفحص يعمل فقط أثناء تشغيل التطبيق (foreground/background
task ضمن حلقة asyncio الخاصة بـ Toga). لإشعارات تعمل والتطبيق مغلق تمامًا
يلزم WorkManager/AlarmManager أصيل عبر كود Java إضافي — هذا تطوير منفصل
يمكن إضافته في مرحلة لاحقة إن احتجته.
"""
from __future__ import annotations

CHANNEL_ID = "blog_new_posts"
CHANNEL_NAME = "مقالات جديدة"

_channel_created = False


def _get_context():
    """يرجع Context الخاص بتطبيق أندرويد الحالي."""
    from java import jclass

    PythonActivity = jclass("org.beeware.android.MainActivity")
    return PythonActivity.singletonThis


def _ensure_channel(context) -> None:
    """ينشئ قناة الإشعارات مرة واحدة (مطلوب من Android 8+)."""
    global _channel_created
    if _channel_created:
        return

    from java import jclass

    NotificationChannel = jclass("android.app.NotificationChannel")

    IMPORTANCE_DEFAULT = 3  # NotificationManager.IMPORTANCE_DEFAULT

    channel = NotificationChannel(CHANNEL_ID, CHANNEL_NAME, IMPORTANCE_DEFAULT)
    manager = context.getSystemService("notification")
    manager.createNotificationChannel(channel)
    _channel_created = True


def notify_new_post(title: str, post_id: int) -> None:
    """يعرض إشعار نظام بعنوان المقال الجديد."""
    try:
        from java import jclass

        context = _get_context()
        _ensure_channel(context)

        NotificationCompatBuilder = jclass("android.app.Notification$Builder")
        builder = NotificationCompatBuilder(context, CHANNEL_ID)
        builder.setContentTitle("مقال جديد في المدونة")
        builder.setContentText(title)
        builder.setAutoCancel(True)
        builder.setSmallIcon(context.getApplicationInfo().icon)
        notification = builder.build()

        manager = context.getSystemService("notification")
        manager.notify(int(post_id), notification)
    except Exception:
        # لا نُسقط التطبيق إذا تعذّر الإشعار (مثلاً أثناء التطوير على سطح
        # المكتب حيث لا توجد بيئة أندرويد أصيلة)
        pass
