"""Discover one MQTT current-layout sensor for every display visible in Xibo."""
import json


class DisplayLayoutMonitor:
    def __init__(self, api, client, prefix, known=()):
        self.api, self.client, self.prefix = api, client, prefix
        self.known = {int(value) for value in known}
        self.configs = {}

    def reconnect(self):
        self.configs.clear()

    def topics(self, display_id):
        base = f'{self.prefix}/displays/{display_id}'
        config = f'homeassistant/sensor/{self.prefix}/display_{display_id}_current_layout/config'
        return config, base + '/state', base + '/availability'

    def publish(self, topic, value):
        self.client.publish(topic, value, qos=1, retain=True)

    def unavailable(self):
        for display_id in self.known:
            self.publish(self.topics(display_id)[2], 'offline')

    def poll(self):
        displays, seen, offset = [], set(), 0
        while True:
            batch = self.api('GET', 'display', params={'start': offset, 'length': 100})
            if not isinstance(batch, list):
                raise ValueError('Xibo display search returned invalid JSON')
            for display in batch:
                display_id = int(display['displayId'])
                if display_id <= 0 or display_id in seen:
                    raise ValueError('Xibo display search returned duplicate/invalid IDs')
                seen.add(display_id)
                displays.append(display)
            if len(batch) != 100:
                break
            offset += len(batch)

        for display in displays:
            display_id = int(display['displayId'])
            name = str(display.get('display') or f'Display {display_id}')
            layout_id = display.get('currentLayoutId')
            layout = display.get('currentLayout')
            layout = str(layout).strip() if layout else None
            if not layout and layout_id not in (None, '', 0, '0'):
                layout = f'Layout {layout_id}'
            config_topic, state_topic, availability_topic = self.topics(display_id)
            config = json.dumps({
                'name': 'Current Layout',
                'unique_id': f'{self.prefix}_display_{display_id}_current_layout',
                'state_topic': state_topic, 'value_template': '{{ value_json.layout }}',
                'json_attributes_topic': state_topic,
                'icon': 'mdi:monitor-dashboard', 'expire_after': 180,
                'availability_mode': 'all',
                'availability': [{'topic': f'{self.prefix}/availability'},
                                 {'topic': availability_topic}],
                'device': {'identifiers': [f'{self.prefix}_display_{display_id}'],
                           'name': name, 'manufacturer': 'Xibo',
                           'model': display.get('clientType') or 'Display',
                           'via_device': self.prefix},
            }, sort_keys=True)
            if self.configs.get(display_id) != config:
                self.publish(config_topic, config)
                self.configs[display_id] = config
            state = {'layout': layout[:255] if layout else None,
                     'layout_id': layout_id, 'display_id': display_id,
                     'display_name': name, 'last_accessed': display.get('lastAccessed'),
                     'source': 'Xibo player NotifyStatus'}
            self.publish(state_topic, json.dumps(state))
            logged_in = display.get('loggedIn', display.get('isLoggedIn', 1))
            authorised = display.get('licensed', 1)
            available = bool(layout) and str(logged_in).lower() not in ('0', 'false', 'no') \
                and str(authorised).lower() not in ('0', 'false', 'no')
            self.publish(availability_topic, 'online' if available else 'offline')

        # Prune only after a complete, successful listing. A network/permission
        # failure must never delete retained discovery for existing displays.
        for display_id in self.known - seen:
            config_topic, state_topic, availability_topic = self.topics(display_id)
            self.publish(availability_topic, 'offline')
            self.publish(config_topic, '')
            self.publish(state_topic, '')
            self.configs.pop(display_id, None)
        self.known = seen
