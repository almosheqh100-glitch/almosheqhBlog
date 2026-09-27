package com.abdualrhmanalmosheqh.blogapp;

import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.app.NotificationManager;
import org.json.JSONArray;
import org.json.JSONObject;

/** Local notification inbox; never uploads reading history. */
public final class NotificationHistory {
    private static JSONArray load(Context context) {
        try { return new JSONArray(context.getSharedPreferences("notification_history",0).getString("items","[]")); }
        catch (Exception e) { return new JSONArray(); }
    }
    private static void save(Context context, JSONArray items) {
        context.getSharedPreferences("notification_history",0).edit().putString("items",items.toString()).commit();
    }
    public static synchronized String list(Context context) { return load(context).toString(); }
    public static synchronized void record(Context context,String id,String title,String url) {
        try {
            JSONArray old=load(context), items=new JSONArray();
            for(int i=0;i<old.length();i++) if(id.equals(old.getJSONObject(i).optString("id"))) return;
            items.put(new JSONObject().put("id",id).put("title",title).put("url",url).put("received",System.currentTimeMillis()).put("read",false));
            for(int i=0;i<old.length() && items.length()<200;i++) items.put(old.getJSONObject(i));
            save(context,items);
        } catch(Exception ignored) { }
    }
    public static synchronized void markRead(Context context,String id) {
        try {
            JSONArray items=load(context);
            for(int i=0;i<items.length();i++) {
                JSONObject item=items.getJSONObject(i);
                if(id==null || id.equals(item.optString("id"))) {
                    item.put("read",true);
                    context.getSystemService(NotificationManager.class).cancel(item.optString("id"),0);
                }
            }
            save(context,items);
        } catch(Exception ignored) { }
    }
    public static synchronized boolean open(Context context,String id) {
        try {
            JSONArray items=load(context);
            for(int i=0;i<items.length();i++) {
                JSONObject item=items.getJSONObject(i);
                if(!id.equals(item.optString("id"))) continue;
                Uri uri=Uri.parse(item.getString("url"));
                if(!"https".equals(uri.getScheme()) || !"abdualrhmanalmosheqh.com".equals(uri.getHost())) return false;
                Intent browser=new Intent(Intent.ACTION_VIEW,uri);
                browser.addCategory(Intent.CATEGORY_BROWSABLE);
                browser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                context.startActivity(browser);
                markRead(context,id);
                return true;
            }
        } catch(Exception ignored) { }
        return false;
    }
}
