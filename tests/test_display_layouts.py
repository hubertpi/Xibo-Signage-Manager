import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'xibo_signage_manager'))
from display_layouts import DisplayLayoutMonitor


class DisplayLayoutTests(unittest.TestCase):
    def setUp(self):
        self.api, self.client = Mock(), Mock()
        self.device = {'identifiers': ['xibo_signage_manager'],
                       'name': 'Xibo Signage Manager',
                       'manufacturer': 'Community', 'model': 'Bulletin Synchronizer'}
        self.monitor = DisplayLayoutMonitor(self.api, self.client, 'xibo_signage_manager',
                                            device=self.device)

    def display(self, identity=1, name='Bulletin Pi 01', **extra):
        return dict(displayId=identity, display=name, currentLayout='Main Bulletin',
                    currentLayoutId=24, lastAccessed=1792600000, loggedIn=1, licensed=1,
                    **extra)

    def sent(self, suffix):
        return [(call.args[0],call.args[1]) for call in self.client.publish.call_args_list
                if call.args[0].endswith(suffix)]

    def test_new_displays_discover_without_configuration(self):
        self.api.return_value = [self.display()]
        self.monitor.poll()
        self.api.return_value = [self.display(), self.display(2, 'Future Pi')]
        self.monitor.poll()
        configs = [json.loads(payload) for _,payload in self.sent('/config')]
        self.assertEqual(len(configs), 2)
        self.assertEqual(configs[1]['name'], 'Future Pi')
        self.assertEqual(configs[0]['name'], 'Bulletin Pi 01')
        self.assertTrue(all(config['device'] == self.device for config in configs))
        self.assertNotIn('via_device', configs[0]['device'])
        self.assertNotEqual(configs[0]['unique_id'], configs[1]['unique_id'])
        self.assertEqual(self.monitor.known, {1,2})
        state = json.loads(self.sent('/state')[-1][1])
        self.assertEqual(state['layout'], 'Main Bulletin')
        self.assertEqual(state['layout_id'], 24)
        self.assertEqual(state['display_id'], 2)

    def test_rename_refreshes_discovery_but_keeps_entity_identity(self):
        self.api.return_value = [self.display()]
        self.monitor.poll()
        self.monitor.poll()
        self.assertEqual(len(self.sent('/config')), 1)
        self.api.return_value = [self.display(name='Renamed Pi')]
        self.monitor.poll()
        first,last = [json.loads(payload) for _,payload in self.sent('/config')]
        self.assertEqual(first['unique_id'], last['unique_id'])
        self.assertEqual(last['name'], 'Renamed Pi')
        self.assertEqual(last['device'], self.device)
        self.assertEqual(first['state_topic'], last['state_topic'])
        self.assertEqual(last['unique_id'], 'xibo_signage_manager_display_1_current_layout')
        self.monitor.reconnect()
        self.monitor.poll()
        self.assertEqual(len(self.sent('/config')), 3)

    def test_never_substitutes_assigned_default_for_missing_report(self):
        entry=self.display()
        entry.update(currentLayout=None,currentLayoutId=None,defaultLayout='Main Bulletin')
        self.api.return_value = [entry]
        self.monitor.poll()
        self.assertIsNone(json.loads(self.sent('/state')[-1][1])['layout'])
        self.assertEqual(self.sent('/availability')[-1][1], 'offline')

    def test_layout_id_fallback_is_reported_id(self):
        entry=self.display()
        entry['currentLayout']=None
        self.api.return_value=[entry]
        self.monitor.poll()
        self.assertEqual(json.loads(self.sent('/state')[-1][1])['layout'],'Layout 24')

    def test_offline_or_deauthorised_display_is_unavailable(self):
        for key in ('loggedIn','licensed'):
            entry=self.display()
            entry[key]=0
            self.api.return_value=[entry]
            self.monitor.poll()
            self.assertEqual(self.sent('/availability')[-1][1], 'offline')

    def test_deleted_discovery_is_pruned_after_restart(self):
        self.monitor.known = {8}
        self.api.return_value=[]
        self.monitor.poll()
        self.assertEqual(self.sent('/config')[-1][1], '')
        self.assertEqual(self.sent('/state')[-1][1], '')
        self.assertEqual(self.monitor.known,set())

    def test_failed_request_never_deletes_discovery(self):
        self.monitor.known={8}
        self.api.side_effect=PermissionError('Forbidden')
        with self.assertRaises(PermissionError):
            self.monitor.poll()
        self.monitor.unavailable()
        self.assertEqual(self.sent('/config'),[])
        self.assertEqual(self.monitor.known,{8})
        self.assertEqual(self.sent('/availability')[-1][1], 'offline')

    def test_pagination_and_nonadvancing_page(self):
        first=[self.display(i,f'Pi {i}') for i in range(1,101)]
        self.api.side_effect=[first,[self.display(101,'Last Pi')]]
        self.monitor.poll()
        self.assertEqual(len(self.monitor.known),101)
        self.assertEqual(self.api.call_args.kwargs['params']['start'],100)
        self.api.side_effect=[first,first]
        self.client.reset_mock()
        with self.assertRaisesRegex(ValueError,'duplicate'):
            self.monitor.poll()
        self.assertEqual(self.sent('/config'),[])
        self.assertEqual(len(self.monitor.known),101)


if __name__=='__main__':
    unittest.main()
