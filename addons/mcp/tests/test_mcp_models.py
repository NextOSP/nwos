# Part of NextOSP. See LICENSE file for full copyright and licensing details.

import base64
import datetime
import json

from nwos.exceptions import AccessError, ValidationError
from nwos.fields import Command
from nwos.service.model import get_public_method
from nwos.tests import TransactionCase, new_test_user


class TestMcpPolicy(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env['ir.model']._get('res.partner')
        cls.partner_name_field = cls.env['ir.model.fields'].search([
            ('model_id', '=', cls.partner_model.id),
            ('name', '=', 'name'),
        ], limit=1)

    def test_unconfigured_models_are_writable_but_not_deletable(self):
        effective = self.env['mcp.policy']._effective_for_model('res.partner')

        self.assertFalse(effective['configured'])
        self.assertTrue(effective['allow_discovery'])
        self.assertTrue(effective['allow_read'])
        self.assertTrue(effective['allow_create'])
        self.assertTrue(effective['allow_update'])
        self.assertTrue(effective['allow_reports'])
        self.assertTrue(effective['allow_attachments'])
        self.assertFalse(effective['allow_delete'])
        self.assertEqual(effective['max_results'], 100)

    def test_archived_policy_denies_access_instead_of_widening_it(self):
        self.env['mcp.policy'].create({
            'model_id': self.partner_model.id,
            'active': False,
            'allow_read': True,
        })

        effective = self.env['mcp.policy']._effective_for_model('res.partner')

        self.assertTrue(effective['configured'])
        self.assertFalse(effective['allow_discovery'])
        self.assertFalse(effective['allow_read'])

    def test_configured_policy_is_normalized_for_gateway_use(self):
        self.env['mcp.policy'].create({
            'model_id': self.partner_model.id,
            'allow_create': True,
            'allowed_field_ids': [Command.set(self.partner_name_field.ids)],
            'workflow_methods': '# comment\nmessage_post\n',
            'max_results': 12,
        })

        effective = self.env['mcp.policy']._effective_for_model('res.partner')

        self.assertTrue(effective['configured'])
        self.assertTrue(effective['allow_create'])
        self.assertEqual(effective['allowed_fields'], {'name'})
        self.assertEqual(effective['workflow_methods'], {'message_post'})
        self.assertEqual(effective['max_results'], 12)

    def test_policy_rejects_fields_from_another_model(self):
        user_model = self.env['ir.model']._get('res.users')
        foreign_field = self.env['ir.model.fields'].search([
            ('model_id', '=', user_model.id),
            ('name', '=', 'login'),
        ], limit=1)

        with self.assertRaises(ValidationError):
            with self.cr.savepoint():
                self.env['mcp.policy'].create({
                    'model_id': self.partner_model.id,
                    'allowed_field_ids': [Command.set(foreign_field.ids)],
                })

    def test_policy_records_are_not_directly_available_to_gateway_users(self):
        gateway_user = new_test_user(
            self.env,
            login='mcp_gateway_user',
            groups='base.group_user',
        )

        with self.assertRaises(AccessError):
            self.env['mcp.policy'].with_user(gateway_user).check_access('read')


class TestMcpMetadata(TransactionCase):

    def test_internal_service_methods_are_private_to_rpc(self):
        for model_name, method_name in (
            ('mcp.gateway', 'tools_call'),
            ('mcp.audit.log', 'log_event'),
            ('mcp.confirmation.token', 'issue'),
            ('mcp.download.token', 'consume'),
        ):
            with self.assertRaises(AccessError):
                get_public_method(self.env[model_name], method_name)

    def test_audit_log_redacts_values_and_retention_cron_purges_only_old_rows(self):
        audit_model = self.env['mcp.audit.log']
        old_log = audit_model.log_event(
            operation='records_search_read',
            model_name='res.partner',
            record_ids=[1, 2],
            status='error',
            error_message='private failure\n' + ('x' * 600),
            business_values={'name': 'must not be logged'},
        )
        current_log = audit_model.log_event(operation='ping')

        self.assertEqual(old_log.record_ids, '1,2')
        self.assertNotIn('\n', old_log.error_message)
        self.assertLessEqual(len(old_log.error_message), 512)
        self.assertNotIn('private failure', old_log.error_message)
        self.assertNotIn('business_values', old_log._fields)

        old_date = datetime.datetime.now() - datetime.timedelta(days=31)
        self.env.cr.execute(
            'UPDATE mcp_audit_log SET create_date = %s WHERE id = %s',
            [old_date, old_log.id],
        )
        audit_model.invalidate_model(['create_date'])
        self.env['ir.config_parameter'].sudo().set_param('mcp.audit_retention_days', 30)

        self.assertTrue(audit_model._cron_purge_old_logs())
        self.assertFalse(old_log.exists())
        self.assertTrue(current_log.exists())

    def test_confirmation_token_is_user_bound_and_single_use(self):
        partner = self.env['res.partner'].create({'name': 'MCP confirmation target'})
        token_model = self.env['mcp.confirmation.token']
        issued = token_model.issue(
            'action',
            'res.partner',
            partner.ids,
            method_name='action_test',
            arguments={'reason': 'approved'},
            preview={'record': partner.display_name},
        )
        raw_token = issued['confirmation_token']
        other_user = new_test_user(
            self.env,
            login='mcp_confirmation_other_user',
            groups='base.group_user',
        )

        self.assertFalse(token_model.sudo().search([('token_hash', '=', raw_token)]))
        with self.assertRaises(AccessError):
            token_model.with_user(other_user).consume(
                raw_token,
                'action',
                'res.partner',
                partner.ids,
                method_name='action_test',
                arguments={'reason': 'approved'},
            )

        self.assertTrue(token_model.consume(
            raw_token,
            'action',
            'res.partner',
            partner.ids,
            method_name='action_test',
            arguments={'reason': 'approved'},
        ))
        with self.assertRaises(ValidationError):
            token_model.consume(
                raw_token,
                'action',
                'res.partner',
                partner.ids,
                method_name='action_test',
                arguments={'reason': 'approved'},
            )

    def test_download_token_is_hashed_and_single_use(self):
        token_model = self.env['mcp.download.token']
        encoded_payload = base64.b64encode(b'mcp payload')
        issued = token_model.issue(
            name='example.txt',
            mimetype='text/plain',
            payload=encoded_payload,
        )
        raw_token = issued['downloadUrl'].rsplit('/', 1)[-1]

        self.assertEqual(issued['uri'], f'nextosp://binary/{raw_token}')
        self.assertEqual(issued['downloadUrl'], f'/mcp/download/{raw_token}')
        self.assertFalse(token_model.sudo().search([('token_hash', '=', raw_token)]))
        downloaded = token_model.consume(raw_token)
        self.assertEqual(downloaded['name'], 'example.txt')
        self.assertEqual(downloaded['mimeType'], 'text/plain')
        self.assertEqual(downloaded['blob'], encoded_payload.decode())
        with self.assertRaises(ValidationError):
            token_model.consume(raw_token)

    def test_download_token_preserves_an_allowed_company_context(self):
        company = self.env['res.company'].create({'name': 'MCP Secondary Company'})
        self.env.user.write({'company_ids': [Command.link(company.id)]})
        token_model = self.env['mcp.download.token'].with_context(
            allowed_company_ids=[company.id],
        )
        issued = token_model.issue(
            name='company.txt',
            mimetype='text/plain',
            payload=base64.b64encode(b'company payload'),
        )

        raw_token = issued['downloadUrl'].rsplit('/', 1)[-1]
        downloaded = self.env['mcp.download.token'].consume(raw_token)
        self.assertEqual(downloaded['blob'], base64.b64encode(b'company payload').decode())

    def test_settings_are_persisted_as_system_parameters(self):
        settings = self.env['res.config.settings'].create({
            'mcp_enabled': True,
            'mcp_allowed_origins': 'https://one.example,https://two.example',
            'mcp_max_request_bytes': 2048,
            'mcp_max_response_bytes': 4096,
            'mcp_max_batch_size': 4,
            'mcp_max_page_size': 25,
            'mcp_execution_timeout': 15,
            'mcp_confirmation_ttl': 120,
            'mcp_download_ttl': 180,
            'mcp_audit_retention_days': 45,
        })
        settings.execute()
        parameters = self.env['ir.config_parameter'].sudo()

        self.assertEqual(parameters.get_param('mcp.enabled'), 'True')
        self.assertEqual(parameters.get_param('mcp.allowed_origins'), 'https://one.example,https://two.example')
        self.assertEqual(parameters.get_param('mcp.max_request_bytes'), '2048')
        self.assertEqual(parameters.get_param('mcp.max_response_bytes'), '4096')
        self.assertEqual(parameters.get_param('mcp.max_batch_size'), '4')
        self.assertEqual(parameters.get_param('mcp.max_page_size'), '25')
        self.assertEqual(parameters.get_param('mcp.execution_timeout'), '15')
        self.assertEqual(parameters.get_param('mcp.confirmation_ttl'), '120')
        self.assertEqual(parameters.get_param('mcp.download_ttl'), '180')
        self.assertEqual(parameters.get_param('mcp.audit_retention_days'), '45')


class TestMcpGateway(TransactionCase):

    def setUp(self):
        super().setUp()
        self.gateway = self.env['mcp.gateway']
        self.partner_model = self.env['ir.model']._get('res.partner')
        self.policy = self.env['mcp.policy'].create({
            'model_id': self.partner_model.id,
            'allow_create': True,
            'allow_update': True,
            'allow_delete': True,
            'allow_attachments': True,
            'workflow_methods': 'message_post',
        })

    def _tool(self, tool_name, **arguments):
        return self.gateway.tools_call(tool_name, arguments)['structuredContent']

    def test_discovery_grouping_resources_and_prompts(self):
        models = self._tool('models_list', query='partner', limit=1)
        self.assertEqual(len(models['models']), 1)
        self.assertIn('nextCursor', models)

        next_page = self._tool(
            'models_list', query='partner', limit=1, cursor=models['nextCursor'],
        )
        self.assertTrue(next_page['models'])
        with self.assertRaises(ValidationError):
            self._tool('models_list', query='partner', limit=1, cursor='tampered')

        schema = self._tool('model_schema', model='res.partner')
        self.assertIn('name', schema['fields'])
        self.assertNotIn('image_1920', schema['fields'])
        self.assertTrue(schema['operations']['create'])

        sql_view_model, _policy = self.gateway._get_model('res.device', 'read')
        self.assertFalse(sql_view_model._auto)

        groups = self._tool(
            'records_group',
            model='res.partner',
            domain=[],
            groupby=['is_company'],
            aggregates=['__count'],
            limit=10,
        )
        self.assertTrue(groups['groups'])

        parent = self.env['res.partner'].create({
            'name': 'MCP grouping parent',
            'email': 'grouping-parent@example.com',
        })
        child = self.env['res.partner'].create({
            'name': 'MCP grouping child',
            'parent_id': parent.id,
        })
        related_groups = self._tool(
            'records_group',
            model='res.partner',
            domain=[['id', '=', child.id]],
            groupby=['parent_id.email'],
            aggregates=['__count'],
        )
        self.assertTrue(related_groups['groups'])
        with self.assertRaises(AccessError):
            self._tool(
                'records_group',
                model='res.partner',
                domain=[],
                groupby=['create_uid.password'],
                aggregates=['__count'],
            )

        record = self.env['res.partner'].create({'name': 'MCP resource target'})
        resource = self.gateway.resources_read(
            f'nextosp://record/res.partner/{record.id}'
        )
        self.assertEqual(resource['contents'][0]['mimeType'], 'application/json')
        self.assertIn(str(record.id), resource['contents'][0]['text'])
        parameters = self.env['ir.config_parameter'].sudo()
        previous_page_size = parameters.get_param('mcp.max_page_size', '100')
        parameters.set_param('mcp.max_page_size', '2')
        try:
            templates = self.gateway.resource_templates_list()
            self.assertEqual(len(templates['resourceTemplates']), 2)
            self.assertIn('nextCursor', templates)
            next_templates = self.gateway.resource_templates_list(
                cursor=templates['nextCursor'],
            )
            self.assertTrue(next_templates['resourceTemplates'])
        finally:
            parameters.set_param('mcp.max_page_size', previous_page_size)

        prompt = self.gateway.prompts_get('record_lookup', {
            'model': 'res.partner',
            'goal': 'Find the resource target',
        })
        self.assertEqual(prompt['messages'][0]['role'], 'user')

    def test_sensitive_fields_are_blocked_in_schema_domains_and_order(self):
        user_schema = self._tool('model_schema', model='res.users')
        self.assertNotIn('password', user_schema['fields'])

        with self.assertRaises(AccessError):
            self._tool('model_schema', model='ir.logging')

        with self.assertRaises(AccessError):
            self._tool(
                'records_search_read',
                model='res.users',
                domain=[['password', '!=', False]],
                fields=['id'],
            )
        with self.assertRaises(AccessError):
            self._tool(
                'records_search_read',
                model='res.users',
                domain=[],
                fields=['id'],
                order='password desc',
            )
        self.env['mcp.policy'].create({
            'model_id': self.env['ir.model']._get('res.partner.category').id,
            'allow_create': False,
        })
        with self.assertRaises(AccessError):
            self._tool(
                'record_create',
                model='res.partner',
                values={'name': 'Nested bypass', 'category_id': [[0, 0, {'name': 'Hidden'}]]},
            )
        with self.assertRaises(ValidationError):
            self.policy.write({'workflow_methods': 'write'})

        partner = self.env['res.partner'].create({'name': 'MCP reference target'})
        attachment = self.env['ir.attachment'].create({
            'name': 'reference-test',
            'type': 'url',
            'url': 'https://example.com/reference-test',
            'res_model': 'res.partner',
            'res_id': partner.id,
        })
        self.env['mcp.policy'].create({
            'model_id': self.env['ir.model']._get('ir.attachment').id,
            'allow_update': True,
        })
        with self.assertRaises(AccessError):
            self._tool(
                'records_update',
                model='ir.attachment',
                ids=[attachment.id],
                values={'res_model': 'ir.config_parameter', 'res_id': 1},
            )

    def test_crud_workflow_and_delete_confirmations(self):
        created = self._tool(
            'record_create', model='res.partner', values={'name': 'MCP CRUD target'},
        )['record']
        record_id = created['id']

        updated = self._tool(
            'records_update',
            model='res.partner',
            ids=[record_id],
            values={'comment': 'Updated through MCP'},
        )
        self.assertEqual(updated['updated_ids'], [record_id])

        preview = self._tool(
            'action_preview',
            model='res.partner',
            ids=[record_id],
            method='message_post',
            kwargs={'body': 'Posted through MCP'},
        )
        action_arguments = {
            'model': 'res.partner',
            'ids': [record_id],
            'method': 'message_post',
            'kwargs': {'body': 'Posted through MCP'},
            'confirmation_token': preview['confirmation_token'],
        }
        action = self._tool('action_confirm', **action_arguments)
        self.assertEqual(action['method'], 'message_post')
        with self.assertRaises(ValidationError):
            self._tool('action_confirm', **action_arguments)

        delete_preview = self._tool(
            'records_delete_preview', model='res.partner', ids=[record_id],
        )
        deleted = self._tool(
            'records_delete_confirm',
            model='res.partner',
            ids=[record_id],
            confirmation_token=delete_preview['confirmation_token'],
        )
        self.assertEqual(deleted['deleted_ids'], [record_id])
        self.assertFalse(self.env['res.partner'].browse(record_id).exists())

    def test_attachments_binary_fields_and_reports_use_download_tokens(self):
        partner = self.env['res.partner'].create({'name': 'MCP binary target'})
        uploaded = self._tool(
            'attachment_upload',
            model='res.partner',
            id=partner.id,
            name='example.txt',
            mimetype='text/plain',
            data=base64.b64encode(b'attachment payload').decode(),
        )['attachment']
        self.assertTrue(uploaded['resource']['downloadUrl'].startswith('/mcp/download/'))
        moved_target = self.env['res.partner'].create({'name': 'MCP moved attachment target'})
        uploaded_record = self.env['ir.attachment'].browse(uploaded['id'])
        uploaded_token = uploaded['resource']['downloadUrl'].rsplit('/', 1)[-1]
        uploaded_record.res_id = moved_target.id
        with self.assertRaises(ValidationError):
            self.gateway.download(uploaded_token)
        uploaded_record.res_id = partner.id
        attachment_resource = self.gateway.resources_read(
            f"nextosp://attachment/{uploaded['id']}"
        )
        self.assertIn('/mcp/download/', attachment_resource['contents'][0]['text'])
        self.assertTrue(self._tool(
            'attachments_list', model='res.partner', ids=[partner.id],
        )['attachments'])

        png = base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+'
            'A8AAQUBAScY42YAAAAASUVORK5CYII='
        )
        partner.image_1920 = base64.b64encode(png)
        binary = self._tool(
            'binary_field_download',
            model='res.partner',
            id=partner.id,
            field='image_1920',
            filename='image.png',
            mimetype='image/png',
        )
        token = binary['resource']['downloadUrl'].rsplit('/', 1)[-1]
        descriptor = self.gateway.resources_read(binary['resource']['uri'])
        self.assertIn('/mcp/download/', descriptor['contents'][0]['text'])
        self.assertNotIn('blob', descriptor['contents'][0])
        downloaded = self.gateway.download(token)
        self.assertTrue(downloaded['content'].startswith(b'\x89PNG'))
        with self.assertRaises(ValidationError):
            self.gateway.download(token)

        revoked_binary = self._tool(
            'binary_field_download',
            model='res.partner',
            id=partner.id,
            field='image_1920',
        )
        self.policy.allow_attachments = False
        revoked_token = revoked_binary['resource']['downloadUrl'].rsplit('/', 1)[-1]
        with self.assertRaises(AccessError):
            self.gateway.download(revoked_token)
        self.policy.allow_attachments = True

        field_revoked_binary = self._tool(
            'binary_field_download',
            model='res.partner',
            id=partner.id,
            field='image_1920',
        )
        image_field = self.env['ir.model.fields'].search([
            ('model_id', '=', self.partner_model.id),
            ('name', '=', 'image_1920'),
        ], limit=1)
        self.policy.write({
            'blocked_field_ids': [Command.link(image_field.id)],
        })
        field_revoked_token = field_revoked_binary['resource']['downloadUrl'].rsplit('/', 1)[-1]
        with self.assertRaises(AccessError):
            self.gateway.download(field_revoked_token)
        with self.assertRaises(AccessError):
            self._tool(
                'binary_field_download',
                model='res.partner',
                id=partner.id,
                field='image_1920',
            )
        self.policy.write({'blocked_field_ids': [Command.clear()]})

        model_policy = self.env['mcp.policy'].create({
            'model_id': self.env['ir.model']._get('ir.model').id,
            'allow_reports': True,
        })
        reports = self._tool('reports_list', model='ir.model')['reports']
        self.assertTrue(reports)
        rendered_resource = self.gateway.resources_read(
            'nextosp://report/ir.model/%s/%s?format=html'
            % (reports[0]['id'], self.partner_model.id)
        )
        rendered = json.loads(rendered_resource['contents'][0]['text'])
        report_token = rendered['resource']['downloadUrl'].rsplit('/', 1)[-1]
        report = self.gateway.download(report_token)
        self.assertEqual(report['mimetype'], 'text/html')
        self.assertTrue(report['content'])
        self.assertTrue(model_policy)
