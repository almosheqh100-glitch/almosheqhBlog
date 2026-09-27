package com.abdualrhmanalmosheqh.blogapp;

import android.app.Activity;
import android.os.Bundle;
import android.widget.Toast;

/** Direct notification activity: opens the browser without starting the Python UI. */
public class NotificationOpenActivity extends Activity {
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        String id=getIntent().getStringExtra("article_id");
        if(id==null || !NotificationHistory.open(this,id))
            Toast.makeText(this,"تعذر فتح المتصفح. افتح المقال من سجل الإشعارات وحاول مرة أخرى.",Toast.LENGTH_LONG).show();
        finish();
    }
}
