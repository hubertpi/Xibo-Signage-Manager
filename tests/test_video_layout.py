"""Native video layouts: full duration, repeat, isolated media, safe replacements."""
import copy
import os
import pathlib
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'xibo_signage_manager'))
from video_layout import sync_video_source, REGION_NAME


class CMS:
    def __init__(self):
        self.published = None
        self.draft = None
        self.media = {}
        self.calls = []
        self.fail_publish = False

    def __call__(self, method, route, **kwargs):
        data = kwargs.get('data', {})
        self.calls.append((method, route, copy.deepcopy(data)))
        if method == 'GET' and route == 'layout':
            return copy.deepcopy([x for x in (self.published, self.draft) if x])
        if method == 'POST' and route == 'layout':
            self.draft = dict(layoutId=101, parentId=100, layout='Lobby Safety', publishedStatusId=2,
                              width=1920, height=1080, regions=[])
            return {'id': 101, 'data': copy.deepcopy(self.draft)}
        if method == 'PUT' and route == 'layout/checkout/100':
            self.draft = copy.deepcopy(self.published)
            self.draft.update(layoutId=101, parentId=100, publishedStatusId=2)
            return {}
        if method == 'GET' and route == 'library':
            return list(self.media.values())
        if method == 'POST' and route == 'library':
            mid = max(self.media, default=70) + 1
            self.media[mid] = dict(mediaId=mid, name=data['name'], duration=123)
            return {'files': [{'mediaId': mid}]}
        if method == 'POST' and route == 'region/101':
            self.draft['regions'] = [dict(regionId=201, name='', regionOptions=[],
                left=0, top=0, width=1920, height=1080,
                regionPlaylist=dict(playlistId=301, isDynamic=0, widgets=[]))]
            return {}
        if method == 'PUT' and route == 'region/201':
            r = self.draft['regions'][0]
            r.update({k: int(data[k]) for k in ('left','top','width','height')})
            r['name'] = data['name']
            r['regionOptions'] = [{'option': 'loop', 'value': data['loop']}]
            return {}
        if method == 'POST' and route == 'playlist/library/assign/301':
            mid = int(data['media[]'][0])
            widgets = self.draft['regions'][0]['regionPlaylist']['widgets']
            widgets.append(dict(widgetId=mid+400, type='video', mediaIds=[mid],
                                useDuration=0, duration=123, widgetOptions=[]))
            return {}
        if method == 'PUT' and route.startswith('playlist/widget/'):
            widget = next(w for w in self.draft['regions'][0]['regionPlaylist']['widgets']
                          if w['widgetId'] == int(route.split('/')[-1]))
            widget['useDuration'] = int(data['useDuration'])
            widget['widgetOptions'] = [{'option': k, 'value': v} for k,v in data.items() if k != 'useDuration']
            return {}
        if method == 'DELETE' and route.startswith('playlist/widget/'):
            p = self.draft['regions'][0]['regionPlaylist']
            p['widgets'] = [w for w in p['widgets'] if w['widgetId'] != int(route.split('/')[-1])]
            return {}
        if method == 'PUT' and route == 'layout/publish/100':
            if self.fail_publish:
                raise RuntimeError('Layout locked')
            self.published = copy.deepcopy(self.draft)
            self.published.update(layoutId=100, publishedStatusId=1)
            del self.published['parentId']
            self.draft = None
            return {}
        if method == 'DELETE' and route.startswith('library/'):
            del self.media[int(route.split('/')[-1])]
            return {}
        raise AssertionError((method, route, kwargs))


class VideoTests(unittest.TestCase):
    options = dict(counter_layout_name='Lobby Safety', media_tag='xsm_video', video_mute=True)

    def video(self, root, content=b'video', name='Safety.mp4'):
        path = root / name
        path.write_bytes(content)
        os.utime(path, (time.time()-30, time.time()-30))
        return path

    def test_create_publish_native_video_fullscreen_and_no_churn_on_next_sync(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            self.video(root)
            api, state = CMS(), {}
            self.assertTrue(sync_video_source(api, self.options, root, state, Mock()))
            region = api.published['regions'][0]
            self.assertEqual((region['left'],region['top'],region['width'],region['height']), (0,0,1920,1080))
            widget = region['regionPlaylist']['widgets'][0]
            self.assertEqual(widget['type'], 'video')
            self.assertEqual(widget['useDuration'], 0)  # Full natural duration, no ten-second cutoff.
            self.assertEqual(widget['mediaIds'], [71])  # Native dependency for XMDS download.
            opts = {x['option']: x['value'] for x in widget['widgetOptions']}
            self.assertEqual(opts['loop'], '1')
            self.assertEqual(opts['showFullScreen'], '1')
            api.calls.clear()
            sync_video_source(api, self.options, root, state, Mock())
            self.assertFalse(any(m != 'GET' for m, _, _ in api.calls))

    def test_failed_publish_retains_previous_video_and_deletes_only_after_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            self.video(root)
            api, state = CMS(), {}
            sync_video_source(api, self.options, root, state, Mock())
            self.video(root, b'replacement')
            api.fail_publish = True
            with self.assertRaises(RuntimeError):
                sync_video_source(api, self.options, root, state, Mock())
            self.assertEqual(set(api.media), {71,72})
            self.assertEqual(api.published['regions'][0]['regionPlaylist']['widgets'][0]['mediaIds'], [71])
            api.fail_publish = False
            api.calls.clear()
            sync_video_source(api, self.options, root, state, Mock())
            self.assertEqual(set(api.media), {72})
            publish = next(i for i,x in enumerate(api.calls) if x[1] == 'layout/publish/100')
            delete = next(i for i,x in enumerate(api.calls) if x[:2] == ('DELETE','library/71'))
            self.assertLess(publish, delete)

    def test_empty_or_copying_folder_preserves_working_video(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            path = self.video(root)
            api, state = CMS(), {}
            sync_video_source(api, self.options, root, state, Mock())
            published = copy.deepcopy(api.published)
            path.unlink()
            api.calls.clear()
            self.assertFalse(sync_video_source(api, self.options, root, state, Mock()))
            self.assertEqual(api.published, published)
            self.assertEqual(set(api.media), {71})
            path.write_bytes(b'in-progress')
            self.assertFalse(sync_video_source(api, self.options, root, state, Mock()))
            self.assertFalse(any(m != 'GET' for m,_,_ in api.calls))

    def test_multiple_videos_are_rejected_before_any_api_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            self.video(root)
            self.video(root, name='Second.mp4')
            api = Mock()
            with self.assertRaises(ValueError):
                sync_video_source(api, self.options, root, {}, Mock())
            api.assert_not_called()

    def test_existing_unrelated_layout_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            self.video(root)
            api = CMS()
            api.published = dict(layout='Lobby Safety',layoutId=100,width=1920,height=1080,
                                 publishedStatusId=1,regions=[{}, {}])
            with self.assertRaises(ValueError):
                sync_video_source(api, self.options, root, {}, Mock())
            self.assertFalse(any(route.startswith(('region/','playlist/','layout/'))
                                 for method,route,_ in api.calls if method != 'GET'))


if __name__ == '__main__':
    unittest.main()
