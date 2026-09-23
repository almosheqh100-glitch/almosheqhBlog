"""Persistent local library. Offline articles never require an account."""
import json
from pathlib import Path

def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    temporary.replace(path)

class Library:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.path = self.directory / 'library.json'
        self.data = {'favorites':[], 'posts':{}, 'offline':{}, 'positions':{}, 'last':None, 'catalog':[],
                     'settings':{'font_size':20, 'dark':False}}
        try:
            loaded = json.loads(self.path.read_text(encoding='utf-8'))
            if isinstance(loaded, dict):
                for key, default in self.data.items():
                    value = loaded.get(key, default)
                    if key == 'last' or isinstance(value, type(default)):
                        self.data[key] = value
        except (OSError, ValueError):
            pass
        self.set_settings(self.data['settings'].get('font_size',20), self.data['settings'].get('dark',False), save=False)

    def save(self):
        atomic_json(self.path, self.data)

    def remember(self, post):
        self.data['posts'][str(post['id'])] = dict(post)

    def favorite(self, post):
        self.remember(post)
        key = str(post['id'])
        if key in self.data['favorites']:
            self.data['favorites'].remove(key)
            result = False
        else:
            self.data['favorites'].append(key)
            result = True
        self.save()
        return result

    def is_favorite(self, post):
        return str(post['id']) in self.data['favorites']

    def articles(self, section):
        ids = self.data['favorites'] if section == 'favorites' else self.data['offline']
        return [self.data['posts'][key] for key in ids if key in self.data['posts']]

    def set_settings(self, size, dark, save=True):
        try: size = int(size)
        except (ValueError, TypeError): size = 20
        self.data['settings'] = {'font_size':max(14,min(36,size)), 'dark':dark is True}
        if save: self.save()

    def mark_reading(self, post, position=None):
        self.remember(post)
        key = str(post['id'])
        self.data['last'] = key
        if position is not None:
            self.data['positions'][key] = max(0.0,min(1.0,float(position)))
        self.save()

    def position(self, post):
        try: return max(0.0,min(1.0,float(self.data['positions'].get(str(post['id']),0))))
        except (TypeError, ValueError): return 0.0

    def last_post(self):
        return self.data['posts'].get(self.data['last'])

    def save_offline(self, post, document):
        key = str(int(post['id']))
        atomic_json(self.directory / 'offline' / (key + '.json'), document)
        self.remember(post)
        self.data['offline'][key] = {k:document[k] for k in ('saved_images','total_images')}
        self.save()

    def read_offline(self, post):
        key = str(int(post['id']))
        if key not in self.data['offline']: return None
        try: return json.loads((self.directory/'offline'/(key+'.json')).read_text(encoding='utf-8'))
        except (OSError, ValueError): return None
