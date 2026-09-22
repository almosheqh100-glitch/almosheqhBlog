# almosheqhBlog

تطبيق أندرويد لتصفح مدونة عبدالرحمن المشيقح، مكتوب باستخدام Python وToga وBriefcase.

## تحميل APK

افتح تبويب **Actions** ثم أحدث تشغيل ناجح لـ **Build Android APK**، ونزّل **almosheqhBlog-APK** من قسم **Artifacts**. فك ضغط الملف وثبّت APK على جهاز أندرويد.

الملف الناتج نسخة تجريبية موقعة بمفتاح Debug، مناسبة للتجربة والتثبيت المباشر. النشر في متجر Google Play يحتاج توقيع إصدار خاصًا بالمالك. لا ترفع مفاتيح التوقيع إلى المستودع.

## الوظائف

- تصفح أحدث 30 مقالًا، والبحث والتصفية بالتصنيف.
- قراءة محتوى المقال وفتح روابطه في المتصفح.
- فحص المقالات الجديدة كل 30 دقيقة أثناء تشغيل التطبيق؛ لا يعمل الفحص بعد إغلاق التطبيق.
- واجهة عربية بعناصر أصلية. توافق TalkBack يحتاج اختبارًا على جهاز فعلي.
- إشعارات النظام تتطلب السماح بها في إعدادات أندرويد؛ لم يتم اختبارها على جهاز فعلي.

## البناء

يتطلب Python 3.13 وJava 17 وAndroid SDK. يستطيع Briefcase تنزيل الأدوات الناقصة.

```sh
python -m pip install briefcase==0.4.5
briefcase create android --no-input
briefcase build android --no-input
briefcase package android -p debug-apk --no-input
```

توجد الحزمة في مجلد `dist/`. يعمل البناء تلقائيًا عند تحديث فرع `main`، ويمكن تشغيله يدويًا من Actions.

## بنية المشروع

- `src/blogapp/app.py`: الواجهة والتحميل والبحث.
- `src/blogapp/wordpress_api.py`: الاتصال بخدمة WordPress.com.
- `src/blogapp/notifications.py`: إشعارات أندرويد عبر Chaquopy.
- `pyproject.toml`: إعدادات التطبيق والصلاحيات.
- `.github/workflows/android.yml`: بناء APK على GitHub Actions.

لم يتضمن المصدر ترخيص توزيع؛ لا يمنح نشر المستودع ترخيصًا مفتوح المصدر تلقائيًا.
