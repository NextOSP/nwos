# Part of NextOSP. See LICENSE file for full copyright and licensing details.

import base64
import datetime
import json

from nwos.tests import HttpCase, tagged


@tagged('-at_install', 'post_install')
class TestMcpHttp(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        parameters = cls.env['ir.config_parameter'].sudo()
        parameters.set_param('mcp.enabled', 'True')
        parameters.set_param('mcp.allowed_origins', '')
        parameters.set_param('mcp.max_page_size', '100')
        cls.api_key = cls.env['res.users.apikeys'].with_user(
            cls.env.ref('base.user_admin')
        )._generate(
            scope='rpc',
            name='MCP HTTP tests',
            expiration_date=datetime.datetime.now() + datetime.timedelta(days=1),
        )

    def _mcp(self, payload, headers=None):
        request_headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        request_headers.update(headers or {})
        return self.url_open(
            '/mcp',
            data=json.dumps(payload),
            headers=request_headers,
            method='POST',
        )

    def test_initialize_and_ping(self):
        response = self._mcp({
            'jsonrpc': '2.0',
            'id': 'initialize-1',
            'method': 'initialize',
            'params': {
                'protocolVersion': '2025-11-25',
                'capabilities': {},
                'clientInfo': {'name': 'NextOSP test client', 'version': '1.0'},
            },
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual(response.headers['MCP-Protocol-Version'], '2025-11-25')
        self.assertTrue(response.headers['Content-Type'].startswith('application/json'))
        body = response.json()
        self.assertEqual(body['jsonrpc'], '2.0')
        self.assertEqual(body['id'], 'initialize-1')
        self.assertEqual(body['result']['protocolVersion'], '2025-11-25')
        self.assertEqual(
            set(body['result']['capabilities']),
            {'tools', 'resources', 'prompts'},
        )
        self.assertEqual(body['result']['serverInfo']['name'], 'nextosp-mcp')

        ping = self._mcp({
            'jsonrpc': '2.0',
            'id': 2,
            'method': 'ping',
            'params': {},
        })
        self.assertEqual(ping.status_code, 200)
        self.assertEqual(ping.json()['result'], {})

    def test_tools_list_advertises_generic_module_coverage(self):
        response = self._mcp({
            'jsonrpc': '2.0',
            'id': 3,
            'method': 'tools/list',
            'params': {},
        })

        self.assertEqual(response.status_code, 200)
        tools = {tool['name']: tool for tool in response.json()['result']['tools']}
        expected = {
            'models_list',
            'model_schema',
            'model_views',
            'records_search_read',
            'records_read',
            'records_group',
            'record_create',
            'records_update',
            'records_delete_preview',
            'records_delete_confirm',
            'action_preview',
            'action_confirm',
            'reports_list',
            'report_render',
            'attachments_list',
            'attachment_upload',
            'binary_field_download',
        }
        self.assertEqual(set(tools), expected)
        self.assertTrue(tools['records_search_read']['annotations']['readOnlyHint'])
        self.assertTrue(tools['records_delete_confirm']['annotations']['destructiveHint'])

    def test_notification_returns_empty_accepted_response(self):
        response = self._mcp({
            'jsonrpc': '2.0',
            'method': 'notifications/initialized',
            'params': {},
        })

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.content, b'')

    def test_protocol_errors_batches_and_invalid_authentication(self):
        unknown = self._mcp({
            'jsonrpc': '2.0', 'id': 10, 'method': 'unknown/method', 'params': {},
        })
        self.assertEqual(unknown.status_code, 200)
        self.assertEqual(unknown.json()['error']['code'], -32601)

        malformed = self.url_open(
            '/mcp',
            data='{',
            method='POST',
            headers={
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
        )
        self.assertEqual(malformed.status_code, 400)
        self.assertEqual(malformed.json()['error']['code'], -32700)

        unsupported_version = self._mcp(
            {'jsonrpc': '2.0', 'id': 11, 'method': 'ping', 'params': {}},
            {'MCP-Protocol-Version': '1900-01-01'},
        )
        self.assertEqual(unsupported_version.status_code, 400)

        batch = self._mcp([
            {'jsonrpc': '2.0', 'id': 12, 'method': 'ping', 'params': {}},
            {'jsonrpc': '2.0', 'id': 13, 'method': 'prompts/list', 'params': {}},
        ])
        self.assertEqual([item['id'] for item in batch.json()], [12, 13])

        invalid_key = self.url_open(
            '/mcp',
            data=json.dumps({'jsonrpc': '2.0', 'id': 14, 'method': 'ping'}),
            method='POST',
            headers={
                'Authorization': 'Bearer invalid',
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
        )
        self.assertEqual(invalid_key.status_code, 401)

    def test_tool_failures_are_mcp_results_and_are_audited(self):
        # Creation is enabled by default, so pin an explicit policy that denies
        # it to exercise a policy-blocked failure path.
        self.env['mcp.policy'].create({
            'model_id': self.env['ir.model']._get('res.partner').id,
            'allow_create': False,
        })
        record_name = 'MCP policy blocked HTTP create'
        response = self._mcp({
            'jsonrpc': '2.0',
            'id': 15,
            'method': 'tools/call',
            'params': {
                'name': 'record_create',
                'arguments': {
                    'model': 'res.partner',
                    'values': {'name': record_name},
                },
            },
        })

        result = response.json()['result']
        self.assertTrue(result['isError'])
        self.assertNotIn('traceback', result['content'][0]['text'].lower())
        self.env.invalidate_all()
        self.assertFalse(self.env['res.partner'].search([('name', '=', record_name)]))
        audit = self.env['mcp.audit.log'].sudo().search([
            ('operation', '=', 'record_create'),
            ('status', '=', 'error'),
        ], order='id desc', limit=1)
        self.assertTrue(audit)
        self.assertFalse(audit.error_message)

        poisoned_value = 'must-not-be-persisted-as-an-audit-record-id'
        poisoned = self._mcp({
            'jsonrpc': '2.0',
            'id': 'audit-metadata-sanitization',
            'method': 'tools/call',
            'params': {
                'name': 'records_read',
                'arguments': {
                    'model': 'res.partner',
                    'ids': poisoned_value,
                },
            },
        })
        self.assertTrue(poisoned.json()['result']['isError'])
        self.env.invalidate_all()
        poisoned_audit = self.env['mcp.audit.log'].sudo().search([
            ('request_id', '=', 'audit-metadata-sanitization'),
        ], limit=1)
        self.assertTrue(poisoned_audit)
        self.assertFalse(poisoned_audit.record_ids)

    def test_resources_and_prompts_round_trip(self):
        resource = self._mcp({
            'jsonrpc': '2.0',
            'id': 16,
            'method': 'resources/read',
            'params': {'uri': 'nextosp://model/res.partner/schema'},
        }).json()['result']
        self.assertEqual(resource['contents'][0]['mimeType'], 'application/json')
        self.assertIn('res.partner', resource['contents'][0]['text'])

        prompt = self._mcp({
            'jsonrpc': '2.0',
            'id': 17,
            'method': 'prompts/get',
            'params': {
                'name': 'record_lookup',
                'arguments': {'model': 'res.partner', 'goal': 'Find a customer'},
            },
        }).json()['result']
        self.assertEqual(prompt['messages'][0]['role'], 'user')

    def test_configured_response_limit_bounds_the_complete_json_response(self):
        parameters = self.env['ir.config_parameter'].sudo()
        previous = parameters.get_param('mcp.max_response_bytes', '1048576')
        parameters.set_param('mcp.max_response_bytes', '1024')
        try:
            response = self._mcp({
                'jsonrpc': '2.0',
                'id': 'bounded-response',
                'method': 'prompts/get',
                'params': {
                    'name': 'record_lookup',
                    'arguments': {
                        'model': 'res.partner',
                        'goal': 'x' * 4096,
                    },
                },
            })

            policy = self.env['mcp.policy'].search([
                ('model_name', '=', 'res.partner'),
            ], limit=1)
            if policy:
                policy.allow_create = True
            else:
                policy = self.env['mcp.policy'].create({
                    'model_id': self.env['ir.model']._get('res.partner').id,
                    'allow_create': True,
                })
            record_name = 'bounded-mutation-' + ('y' * 600)
            mutation = self._mcp({
                'jsonrpc': '2.0',
                'id': 'bounded-mutation',
                'method': 'tools/call',
                'params': {
                    'name': 'record_create',
                    'arguments': {
                        'model': 'res.partner',
                        'values': {'name': record_name},
                    },
                },
            })
        finally:
            parameters.set_param('mcp.max_response_bytes', previous)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['id'], 'bounded-response')
        self.assertEqual(response.json()['error']['code'], -32009)
        self.assertLessEqual(len(response.content), 1024)
        self.assertEqual(mutation.json()['id'], 'bounded-mutation')
        self.assertEqual(mutation.json()['error']['code'], -32009)
        self.env.invalidate_all()
        self.assertFalse(self.env['res.partner'].search([('name', '=', record_name)]))

    def test_allowed_origin_cors_preflight(self):
        origin = 'https://assistant.example'
        self.env['ir.config_parameter'].sudo().set_param('mcp.allowed_origins', origin)

        response = self.url_open(
            '/mcp',
            method='OPTIONS',
            headers={
                'Origin': origin,
                'Access-Control-Request-Method': 'POST',
                'Access-Control-Request-Headers': 'Authorization, Content-Type',
            },
        )

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.headers['Access-Control-Allow-Origin'], origin)
        self.assertEqual(response.headers['Access-Control-Allow-Methods'], 'POST')
        self.assertIn('Authorization', response.headers['Access-Control-Allow-Headers'])

        download_preflight = self.url_open(
            '/mcp/download/not-inspected-during-preflight',
            method='OPTIONS',
            headers={
                'Origin': origin,
                'Access-Control-Request-Method': 'GET',
                'Access-Control-Request-Headers': 'Authorization',
            },
        )
        self.assertEqual(download_preflight.status_code, 204)
        self.assertEqual(
            download_preflight.headers['Access-Control-Allow-Methods'], 'GET'
        )

    def test_endpoint_can_be_disabled_and_rejects_explicit_database_selection(self):
        parameters = self.env['ir.config_parameter'].sudo()
        parameters.set_param('mcp.enabled', 'False')
        try:
            disabled = self._mcp({
                'jsonrpc': '2.0', 'id': 18, 'method': 'ping', 'params': {},
            })
            self.assertEqual(disabled.status_code, 404)
        finally:
            parameters.set_param('mcp.enabled', 'True')

        explicit_database = self.url_open(
            f'/mcp?db={self.env.cr.dbname}',
            data=json.dumps({
                'jsonrpc': '2.0', 'id': 19, 'method': 'ping', 'params': {},
            }),
            method='POST',
            headers={
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
        )
        self.assertEqual(explicit_database.status_code, 400)

        # The X-NWOS-Database routing header is the supported multi-database
        # mechanism and must be accepted.
        database_header = self.url_open(
            '/mcp',
            data=json.dumps({
                'jsonrpc': '2.0', 'id': 20, 'method': 'ping', 'params': {},
            }),
            method='POST',
            headers={
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'X-NWOS-Database': self.env.cr.dbname,
            },
        )
        self.assertEqual(database_header.status_code, 200)

    def test_download_url_is_binary_and_single_use(self):
        payload = b'private MCP download'
        issued = self.env['mcp.download.token'].with_user(
            self.env.ref('base.user_admin')
        ).issue(
            name='private.txt',
            mimetype='text/plain',
            payload=base64.b64encode(payload),
        )
        headers = {'Authorization': f'Bearer {self.api_key}'}

        response = self.url_open(issued['downloadUrl'], headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, payload)
        self.assertEqual(response.headers['Content-Type'], 'text/plain')
        self.assertEqual(response.headers['Cache-Control'], 'private, no-store')

        reused = self.url_open(issued['downloadUrl'], headers=headers)
        self.assertEqual(reused.status_code, 404)

    def test_transport_rejects_unsafe_content_negotiation_and_origin(self):
        payload = {'jsonrpc': '2.0', 'id': 4, 'method': 'ping', 'params': {}}

        wrong_content_type = self._mcp(payload, {'Content-Type': 'text/plain'})
        self.assertEqual(wrong_content_type.status_code, 415)
        self.assertEqual(wrong_content_type.json()['error']['code'], -32600)

        event_stream_only = self._mcp(payload, {'Accept': 'text/event-stream'})
        self.assertEqual(event_stream_only.status_code, 406)
        self.assertEqual(event_stream_only.json()['error']['code'], -32600)

        untrusted_origin = self._mcp(payload, {'Origin': 'https://untrusted.example'})
        self.assertEqual(untrusted_origin.status_code, 403)
        self.assertEqual(untrusted_origin.json()['error']['code'], -32001)
