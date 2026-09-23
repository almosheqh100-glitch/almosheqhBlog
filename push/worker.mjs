const SITE = 'https://public-api.wordpress.com/rest/v1.1/sites/236529963';
const PROJECT = 'almosheqhblog';
const json = (value, status = 200) => Response.json(value, { status });
let cachedToken;
const b64 = bytes => btoa(String.fromCharCode(...bytes)).replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_');
const encode = value => b64(new TextEncoder().encode(JSON.stringify(value)));

async function accessToken(env) {
  const now = Math.floor(Date.now() / 1000);
  if (cachedToken && cachedToken.expires > now + 60) return cachedToken.value;
  const account = JSON.parse(env.FCM_SERVICE_ACCOUNT);
  if (account.project_id !== PROJECT) throw new Error('Wrong project');
  const pem = account.private_key.replace(/-----[^-]+-----/g, '').replace(/\s/g, '');
  const key = await crypto.subtle.importKey('pkcs8', Uint8Array.from(atob(pem), c => c.charCodeAt(0)), { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' }, false, ['sign']);
  const unsigned = `${encode({ alg: 'RS256', typ: 'JWT' })}.${encode({ iss: account.client_email, scope: 'https://www.googleapis.com/auth/firebase.messaging', aud: 'https://oauth2.googleapis.com/token', iat: now, exp: now + 3600 })}`;
  const signature = await crypto.subtle.sign('RSASSA-PKCS1-v1_5', key, new TextEncoder().encode(unsigned));
  const response = await fetch('https://oauth2.googleapis.com/token', { method: 'POST', body: new URLSearchParams({ grant_type: 'urn:ietf:params:oauth:grant-type:jwt-bearer', assertion: `${unsigned}.${b64(new Uint8Array(signature))}` }) });
  if (!response.ok) throw new Error('Authentication failed');
  const result = await response.json();
  cachedToken = { value: result.access_token, expires: now + result.expires_in };
  return cachedToken.value;
}

export function validPost(post, id, started) {
  const date = Date.parse(post.date);
  let url;
  try { url = new URL(post.URL); } catch { return false; }
  return String(post.ID) === id && post.status === 'publish' && post.type === 'post'
    && !post.password && Number.isFinite(date) && date >= started && date <= Date.now() + 60000
    && ['http:', 'https:'].includes(url.protocol) && url.hostname === 'abdualrhmanalmosheqh.com' && !url.username && !url.password;
}

async function send(env, post, validateOnly = false) {
  const token = await accessToken(env);
  const articleUrl = new URL(post.URL);
  articleUrl.protocol = 'https:';
  const response = await fetch(`https://fcm.googleapis.com/v1/projects/${PROJECT}/messages:send`, {
    method: 'POST', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ validate_only: validateOnly, message: { topic: 'published_articles', data: { id: String(post.ID), title: String(post.title).slice(0, 500), url: articleUrl.href }, android: { priority: 'HIGH', ttl: '86400s' } } }),
  });
  if (!response.ok) throw new Error('FCM rejected message');
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === '/health') return json({ service: 'almosheqhblog-push' });
    if (!env.WEBHOOK_SECRET || url.pathname !== `/publish/${env.WEBHOOK_SECRET}`) return json({ error: 'Not found' }, 404);
    if (request.method !== 'POST') return json({ error: 'POST required' }, 405);
    if (Number(request.headers.get('content-length') || 0) > 16384) return json({ error: 'Too large' }, 413);
    try {
      const raw = await request.text();
      if (raw.length > 16384) return json({ error: 'Too large' }, 413);
      const form = new URLSearchParams(raw);
      const id = form.get('ID');
      if (form.get('hook') !== 'publish_post' || !/^\d{1,10}$/.test(id || '')) return json({ error: 'Invalid event' }, 400);
      const started = Date.parse(env.ACTIVATED_AT);
      if (!Number.isFinite(started)) return json({ error: 'Not configured' }, 503);
      const response = await fetch(`${SITE}/posts/${id}`, { headers: { Accept: 'application/json' } });
      if (!response.ok) return json({ error: 'Post unavailable' }, 503);
      const post = await response.json();
      if (request.headers.get('X-Validate-Only') === '1') {
        if (!validPost(post, id, 0)) return json({ error: 'Invalid post' }, 400);
        await send(env, post, true);
        return json({ validated: true, sent: false });
      }
      if (!validPost(post, id, started)) return json({ ignored: true });
      // A unique database row prevents concurrent webhook deliveries from broadcasting twice.
      const claim = await env.DB.prepare('INSERT OR IGNORE INTO deliveries (id, status, updated_at) VALUES (?, ?, ?)').bind(id, 'pending', Date.now()).run();
      if (!claim.meta.changes) return json({ duplicate: true });
      try {
        await send(env, post);
        await env.DB.prepare('UPDATE deliveries SET status = ?, updated_at = ? WHERE id = ?').bind('sent', Date.now(), id).run();
      } catch {
        // Keep an uncertain delivery claimed: retrying could send the same alert twice.
        await env.DB.prepare('UPDATE deliveries SET status = ? WHERE id = ?').bind('failed', id).run();
        return json({ error: 'Delivery failed' }, 502);
      }
      return json({ sent: true });
    } catch { return json({ error: 'Service unavailable' }, 503); }
  },
};

export { send };
