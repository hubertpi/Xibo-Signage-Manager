"""Independent feeds must not replace or purge another layout's media."""
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'xibo_signage_manager'))
from managed_layouts import layout_sources, ensure_layout, sync_sources
from slideshow import sync_media


class ManagedLayoutsTests(unittest.TestCase):
    def options(self, root):
        return dict(counter_layout_name='Main Digital Bulletin - 4K',
                    bulletin_folder=str(root / 'bulletins'), media_tag='xsm',
                    events_ics_url='https://example.test/main.ics',
                    birthdays_ics_url='https://example.test/birthdays.ics',
                    additional_layouts=[dict(name='Design Engineers',
                        bulletin_folder=str(root / 'Design Engineers'),
                        events_ics_url='https://example.test/design.ics',
                        events_heading='Design Engineer Schedule')])

    def test_each_feed_uses_its_own_events_and_shared_birthdays(self):
        with tempfile.TemporaryDirectory() as tmp:
            options = self.options(pathlib.Path(tmp))
            main, extra = layout_sources(options)
            self.assertIs(main['options'], options)
            self.assertEqual(extra['options']['events_ics_url'], 'https://example.test/design.ics')
            self.assertEqual(extra['options']['birthdays_ics_url'], options['birthdays_ics_url'])
            self.assertNotEqual(main['options']['media_tag'], extra['options']['media_tag'])
            self.assertEqual(extra['options']['events_heading'], 'Design Engineer Schedule')
            self.assertNotIn('events_heading', options)
            options['additional_layouts'][0]['birthdays_ics_url'] = ''
            self.assertEqual(layout_sources(options)[1]['options']['birthdays_ics_url'], '')

    def test_legacy_configuration_keeps_primary_ownership(self):
        options = self.options(pathlib.Path('/share/digital_signage'))
        del options['additional_layouts']
        self.assertEqual(len(layout_sources(options)), 1)
        self.assertIsNone(layout_sources(options)[0]['scope'])

    def test_rename_retains_media_namespace(self):
        options = self.options(pathlib.Path('/share/digital_signage'))
        before = layout_sources(options)[1]
        options['additional_layouts'][0]['name'] = 'Engineering Bulletin'
        after = layout_sources(options)[1]
        self.assertEqual(before['scope'], after['scope'])
        self.assertEqual(before['options']['media_tag'], after['options']['media_tag'])

    def test_duplicate_names_folders_and_relative_paths_are_rejected(self):
        for field, value in [('name', 'main digital bulletin - 4k'),
                             ('bulletin_folder', '/share/digital_signage/bulletins'),
                             ('bulletin_folder', 'relative/path')]:
            with self.subTest(field=field, value=value):
                options = self.options(pathlib.Path('/share/digital_signage'))
                options['additional_layouts'][0][field] = value
                with self.assertRaises(ValueError):
                    layout_sources(options)

    def test_new_layout_copies_only_the_published_parent_once(self):
        api = Mock(side_effect=[[], [dict(layoutId=40, layout="Main Digital Bulletin - 4K", publishedStatusId=1),
                                     dict(layoutId=41, layout="Main Digital Bulletin - 4K", parentId=40, publishedStatusId=2)], {}])
        ensure_layout(api, 'Design Engineers', 'Main Digital Bulletin - 4K')
        args, kw = api.call_args
        self.assertEqual(args, ('POST', 'layout/copy/40'))
        self.assertEqual(kw['data']['name'], 'Design Engineers')
        self.assertEqual(kw['data']['copyMediaFiles'], '0')
        api = Mock(return_value=[dict(layoutId=50, layout="Design Engineers", publishedStatusId=1), dict(layoutId=51, layout="Design Engineers", parentId=50)])
        ensure_layout(api, 'Design Engineers', 'Main Digital Bulletin - 4K')
        self.assertEqual(api.call_count, 1)

    def test_ambiguous_layout_name_cannot_target_an_arbitrary_layout(self):
        api = Mock(return_value=[dict(layoutId=50, layout="Design Engineers"), dict(layoutId=60, layout="Design Engineers")])
        with self.assertRaises(ValueError):
            ensure_layout(api, 'Design Engineers', 'Main Digital Bulletin - 4K')
        self.assertEqual(api.call_count, 1)

    def test_both_feeds_sync_with_separate_state_cache_and_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            options = self.options(root)
            (root / 'bulletins').mkdir()
            state = {'slide_assets': {'main.jpg': {'media_id': 71}}}
            with patch('managed_layouts.rename_bulletins', return_value=[]) as scan, \
                 patch('managed_layouts.sync_media', side_effect=[([], {71}), ([], {81})]) as media, \
                 patch('managed_layouts.ensure_layout') as copy, \
                 patch('managed_layouts.sync_live_layout') as layout, \
                 patch('managed_layouts.cleanup_assets') as cleanup:
                result = sync_sources(Mock(), options, state, Mock(), root / 'date', root / 'cache')
                self.assertEqual(result['problems'], [])
                self.assertEqual(scan.call_count, 2)
                self.assertTrue((root / 'Design Engineers').is_dir())
                self.assertIs(media.call_args_list[0].args[2], state)
                self.assertIsNot(media.call_args_list[1].args[2], state)
                self.assertNotEqual(media.call_args_list[0].args[4:6], media.call_args_list[1].args[4:6])
                self.assertNotEqual(media.call_args_list[0].kwargs, media.call_args_list[1].kwargs)
                self.assertIs(cleanup.call_args_list[0].args[1], state)
                self.assertIs(cleanup.call_args_list[1].args[1], media.call_args_list[1].args[2])
                self.assertEqual(layout.call_count, 2)
                copy.assert_called_once()

    def test_failed_primary_does_not_block_extra_or_cleanup_failed_feed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            with patch('managed_layouts.rename_bulletins', return_value=[]), \
                 patch('managed_layouts.sync_media', return_value=([], set())), \
                 patch('managed_layouts.ensure_layout'), \
                 patch('managed_layouts.sync_live_layout', side_effect=[RuntimeError('locked'), True]), \
                 patch('managed_layouts.cleanup_assets') as cleanup:
                state = {}
                result = sync_sources(Mock(), self.options(root), state, Mock(), root / 'date', root / 'cache')
                self.assertEqual(len(result['problems']), 1)
                self.assertIn('Main Digital Bulletin - 4K: locked', result['problems'][0])
                self.assertEqual(cleanup.call_count, 1)
                self.assertIsNot(cleanup.call_args.args[1], state)

    def test_incomplete_copy_defers_only_its_own_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            with patch('managed_layouts.rename_bulletins', side_effect=[None, []]), \
                 patch('managed_layouts.sync_media', return_value=([], set())), \
                 patch('managed_layouts.ensure_layout'), \
                 patch('managed_layouts.sync_live_layout') as layout, \
                 patch('managed_layouts.cleanup_assets'):
                result = sync_sources(Mock(), self.options(root), {}, Mock(), root / 'date', root / 'cache')
                self.assertTrue(result['pending'])
                self.assertEqual(layout.call_count, 1)
                self.assertEqual(layout.call_args.args[1]['counter_layout_name'], 'Design Engineers')

    def test_same_filename_uploads_get_distinct_titles_and_media_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            image = root / 'notice.jpg'
            image.write_bytes(b'image')
            record = dict(path=image, secs=10, original='notice.jpg', digest='unused', desired_name='01 - 10s - notice.jpg')
            api = Mock(side_effect=[[], {'files': [{'mediaId': 71}]}, {},
                                    [], {'files': [{'mediaId': 81}]}, {}])
            main, _ = sync_media(api, [record], {}, Mock(), root, 'xsm')
            extra, _ = sync_media(api, [record], {}, Mock(), root, 'xsm_design', title_prefix='XSM [design] - ')
            self.assertEqual(main[0]['media_id'], 71)
            self.assertEqual(extra[0]['media_id'], 81)
            self.assertNotEqual(main[0]['title'], extra[0]['title'])
            self.assertEqual(api.call_args_list[1].kwargs['data']['tags'], 'xsm')
            self.assertEqual(api.call_args_list[4].kwargs['data']['tags'], 'xsm_design')


if __name__ == '__main__':
    unittest.main()
