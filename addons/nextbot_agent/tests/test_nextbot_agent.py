# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from datetime import timedelta
import json
from unittest.mock import patch

from nwos import Command, fields
from nwos.exceptions import AccessError, ValidationError
from nwos.tests import TransactionCase, tagged


@tagged('nextbot_agent')
class TestNextBotAgent(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'NextBot Runtime User',
            'login': 'nextbot-runtime-user',
            'email': 'nextbot-runtime@example.com',
            'group_ids': [Command.set([cls.env.ref('base.group_user').id])],
        })

    def _conversation(self, user=None):
        user = user or self.user
        return self.env['nextbot.conversation'].with_user(user)._create_for_user()

    def _run(self, conversation, status='queued', prompt='Hello NextBot'):
        user = conversation.user_id
        return self.env['nextbot.run'].sudo().create({
            'conversation_id': conversation.id,
            'company_id': user.company_id.id,
            'allowed_company_ids': [Command.set(user.company_ids.ids)],
            'status': status,
            'prompt': prompt,
        }).with_user(user).with_context(allowed_company_ids=user.company_ids.ids)

    def _enable_ai(self):
        parameters = self.env['ir.config_parameter'].sudo()
        parameters.set_param('base.ai.enabled', True)
        parameters.set_param('base.ai.provider', 'openai')
        parameters.set_param('base.ai.endpoint', 'https://api.openai.example/v1')
        parameters.set_param('base.ai.model.intelligent', 'nextbot-test')
        parameters.set_param('base.ai.api_key', 'test-key')

    @staticmethod
    def _provider_response(message):
        class Response:
            headers = {'Content-Type': 'application/json; charset=utf-8'}
            encoding = 'utf-8'
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {'choices': [{'message': message}]}

        return Response()

    def _planner_response(self, step_type='write'):
        return self._provider_response({'tool_calls': [{
            'id': 'plan_1',
            'type': 'function',
            'function': {
                'name': 'set_task_plan',
                'arguments': json.dumps({
                    'goal': 'Complete the test task',
                    'completion_criteria': ['Return a verified response'],
                    'steps': [{
                        'key': 'execute',
                        'title': 'Execute',
                        'objective': 'Complete the test request',
                        'type': step_type,
                        'depends_on': [],
                    }],
                }),
            },
        }]})

    def test_new_conversations_are_distinct_private_discuss_groups(self):
        first = self._conversation()
        second = self._conversation()

        self.assertNotEqual(first, second)
        self.assertEqual('group', first.channel_id.channel_type)
        self.assertEqual(
            {self.user.partner_id.id, self.env.ref('base.partner_root').id},
            set(first.channel_id.sudo().channel_member_ids.partner_id.ids),
        )

    def test_event_sequence_is_ordered_and_replayable(self):
        run = self._run(self._conversation())

        first = run._add_event('run.status', {'status': 'queued'})
        second = run._add_event('activity.summary', {'message': 'Preparing'})

        self.assertEqual((1, 2), (first.sequence, second.sequence))
        self.assertEqual(
            [1, 2],
            self.env['nextbot.run.event'].with_user(self.user).search([
                ('run_id', '=', run.id),
            ]).mapped('sequence'),
        )

    def test_json_timestamps_are_iso_utc(self):
        run = self._run(self._conversation(), status='running')
        run.sudo().started_at = fields.Datetime.now()
        event = run._add_event('run.status', {'status': 'running'})

        self.assertRegex(run._serialize()['started_at'], r'^\d{4}-\d{2}-\d{2}T.*Z$')
        self.assertRegex(event._serialize()['timestamp'], r'^\d{4}-\d{2}-\d{2}T.*Z$')

    def test_active_run_blocks_conversation_archive_and_delete(self):
        conversation = self._conversation()
        run = self._run(conversation, status='queued')

        with self.assertRaises(ValidationError):
            conversation.sudo().write({'active': False})
        with self.assertRaises(ValidationError):
            conversation.sudo().unlink()

        run.with_user(self.user).action_cancel()
        conversation.sudo().write({'active': False})
        self.assertFalse(conversation.active)

    def test_workspace_never_creates_discuss_dm(self):
        imported = self.env['nextbot.conversation'].with_user(
            self.user,
        )._get_or_create_for_user()

        self.assertFalse(imported, 'The workspace must not seed a Discuss DM with the bot.')

    def test_nextbot_channels_hidden_from_discuss(self):
        conversation = self._conversation()

        channels = self.env['discuss.channel'].with_user(self.user)._get_channels_as_member()

        self.assertNotIn(conversation.channel_id, channels)

    def test_workspace_delete_archives_canonical_chat(self):
        bot_partner = self.env.ref('base.partner_root')
        self.env['discuss.channel'].with_user(self.user)._get_or_create_chat([
            bot_partner.id,
            self.user.partner_id.id,
        ])
        canonical = self.env['nextbot.conversation'].with_user(
            self.user,
        )._get_or_create_for_user()
        self.assertTrue(canonical, 'A pre-existing legacy DM must still be imported.')

        hard_deleted = canonical._delete_from_workspace()

        self.assertFalse(hard_deleted)
        self.assertTrue(canonical.with_context(active_test=False).exists())
        self.assertFalse(canonical.active)
        imported = self.env['nextbot.conversation'].with_user(
            self.user,
        )._get_or_create_for_user(reactivate=False)
        self.assertEqual(canonical, imported)
        self.assertFalse(imported.active)

    def test_all_tools_available_and_writes_need_approval(self):
        registry = self.env['nextbot.tool.registry'].with_user(self.user)

        names = [item['function']['name'] for item in registry.get_definitions()]
        self.assertIn('search_records', names)
        self.assertFalse(registry.requires_approval('search_records'))
        self.assertTrue(registry.requires_approval('prepare_create_record'))

    def test_generic_write_tool_blocks_credential_models(self):
        registry = self.env['nextbot.tool.registry'].with_user(self.user)
        run = self._run(self._conversation())

        with self.assertRaises(AccessError):
            registry.prepare_write(
                'prepare_update_record',
                {
                    'model': 'ir.config_parameter',
                    'res_id': 1,
                    'values': {'value': 'must-not-change'},
                },
                run,
            )

    def test_generic_write_tool_blocks_secret_fields(self):
        registry = self.env['nextbot.tool.registry'].with_user(self.user)
        run = self._run(self._conversation())

        with self.assertRaises(AccessError):
            registry.prepare_write(
                'prepare_update_record',
                {
                    'model': 'res.users',
                    'res_id': self.user.id,
                    'values': {'password': 'must-not-change'},
                },
                run,
            )

    def test_product_bulk_create_deduplicates_existing_and_request_rows(self):
        class FakeRecord:
            _fields = {'name': object(), 'default_code': object(), 'barcode': object()}

            def __init__(self, record_id, **values):
                self.id = record_id
                self.values = values
                self.display_name = values.get('name') or values.get('default_code')

            def __getitem__(self, key):
                return self.values.get(key)

        class FakeProductModel:
            _name = 'product.template'
            _fields = FakeRecord._fields

            def with_context(self, **_context):
                return self

            def search(self, _domain, limit=None):
                return [FakeRecord(41, name='Existing product', default_code='SKU-1', barcode=False)]

        registry = self.env['nextbot.tool.registry']
        accepted, skipped = registry._dedupe_create_records(FakeProductModel(), [
            {'name': 'Should match existing', 'default_code': 'sku-1'},
            {'name': 'New product', 'default_code': 'SKU-2'},
            {'name': 'Repeated in request', 'default_code': 'sku-2'},
            {'name': 'Another product', 'default_code': 'SKU-3'},
        ])

        self.assertEqual(['SKU-2', 'SKU-3'], [item['default_code'] for item in accepted])
        self.assertEqual(['already_exists', 'duplicate_in_request'], [item['reason'] for item in skipped])
        self.assertEqual(41, skipped[0]['matched_id'])

    def test_all_duplicate_product_create_is_a_completed_noop_without_approval(self):
        run = self._run(self._conversation(), status='running').with_user(self.user)
        registry = self.env['nextbot.tool.registry']
        prepared = {
            'arguments': {
                'model': 'product.template',
                'records': [],
                'duplicate_report': [{
                    'name': 'Existing product',
                    'default_code': 'SKU-1',
                    'reason': 'already_exists',
                    'matched_id': 41,
                    'matched_name': '[SKU-1] Existing product',
                }],
            },
            'summary': 'No new products',
            'summary_html': '',
        }
        with patch.object(type(registry), 'prepare_write', return_value=prepared):
            result = run._execute_tool_call('prepare_create_records', {
                'model': 'product.template',
                'records': [{'name': 'Existing product', 'default_code': 'SKU-1'}],
            })

        self.assertTrue(result['no_op'])
        self.assertEqual('skipped_existing', result['status'])
        self.assertEqual(1, result['skipped_count'])
        self.assertFalse(run.approval_ids)
        self.assertEqual('completed', run.tool_execution_ids.state)

    def test_reject_approval_never_executes_tool(self):
        run = self._run(self._conversation(), status='waiting_approval')
        approval = self.env['nextbot.approval'].sudo().create_pending(
            run=run,
            tool_name='prepare_update_record',
            arguments={
                'model': 'res.partner',
                'res_id': self.user.partner_id.id,
                'values': {'phone': 'should-not-be-written'},
            },
            summary='Update phone',
            ttl_minutes=15,
        ).with_user(self.user)

        approval.action_reject()

        self.assertEqual('rejected', approval.state)
        self.assertEqual('waiting_input', run.status)
        self.assertNotEqual('should-not-be-written', self.user.partner_id.phone)

    def test_runtime_persists_provider_response_and_messages(self):
        self._enable_ai()
        run = self._run(self._conversation(), prompt='Say hello briefly')
        with patch('nwos.addons.mail_bot.models.mail_bot.requests.post') as request_post:
            request_post.side_effect = [
                self._planner_response(),
                self._provider_response({'content': 'Hello from NextBot.'}),
            ]

            run._execute_runtime()

        self.assertEqual('completed', run.status)
        self.assertEqual('Hello from NextBot.', run.response_text)
        self.assertTrue(run.input_message_id)
        self.assertTrue(run.response_message_id)
        self.assertEqual(self.env.ref('base.partner_root'), run.response_message_id.author_id)
        self.assertIn('assistant.text.completed', run.event_ids.mapped('event_type'))
        deltas = run.event_ids.filtered(
            lambda event: event.event_type == 'assistant.text.delta'
        ).mapped('payload')
        self.assertEqual('Hello from NextBot.', ''.join(item['delta'] for item in deltas))
        self.assertTrue(all(len(item['delta']) <= 640 for item in deltas))

    def test_runtime_turns_write_tool_into_persistent_approval(self):
        self._enable_ai()
        run = self._run(self._conversation(), prompt='Update my phone')
        tool_call = {
            'id': 'update_phone',
            'type': 'function',
            'function': {
                'name': 'prepare_post_comment',
                'arguments': json.dumps({
                    'model': 'res.partner',
                    'res_id': self.user.partner_id.id,
                    'body': 'This must wait for approval.',
                }),
            },
        }
        with patch('nwos.addons.mail_bot.models.mail_bot.requests.post') as request_post:
            request_post.side_effect = [
                self._planner_response(),
                self._provider_response({'tool_calls': [tool_call]}),
                self._provider_response({'content': 'The proposal is ready.'}),
            ]

            run._execute_runtime()

        self.assertEqual('waiting_approval', run.status)
        self.assertEqual(1, len(run.approval_ids))
        self.assertEqual('pending', run.approval_ids.state)
        self.assertFalse(self.user.partner_id.message_ids.filtered(
            lambda message: 'This must wait for approval.' in (message.body or '')
        ))

    def test_expired_approval_persists_terminal_state(self):
        run = self._run(self._conversation(), status='waiting_approval')
        approval = self.env['nextbot.approval'].sudo().create({
            'run_id': run.id,
            'tool_name': 'prepare_update_record',
            'arguments': {
                'model': 'res.partner',
                'res_id': self.user.partner_id.id,
                'values': {'phone': 'never-written'},
            },
            'expires_at': fields.Datetime.now() - timedelta(minutes=1),
        }).with_user(self.user)

        result = approval.action_approve()

        self.assertEqual('expired', result['state'])
        self.assertEqual('expired', approval.state)
        self.assertEqual('waiting_input', run.status)
        self.assertNotEqual('never-written', self.user.partner_id.phone)

    def test_cron_expires_approval_with_events_and_final_response(self):
        run = self._run(self._conversation(), status='waiting_approval')
        approval = self.env['nextbot.approval'].sudo().create({
            'run_id': run.id,
            'tool_name': 'prepare_update_record',
            'arguments': {
                'model': 'res.partner',
                'res_id': self.user.partner_id.id,
                'values': {'phone': 'never-written'},
            },
            'expires_at': fields.Datetime.now() - timedelta(minutes=1),
        })

        processed = self.env['nextbot.approval']._cron_expire_pending()

        self.assertEqual(1, processed)
        self.assertEqual('expired', approval.state)
        self.assertEqual('waiting_input', run.status)
        self.assertIn('No ERP data was changed', run.response_text)
        self.assertTrue(run.response_message_id)
        resolved = run.event_ids.filtered(lambda event: event.event_type == 'approval.resolved')
        self.assertEqual('expired', resolved[-1].payload['decision'])

    def test_cancellation_resolves_each_pending_approval(self):
        run = self._run(self._conversation(), status='waiting_approval')
        approval = self.env['nextbot.approval'].sudo().create_pending(
            run=run,
            tool_name='prepare_update_record',
            arguments={
                'model': 'res.partner',
                'res_id': self.user.partner_id.id,
                'values': {'phone': 'never-written'},
            },
            ttl_minutes=15,
        )

        run.action_cancel()

        self.assertEqual('rejected', approval.state)
        resolved = run.event_ids.filtered(lambda event: event.event_type == 'approval.resolved')
        self.assertEqual({
            'approval_id': approval.id,
            'decision': 'rejected',
            'reason': 'cancelled',
        }, resolved[-1].payload)

    def test_runtime_reuses_preassigned_input_message(self):
        self._enable_ai()
        conversation = self._conversation()
        source = self._run(conversation, prompt='Regenerate this')
        input_message = source._post_user_message()
        regenerated = self._run(conversation, prompt=source.prompt)
        regenerated.sudo().input_message_id = input_message
        before = self.env['mail.message'].search_count([
            ('model', '=', 'discuss.channel'),
            ('res_id', '=', conversation.channel_id.id),
            ('author_id', '=', self.user.partner_id.id),
        ])
        with patch('nwos.addons.mail_bot.models.mail_bot.requests.post') as request_post:
            request_post.side_effect = [
                self._planner_response(),
                self._provider_response({'content': 'Regenerated.'}),
            ]
            regenerated._execute_runtime()
        after = self.env['mail.message'].search_count([
            ('model', '=', 'discuss.channel'),
            ('res_id', '=', conversation.channel_id.id),
            ('author_id', '=', self.user.partner_id.id),
        ])

        self.assertEqual(before, after)
        self.assertEqual(input_message, regenerated.input_message_id)

    def test_record_collection_artifact_has_json_download(self):
        run = self._run(self._conversation(), status='running')
        result = {'records': [{'id': 7, 'display_name': 'Example'}]}

        artifact = run._create_collection_artifact('search_records', result)

        self.assertEqual('record_collection', artifact.artifact_type)
        self.assertEqual('application/json', artifact.attachment_id.mimetype)
        self.assertEqual(result, json.loads(artifact.attachment_id.raw.decode('utf-8')))
        self.assertTrue(artifact._serialize()['download_url'])

    def test_builtin_read_result_has_typed_card(self):
        run = self._run(self._conversation(), status='running')
        card = self.env['nextbot.tool.registry'].with_user(self.user).result_card(
            'read_record',
            {'model': 'res.partner', 'res_id': self.user.partner_id.id},
            {'record': {'id': self.user.partner_id.id, 'display_name': self.user.name}},
            run,
        )

        self.assertEqual('record', card['type'])
        self.assertEqual('res.partner', card['res_model'])
        self.assertEqual(self.user.partner_id.id, card['res_id'])

    def test_bulk_create_approval_preview_identifies_the_action(self):
        preview = self.env['nextbot.tool.registry'].approval_preview(
            'prepare_create_records',
            {
                'model': 'res.partner',
                'records': [{'name': 'Preview partner'}],
            },
        )

        self.assertEqual('create', preview['action'])
        self.assertEqual('res.partner', preview['model'])
        self.assertEqual(1, preview['count'])

    def test_v2_read_tool_is_idempotent(self):
        run = self._run(self._conversation(), status='running')

        first = run._execute_tool_call('describe_model', {'model': 'res.partner'})
        second = run._execute_tool_call('describe_model', {'model': 'res.partner'})

        self.assertEqual(first, second)
        self.assertEqual(1, len(run.tool_execution_ids))
        self.assertEqual(1, run.tool_call_count)
        self.assertEqual('completed', run.tool_execution_ids.state)

    def test_v2_invalid_tool_arguments_are_repairable(self):
        run = self._run(self._conversation(), status='running')

        result = run._execute_tool_call('search_records', {
            'model': 'res.partner',
            'domain': {'name': 'name', 'operator': '=', 'value': 'Example'},
        })

        self.assertIn('error', result)
        self.assertEqual('running', run.status)
        self.assertIn('tool.failed', run.event_ids.mapped('event_type'))

    def test_v2_steering_supersedes_pending_approval(self):
        run = self._run(self._conversation(), status='waiting_approval')
        operation = self.env['nextbot.tool.execution'].sudo().create({
            'run_id': run.id,
            'tool_name': 'prepare_update_record',
            'arguments': {
                'model': 'res.partner',
                'res_id': self.user.partner_id.id,
                'values': {'phone': 'never-written'},
            },
            'access': 'write',
            'state': 'proposed',
            'idempotency_key': 'steer-test',
        })
        approval = self.env['nextbot.approval'].sudo().create_pending(
            run=run,
            tool_name='__batch__',
            arguments={'execution_ids': [operation.id]},
            ttl_minutes=15,
        )
        operation.sudo().approval_id = approval

        result = run.action_steer('Use the mobile field instead')

        self.assertEqual('queued', result['status'])
        self.assertTrue(run.replan_requested)
        self.assertEqual('superseded', approval.state)
        self.assertEqual('superseded', operation.state)

    def test_v2_expired_coordinator_lease_is_recovered(self):
        run = self._run(self._conversation(), status='running')
        run.sudo().write({
            'lease_token': 'dead-worker',
            'lease_expires_at': fields.Datetime.now() - timedelta(minutes=1),
        })

        recovered = self.env['nextbot.run']._cron_recover_expired_leases()

        self.assertGreaterEqual(recovered, 1)
        self.assertEqual('queued', run.status)
        self.assertIn('run.recovered', run.event_ids.mapped('event_type'))

    def test_v2_groups_write_operations_and_approval_is_idempotent(self):
        run = self._run(self._conversation(), status='running')
        memories = self.env['nextbot.memory'].with_user(self.user).create([
            {'content': 'First value before approval'},
            {'content': 'Second value before approval'},
        ])
        updates = zip(memories, ('First approved value', 'Second approved value'))
        for memory, content in updates:
            result = run._execute_tool_call('prepare_update_record', {
                'model': 'nextbot.memory',
                'res_id': memory.id,
                'values': {'content': content},
            })
            self.assertEqual('proposed', result['status'])

        approval = run._create_approval_batch().with_user(self.user)

        self.assertEqual('waiting_approval', run.status)
        self.assertEqual(2, len(approval.operation_ids))
        approval.action_approve()
        values_after_approval = tuple(memories.mapped('content'))
        approval.action_approve()

        self.assertEqual('approved', approval.state, approval.error_message)
        self.assertTrue(all(state == 'completed' for state in approval.operation_ids.mapped('state')))
        self.assertEqual(('First approved value', 'Second approved value'), values_after_approval)
        self.assertEqual(values_after_approval, tuple(memories.mapped('content')))
        self.assertEqual('verifying', run.status)
        verification_steps = run.step_ids.filtered(lambda step: step.step_type == 'verification')
        self.assertTrue(verification_steps)
        self.assertEqual({'queued'}, set(verification_steps.mapped('status')))

    def test_v2_budget_pause_can_continue_same_task(self):
        run = self._run(self._conversation(), status='running')
        run.sudo().iteration_count = 40

        self.assertTrue(run._budget_reached())
        run._pause_for_budget()
        resumed = run.action_continue()

        self.assertEqual('queued', resumed['status'])
        self.assertEqual(1, run.continuation_count)
        self.assertFalse(run.pause_reason)
        self.assertFalse(run._budget_reached(), 'Continue must grant another budget window.')
        self.assertIn('task.continued', run.event_ids.mapped('event_type'))

    def test_v2_scheduler_queues_independent_read_steps_in_parallel(self):
        run = self._run(self._conversation(), status='running')
        run.sudo().plan_revision = 1
        Step = self.env['nextbot.run.step'].sudo()
        first = Step.create({
            'run_id': run.id,
            'key': 'r1_first',
            'title': 'First read',
            'objective': 'Read one source',
            'sequence': 10,
        })
        second = Step.create({
            'run_id': run.id,
            'key': 'r1_second',
            'title': 'Second read',
            'objective': 'Read another source',
            'sequence': 20,
        })
        dependent = Step.create({
            'run_id': run.id,
            'key': 'r1_dependent',
            'title': 'Combine evidence',
            'objective': 'Use both sources',
            'sequence': 30,
            'dependency_ids': [Command.set([first.id, second.id])],
        })

        queued = run._schedule_ready_steps()

        self.assertEqual({first.id, second.id}, set(queued.ids))
        self.assertEqual('pending', dependent.status)
        first.sudo().status = 'completed'
        self.assertFalse(run._schedule_ready_steps().filtered(lambda step: step == dependent))
        second.sudo().status = 'completed'
        self.assertEqual(dependent, run._schedule_ready_steps())

    def test_v2_large_task_context_compacts_to_valid_json(self):
        run = self._run(self._conversation(), status='running')
        run.sudo().plan_revision = 1
        self.env['nextbot.run.step'].sudo().create({
            'run_id': run.id,
            'key': 'r1_large',
            'title': 'Large evidence step',
            'objective': 'Summarize a large result safely',
            'sequence': 10,
            'status': 'completed',
            'output_data': {'summary': 'evidence ' * 5000},
        })
        self.env['ir.config_parameter'].sudo().set_param(
            'nextbot_agent.context_token_budget', 4000,
        )

        context = run._task_state_context()
        decoded = json.loads(context)

        self.assertTrue(decoded['compacted'])
        self.assertLessEqual(len(context), 16000)
        self.assertNotIn('evidence evidence evidence', context)
