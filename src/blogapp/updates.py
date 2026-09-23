"""Read public stable releases and download only this application's APK."""
import re
from urllib.parse import urlparse
import httpx

CURRENT_VERSION = '1.4.0'
REPO_URL = 'https://github.com/almosheqh100-glitch/almosheqhBlog'
LATEST_URL = 'https://api.github.com/repos/almosheqh100-glitch/almosheqhBlog/releases/latest'

def version_tuple(value):
    match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)', value or '')
    if not match:
        raise ValueError('Invalid release version')
    return tuple(map(int, match.groups()))

def parse_release(data, current=CURRENT_VERSION):
    if data.get('draft') or data.get('prerelease'):
        return None
    tag = data.get('tag_name', '')
    version = version_tuple(tag)
    if version <= version_tuple(current):
        return None
    number = '.'.join(map(str, version))
    name = f'almosheqhBlog-{number}.apk'
    expected = f'{REPO_URL}/releases/download/{tag}/{name}'
    asset = next((a for a in data.get('assets', []) if a.get('name') == name and a.get('state') == 'uploaded'), None)
    if not asset or asset.get('browser_download_url') != expected or asset.get('size', 0) <= 0:
        raise ValueError('Release APK is not available')
    notes = (data.get('body') or '').strip()
    if not notes:
        raise ValueError('Release description is required before download')
    return {'version':number, 'notes':notes, 'url':expected, 'filename':name, 'size':asset['size']}

def fetch_update():
    with httpx.Client(timeout=10, headers={'Accept':'application/vnd.github+json', 'User-Agent':'almosheqhBlog'}) as client:
        response = client.get(LATEST_URL)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return parse_release(response.json())

def enqueue_download(release):
    """Use Android's download service; return False for a browser fallback."""
    url = release['url']
    if not url.startswith(REPO_URL + '/releases/download/') or urlparse(url).scheme != 'https':
        raise ValueError('Unexpected download source')
    try:
        from java import jclass
    except ImportError:
        return False
    # Public Downloads needs storage permission before Android 10; let the browser
    # handle those devices without requesting broad storage access.
    if jclass('android.os.Build$VERSION').SDK_INT < 29:
        return False
    context = jclass('org.beeware.android.MainActivity').singletonThis
    manager = context.getSystemService('download')
    request = jclass('android.app.DownloadManager$Request')(jclass('android.net.Uri').parse(url))
    request.setTitle('تحديث مدونة عبدالرحمن المشيقح ' + release['version'])
    request.setDescription('بعد التنزيل افتح الملف لتثبيت التحديث')
    request.setMimeType('application/vnd.android.package-archive')
    request.setNotificationVisibility(1)  # VISIBILITY_VISIBLE_NOTIFY_COMPLETED
    request.setDestinationInExternalPublicDir(jclass('android.os.Environment').DIRECTORY_DOWNLOADS, release['filename'])
    manager.enqueue(request)
    return True
