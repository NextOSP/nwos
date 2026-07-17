# Part of NextOSP. See LICENSE file for full copyright and licensing details.

import json

from nwos import Command
from nwos.tests import HttpCase, TransactionCase, tagged


class RealtimeBusCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'NextBot Bus User',
            'login': 'nextbot-bus-user',
            'email': 'nextbot-bus@example.com',
            'group_ids': [Command.set([cls.env.ref('base.group_user').id])],
        })

    def _run(self):
        conversation = self.env['nextbot.conversation'].with_user(self.user)._create_for_user()
        return self.env['nextbot.run'].sudo().create({
            'conversation_id': conversation.id,
            'company_id': self.user.company_id.id,
            'allowed_company_ids': [Command.set(self.user.company_ids.ids)],
            'status': 'queued',
            'prompt': 'Hello NextBot',
        }).with_user(self.user)

    def _bus_messages(self):
        """Run precommit hooks (bus row creation) and return nextbot bus rows."""
        self.env.cr.flush()
        partner_channel = json.dumps(
            (self.env.cr.dbname, 'res.partner', self.user.partner_id.id),
            separators=(',', ':'),
        )
        rows = self.env['bus.bus'].sudo().search([('channel', '=', partner_channel)])
        messages = [json.loads(row.message) for row in rows]
        # Discuss/mail can also notify the same partner channel; only the
        # workspace push notifications are under test here.
        return [message for message in messages if message['type'] == 'nextbot.run/event']


@tagged('nextbot_agent')
class TestRealtimeBus(RealtimeBusCase):

    def test_add_event_sends_partner_bus_notification(self):
        run = self._run()

        event = run._add_event('assistant.text.delta', {'delta': 'Hello'})

        messages = self._bus_messages()
        self.assertEqual(1, len(messages))
        self.assertEqual('nextbot.run/event', messages[0]['type'])
        payload = messages[0]['payload']
        self.assertEqual(run.id, payload['run_id'])
        self.assertEqual(run.conversation_id.id, payload['conversation_id'])
        self.assertEqual(event.sequence, payload['event']['sequence'])
        self.assertEqual('assistant.text.delta', payload['event']['type'])
        self.assertEqual({'delta': 'Hello'}, payload['event']['payload'])

    def test_every_event_type_is_pushed_in_order(self):
        run = self._run()

        run._add_event('run.status', {'status': 'running'})
        run._add_event('assistant.text.delta', {'delta': 'Hi'})
        run._add_event('assistant.text.completed', {'text': 'Hi'})

        messages = self._bus_messages()
        self.assertEqual(
            [1, 2, 3],
            [message['payload']['event']['sequence'] for message in messages],
        )

    def test_bus_payload_is_redacted(self):
        run = self._run()

        run._add_event('tool.completed', {'arguments': {'api_key': 'super-secret'}})

        messages = self._bus_messages()
        self.assertEqual(
            '[redacted]',
            messages[0]['payload']['event']['payload']['arguments']['api_key'],
        )

    def test_oversized_payload_falls_back_to_fetch_required(self):
        run = self._run()

        # redact() caps single strings at 4000 chars, so oversize needs many keys.
        event = run._add_event(
            'tool.completed',
            {'part_%d' % index: 'x' * 4000 for index in range(20)},
        )

        messages = self._bus_messages()
        self.assertEqual(1, len(messages))
        payload = messages[0]['payload']
        self.assertTrue(payload['fetch_required'])
        self.assertEqual(event.sequence, payload['sequence'])
        self.assertEqual(run.id, payload['run_id'])
        self.assertNotIn('event', payload)


@tagged('nextbot_agent', 'post_install', '-at_install')
class TestRealtimeBootstrap(HttpCase):

    def test_bootstrap_advertises_bus_transport(self):
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'NextBot Bootstrap User',
            'login': 'nextbot-bootstrap-user',
            'password': 'nextbot-bootstrap-user',
            'email': 'nextbot-bootstrap@example.com',
            'group_ids': [Command.set([self.env.ref('base.group_user').id])],
        })
        self.authenticate(user.login, 'nextbot-bootstrap-user')

        result = self.make_jsonrpc_request('/nextbot/bootstrap', {})

        self.assertEqual('bus_push', result['features']['event_transport'])
        self.assertEqual('nextbot.run/event', result['features']['event_bus_notification'])
