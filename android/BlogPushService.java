package com.abdualrhmanalmosheqh.blogapp;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.text.Html;
import androidx.annotation.NonNull;
import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;
import com.google.firebase.FirebaseApp;
import com.google.firebase.messaging.FirebaseMessaging;
import com.google.firebase.messaging.FirebaseMessagingService;
import com.google.firebase.messaging.RemoteMessage;
import java.util.Map;

public class BlogPushService extends FirebaseMessagingService {
    private static final String CHANNEL="blog_new_posts";
    public static void schedule(Context context) {
        channel(context);
        FirebaseApp.initializeApp(context);
        FirebaseMessaging.getInstance().subscribeToTopic("published_articles").addOnCompleteListener(task -> {
            context.getSharedPreferences("push_status",MODE_PRIVATE).edit().putBoolean("subscribed",task.isSuccessful()).apply();
        });
    }
    public static boolean subscribed(Context context) {
        return context.getSharedPreferences("push_status",MODE_PRIVATE).getBoolean("subscribed",false);
    }
    private static void channel(Context context) {
        if (Build.VERSION.SDK_INT>=26) context.getSystemService(NotificationManager.class).createNotificationChannel(
            new NotificationChannel(CHANNEL,"مقالات جديدة",NotificationManager.IMPORTANCE_DEFAULT));
    }
    public static boolean enabled(Context context) {
        if (!NotificationManagerCompat.from(context).areNotificationsEnabled()) return false;
        if (Build.VERSION.SDK_INT>=26) {
            NotificationChannel channel=context.getSystemService(NotificationManager.class).getNotificationChannel(CHANNEL);
            return channel==null || channel.getImportance()!=NotificationManager.IMPORTANCE_NONE;
        }
        return true;
    }
    @Override public void onNewToken(@NonNull String token) {
        // SDK manages the token. Never expose it in UI, logs, or the public repository.
        schedule(this);
    }
    @Override public void onMessageReceived(@NonNull RemoteMessage message) {
        Map<String,String> data=message.getData();
        String id=data.get("id"),title=data.get("title"),url=data.get("url");
        if (id==null || !id.matches("[0-9]{1,10}") || title==null || url==null || !enabled(this)) return;
        Uri uri=Uri.parse(url);
        if (!"https".equals(uri.getScheme()) || !"abdualrhmanalmosheqh.com".equals(uri.getHost())) return;
        synchronized (BlogPushService.class) {
            android.content.SharedPreferences seen=getSharedPreferences("push_delivered",MODE_PRIVATE);
            if (seen.getBoolean(id,false)) return;
            Intent intent=new Intent(Intent.ACTION_VIEW,uri);
            PendingIntent action=PendingIntent.getActivity(this,id.hashCode(),intent,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
            channel(this);
            String plainTitle=Html.fromHtml(title,Html.FROM_HTML_MODE_LEGACY).toString();
            NotificationCompat.Builder builder=new NotificationCompat.Builder(this,CHANNEL)
                .setSmallIcon(android.R.drawable.ic_dialog_info).setContentTitle("مقال جديد في المدونة")
                .setContentText(plainTitle).setStyle(new NotificationCompat.BigTextStyle().bigText(plainTitle))
                .setContentIntent(action).setAutoCancel(true).setOnlyAlertOnce(true);
            try {
                NotificationManagerCompat.from(this).notify(id,0,builder.build());
                seen.edit().putBoolean(id,true).commit();
            } catch (SecurityException ignored) { }
        }
    }
}
