import pathlib, sys, unittest
from datetime import datetime, timezone
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from blogapp.views import parse_snapshot, attach_views
from blogapp.presentation import post_label

class ViewsTest(unittest.TestCase):
    def test_accessible_count_in_article_name(self):
        self.assertEqual(post_label({'title':'عنوان &amp; مقال','views':1250}), 'عنوان & مقال — 1,250 مشاهدة')
    def test_missing_does_not_mean_zero(self):
        posts = attach_views([{'id':1,'title':'أ'},{'id':2,'title':'ب'}],{1:0})
        self.assertEqual(post_label(posts[0]),'أ — 0 مشاهدة')
        self.assertEqual(post_label(posts[1]),'ب — عدد المشاهدات غير متاح')
    def test_reject_daily_or_other_site_counts(self):
        for site, period in [(1,'all_time'),(236529963,'day')]:
            with self.assertRaises(ValueError):
                parse_snapshot({'site_id':site,'period':period})
    def test_valid_lifetime_snapshot(self):
        data={'site_id':236529963,'period':'all_time','updated_at':'2026-09-23T00:00:00Z','posts':{'769':2}}
        counts, updated=parse_snapshot(data,now=datetime(2026,9,23,tzinfo=timezone.utc))
        self.assertEqual(counts,{769:2})
        for invalid in [-1, True, '2']:
            data['posts']['769']=invalid
            with self.assertRaises(ValueError):
                parse_snapshot(data,now=datetime(2026,9,23,tzinfo=timezone.utc))
