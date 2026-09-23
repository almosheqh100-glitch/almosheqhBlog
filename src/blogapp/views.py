"""Public aggregate counts only; never ship WordPress credentials in the APK."""
from datetime import datetime, timezone, timedelta
import httpx

SITE_ID = 236529963
SNAPSHOT_URL = 'https://raw.githubusercontent.com/almosheqh100-glitch/almosheqhBlog/stats/views.json'

def fetch_snapshot():
    with httpx.Client(timeout=10) as client:
        response = client.get(SNAPSHOT_URL)
        response.raise_for_status()
        data = response.json()
    parse_snapshot(data)
    return data

def parse_snapshot(data, now=None):
    if data.get('site_id') != SITE_ID or data.get('period') != 'all_time':
        raise ValueError('Expected lifetime counts for this blog')
    updated = datetime.fromisoformat(data['updated_at'].replace('Z', '+00:00'))
    if updated.tzinfo is None:
        raise ValueError('Timestamp needs timezone')
    now = now or datetime.now(timezone.utc)
    if updated > now + timedelta(minutes=5):
        raise ValueError('Future snapshot')
    counts = data['posts']
    if not isinstance(counts, dict):
        raise ValueError('Invalid counts')
    result = {}
    for key, value in counts.items():
        if not str(key).isdigit() or int(key) <= 0 or type(value) is not int or value < 0:
            raise ValueError('Invalid post count')
        result[int(key)] = value
    return result, updated

def attach_views(posts, counts):
    # Missing values are unknown, never invented zeroes.
    return [dict(post, views=counts.get(post['id'])) for post in posts]

def most_viewed(posts, counts):
    return sorted(attach_views(posts,counts),key=lambda p:(p['views'] is None,-(p['views'] or 0),-p['id']))
