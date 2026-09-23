import copy
import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))
from blogapp.updates import parse_release, REPO_URL

class UpdatesTest(unittest.TestCase):
    def setUp(self):
        self.release = {'tag_name':'v1.4.0','draft':False,'prerelease':False,'body':'وصف الإصدار الجديد', 'assets':[{'name':'almosheqhBlog-1.4.0.apk','state':'uploaded','size':123,'browser_download_url':REPO_URL+'/releases/download/v1.4.0/almosheqhBlog-1.4.0.apk'}]}

    def test_update_includes_notes_and_direct_apk(self):
        result = parse_release(self.release, '1.3.0')
        self.assertEqual(result['notes'], self.release['body'])
        self.assertTrue(result['url'].endswith('.apk'))
        self.assertIsNone(parse_release(self.release, '1.4.0'))
        self.assertIsNone(parse_release(self.release, '1.5.0'))

    def test_never_offer_unpublished_or_incomplete_release(self):
        for flag in ('draft', 'prerelease'):
            data = copy.deepcopy(self.release); data[flag] = True
            self.assertIsNone(parse_release(data,current='1.3.0'))
        for field, value in [('body',''),('assets',[])]:
            data = copy.deepcopy(self.release); data[field] = value
            with self.assertRaises(ValueError):parse_release(data,current='1.3.0')

    def test_reject_unexpected_download_destination(self):
        self.release['assets'][0]['browser_download_url'] = 'https://example.com/file.apk'
        with self.assertRaises(ValueError):parse_release(self.release,current='1.3.0')

    def test_numeric_versions(self):
        self.assertIsNotNone(parse_release(self.release, '1.3.99'))
        self.assertIsNone(parse_release(self.release, '1.10.0'))
