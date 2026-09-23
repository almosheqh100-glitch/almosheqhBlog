"""Copy reviewed native sources into the generated Briefcase project."""
from pathlib import Path
import shutil,json
import xml.etree.ElementTree as ET
root=Path(__file__).resolve().parents[1]
app=root/'build/blogapp/android/gradle/app'
if not (app/'build.gradle').exists():raise SystemExit('Create Android project first')
package='com/abdualrhmanalmosheqh/blogapp'
for name in ('BlogPushService.java',):
    target=app/'src/main/java'/package/name
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(root/'android'/name,target)
gradle=app/'build.gradle'
content=gradle.read_text()
if 'firebase-messaging' not in content:
    content+='\ndependencies {\n implementation platform("com.google.firebase:firebase-bom:34.19.0")\n implementation "com.google.firebase:firebase-messaging"\n}\n'
gradle.write_text(content)
config=json.loads((root/'android/google-services.json').read_text())
client=next(c for c in config['client'] if c['client_info']['android_client_info']['package_name']=='com.abdualrhmanalmosheqh.blogapp')
resources=ET.Element('resources')
values={'google_app_id':client['client_info']['mobilesdk_app_id'],'gcm_defaultSenderId':config['project_info']['project_number'],'project_id':config['project_info']['project_id'],'google_api_key':client['api_key'][0]['current_key']}
for key,value in values.items():ET.SubElement(resources,'string',{'name':key,'translatable':'false'}).text=value
path=app/'src/main/res/values/firebase.xml'
path.parent.mkdir(parents=True,exist_ok=True)
ET.ElementTree(resources).write(path,encoding='utf-8',xml_declaration=True)
android='{http://schemas.android.com/apk/res/android}'
ET.register_namespace('android','http://schemas.android.com/apk/res/android')
manifest=app/'src/main/AndroidManifest.xml'
tree=ET.parse(manifest);application=tree.getroot().find('application')
name='com.abdualrhmanalmosheqh.blogapp.BlogPushService'
if not any(s.get(android+'name')==name for s in application.findall('service')):
    service=ET.SubElement(application,'service',{android+'name':name,android+'exported':'false'})
    intent=ET.SubElement(service,'intent-filter')
    ET.SubElement(intent,'action',{android+'name':'com.google.firebase.MESSAGING_EVENT'})
tree.write(manifest,encoding='utf-8',xml_declaration=True)
print('Native Firebase messaging service installed with validated app resources.')
