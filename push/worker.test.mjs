import test from 'node:test';
import assert from 'node:assert/strict';
import worker, { validPost } from './worker.mjs';

test('only newly published public posts from this blog qualify', () => {
  const p = { ID: 769, type: 'post', status: 'publish', date: new Date().toISOString(), URL: 'https://abdualrhmanalmosheqh.com/article/' };
  const start = Date.now() - 10000;
  assert.equal(validPost(p, '769', start), true);
  assert.equal(validPost({...p, URL:'http://abdualrhmanalmosheqh.com/article/'}, '769', start), true);
  for (const change of [{ status: 'draft' }, { type: 'page' }, { password: 'secret' }, { URL: 'https://example.com/' }, { date: '2020-01-01' }, { ID: 770 }]) assert.equal(validPost({ ...p, ...change }, '769', start), false);
});
test('duplicate deliveries are acknowledged without contacting Firebase', async () => {
  const originalFetch = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => {
    calls++;
    return Response.json({ID:769, type:'post', status:'publish', date:new Date().toISOString(), URL:'https://abdualrhmanalmosheqh.com/article/'});
  };
  try {
    const env = {WEBHOOK_SECRET:'test', ACTIVATED_AT:new Date(Date.now()-10000).toISOString(), DB:{prepare:()=>({bind:()=>({run:async()=>({meta:{changes:0}})})})}};
    const response = await worker.fetch(new Request('https://worker/publish/test',{method:'POST',body:'hook=publish_post&ID=769'}), env);
    assert.deepEqual(await response.json(), {duplicate:true});
    assert.equal(calls,1);
  } finally { globalThis.fetch = originalFetch; }
});
test('unauthorized requests and malformed events cannot send messages', async () => {
  const env = { WEBHOOK_SECRET: 'test-secret' };
  assert.equal((await worker.fetch(new Request('https://worker/publish/wrong', { method: 'POST' }), env)).status, 404);
  assert.equal((await worker.fetch(new Request('https://worker/publish/test-secret'), env)).status, 405);
  assert.equal((await worker.fetch(new Request('https://worker/publish/test-secret', { method: 'POST', body: 'hook=delete_post&ID=769' }), env)).status, 400);
});
