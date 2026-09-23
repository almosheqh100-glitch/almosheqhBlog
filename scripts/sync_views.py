"""Publish only aggregate lifetime counts; tokens are never included in output."""
import base64
from datetime import datetime, timezone
import json
import os
import time
import urllib.request
import urllib.error

SITE = 236529963
WP = f'https://public-api.wordpress.com/rest/v1.1/sites/{SITE}'
REPO = 'almosheqh100-glitch/almosheqhBlog'
GH = f'https://api.github.com/repos/{REPO}'

def request(url, token=None, method='GET', data=None):
    headers = {'User-Agent': 'almosheqhBlog-Stats-Sync', 'Accept': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    body = None if data is None else json.dumps(data).encode()
    if body is not None:
        headers['Content-Type'] = 'application/json'
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers, data=body, method=method), timeout=30) as r:
        return json.load(r)

def collect(token):
    ids = []
    page = 1
    while True:
        data = request(WP + f'/posts/?number=100&page={page}&fields=ID&status=publish')
        posts = data['posts']
        ids.extend(p['ID'] for p in posts)
        if not posts or len(ids) >= data['found']:
            break
        page += 1
        time.sleep(1)
    counts = {}
    for post_id in ids:
        time.sleep(1)
        stats = request(WP + f'/stats/post/{post_id}', token=token)
        total = stats.get('views')
        if type(total) is not int or total < 0:
            raise ValueError(f'Lifetime views unavailable for post {post_id}; previous snapshot retained')
        counts[str(post_id)] = total
    if not counts:
        raise ValueError('No published posts; previous snapshot retained')
    return {'site_id':SITE,'period':'all_time','updated_at':datetime.now(timezone.utc).isoformat(),'posts':counts}

def publish(snapshot, token):
    try:
        request(GH+'/git/ref/heads/stats', token)
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
        main = request(GH+'/git/ref/heads/main', token)
        request(GH+'/git/refs', token, 'POST', {'ref':'refs/heads/stats','sha':main['object']['sha']})
    previous = None
    try:
        previous = request(GH+'/contents/views.json?ref=stats', token)
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
    payload = {'message':'Update lifetime post view counts','branch':'stats','content':base64.b64encode(json.dumps(snapshot,ensure_ascii=False,sort_keys=True).encode()).decode()}
    if previous:
        payload['sha'] = previous['sha']
    request(GH+'/contents/views.json', token, 'PUT', payload)

if __name__ == '__main__':
    wp_token = os.environ.get('WP_STATS_TOKEN')
    gh_token = os.environ.get('GITHUB_TOKEN')
    if not wp_token or not gh_token:
        raise SystemExit('Stats connection has not been configured.')
    try:
        snapshot = collect(wp_token)
        publish(snapshot, gh_token)
        print(f"Updated lifetime counts for {len(snapshot['posts'])} published posts.")
    except Exception as error:
        # Do not emit response bodies, tokens, or account details to public logs.
        raise SystemExit(f'Stats sync failed ({type(error).__name__}); previous snapshot retained.')
