# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from nwos import Command
from nwos.exceptions import AccessError
from nwos.tests import TransactionCase, tagged


@tagged('nextbot_agent')
class TestNextBotMemory(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Memory User',
            'login': 'nextbot-memory-user',
            'email': 'nextbot-memory@example.com',
            'group_ids': [Command.set([cls.env.ref('base.group_user').id])],
        })
        cls.other_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Other Memory User',
            'login': 'nextbot-memory-other',
            'email': 'nextbot-memory-other@example.com',
            'group_ids': [Command.set([cls.env.ref('base.group_user').id])],
        })

    def _conversation(self, user=None):
        user = user or self.user
        return self.env['nextbot.conversation'].with_user(user)._create_for_user()

    def _run(self, status='completed', prompt='Hello', response='Hi'):
        conversation = self._conversation()
        return self.env['nextbot.run'].sudo().create({
            'conversation_id': conversation.id,
            'company_id': self.user.company_id.id,
            'allowed_company_ids': [Command.set(self.user.company_ids.ids)],
            'status': status,
            'prompt': prompt,
            'response_text': response,
            'completed_at': self.env.cr.now(),
        })

    def _enable_ai(self):
        parameters = self.env['ir.config_parameter'].sudo()
        parameters.set_param('base.ai.enabled', True)
        parameters.set_param('base.ai.provider', 'openai')
        parameters.set_param('base.ai.endpoint', 'https://api.openai.example/v1')
        parameters.set_param('base.ai.model', 'nextbot-test')
        parameters.set_param('base.ai.api_key', 'test-key')

    # ------------------------------------------------------------------
    # Org rules
    # ------------------------------------------------------------------

    def test_org_rules_injected_into_system_prompt(self):
        self.env['nextbot.org.rule'].sudo().create({
            'name': 'Validity',
            'content': 'Always mention that quotations are valid for 30 days.',
        })
        conversation = self._conversation()
        bot = self.env['mail.bot'].with_user(self.user)
        messages = bot._ai_prepare_messages(conversation.channel_id, {}, 'hello')

        self.assertIn('Organization rules', messages[0]['content'])
        self.assertIn('valid for 30 days', messages[0]['content'])

    def test_other_company_rule_not_injected(self):
        company = self.env['res.company'].sudo().create({'name': 'Elsewhere Co'})
        self.env['nextbot.org.rule'].sudo().create({
            'name': 'Elsewhere only',
            'content': 'Speak only Klingon.',
            'company_id': company.id,
        })
        conversation = self._conversation()
        bot = self.env['mail.bot'].with_user(self.user)
        messages = bot._ai_prepare_messages(conversation.channel_id, {}, 'hello')

        self.assertNotIn('Klingon', messages[0]['content'])

    def test_non_admin_cannot_write_org_rules(self):
        with self.assertRaises(AccessError):
            self.env['nextbot.org.rule'].with_user(self.user).create({
                'name': 'Nope',
                'content': 'Users cannot write rules.',
            })

    # ------------------------------------------------------------------
    # Language
    # ------------------------------------------------------------------

    def test_language_name_follows_user_lang(self):
        bot = self.env['mail.bot'].with_user(self.user)
        self.assertIn('English', bot._ai_user_language_name())

    def test_forced_language_overrides_user_lang(self):
        vi_lang = self.env['res.lang'].sudo().search(
            [('code', '=', 'vi_VN'), ('active', 'in', (True, False))], limit=1,
        )
        if not vi_lang:
            self.skipTest('vi_VN language data is unavailable.')
        vi_lang.active = True
        self.env['ir.config_parameter'].sudo().set_param(
            'nextbot_agent.force_response_lang', 'vi_VN',
        )
        bot = self.env['mail.bot'].with_user(self.user)
        self.assertTrue(bot._ai_is_vietnamese_language())
        self.assertIn('Vi', bot._ai_user_language_name())

    # ------------------------------------------------------------------
    # Memory model + tools
    # ------------------------------------------------------------------

    def test_memory_record_rule_isolates_users(self):
        memory = self.env['nextbot.memory'].with_user(self.user).create({
            'user_id': self.user.id,
            'content': 'Prefers totals in VND.',
        })
        other = self.env['nextbot.memory'].with_user(self.other_user)
        self.assertFalse(other.search([('id', '=', memory.id)]))
        with self.assertRaises(AccessError):
            other.browse(memory.id).read(['content'])

    def test_memory_injected_into_system_prompt(self):
        self.env['nextbot.memory'].with_user(self.user).create({
            'user_id': self.user.id,
            'content': 'Handles the Hanoi region.',
        })
        conversation = self._conversation()
        bot = self.env['mail.bot'].with_user(self.user)
        messages = bot._ai_prepare_messages(conversation.channel_id, {}, 'What is my region?')

        self.assertIn('Stored user memory', messages[0]['content'])
        self.assertIn('Hanoi', messages[0]['content'])

    def test_remember_tool_needs_no_approval_and_dedupes(self):
        registry = self.env['nextbot.tool.registry'].with_user(self.user)
        run = self._run(status='running')

        self.assertFalse(registry.requires_approval('remember'))
        result = registry.execute('remember', {'content': 'Prefers concise answers.'}, run)
        self.assertTrue(result['saved'])
        self.assertFalse(run.approval_ids)

        duplicate = registry.execute('remember', {'content': 'Prefers concise answers.'}, run)
        self.assertFalse(duplicate['saved'])
        self.assertEqual('duplicate', duplicate['reason'])

    def test_remember_tool_refuses_sensitive_and_rate_limits(self):
        registry = self.env['nextbot.tool.registry'].with_user(self.user)
        run = self._run(status='running')

        refused = registry.execute('remember', {'content': 'My password is hunter2'}, run)
        self.assertEqual('sensitive_content_refused', refused['reason'])

        for index in range(3):
            registry.execute('remember', {'content': 'Durable fact number %s.' % index}, run)
        limited = registry.execute('remember', {'content': 'One fact too many.'}, run)
        self.assertEqual('rate_limited', limited['reason'])

    def test_forget_tool_archives(self):
        self.env['nextbot.memory'].with_user(self.user).create({
            'user_id': self.user.id,
            'content': 'Prefers weekly pipeline reports.',
        })
        registry = self.env['nextbot.tool.registry'].with_user(self.user)
        run = self._run(status='running')

        result = registry.execute('forget', {'query': 'weekly pipeline reports'}, run)
        self.assertTrue(result['found'])
        remaining = self.env['nextbot.memory'].with_user(self.user).search([
            ('user_id', '=', self.user.id),
        ])
        self.assertFalse(remaining)
        archived = self.env['nextbot.memory'].with_user(self.user).with_context(
            active_test=False,
        ).search([('user_id', '=', self.user.id)])
        self.assertTrue(archived)
        self.assertFalse(archived.active)

    # ------------------------------------------------------------------
    # Auto-learning
    # ------------------------------------------------------------------

    def test_extraction_creates_memories_and_marks_done(self):
        self._enable_ai()
        run = self._run(prompt='I always want prices in VND', response='Noted!')

        def fake_completion(bot_self, settings, messages, **kwargs):
            return {'content': '["Prefers prices in VND"]'}

        with patch(
            'nwos.addons.mail_bot.models.mail_bot.MailBot._ai_chat_completion',
            new=fake_completion,
        ):
            self.env['nextbot.run']._cron_extract_memories()

        self.assertEqual('done', run.memory_status)
        memory = self.env['nextbot.memory'].sudo().search([('user_id', '=', self.user.id)])
        self.assertEqual(1, len(memory))
        self.assertEqual('learned', memory.source)
        self.assertIn('VND', memory.content)

    def test_extraction_failure_never_touches_run_status(self):
        self._enable_ai()
        run = self._run(prompt='hello', response='hi')

        def broken_completion(bot_self, settings, messages, **kwargs):
            raise ValueError('provider exploded')

        with patch(
            'nwos.addons.mail_bot.models.mail_bot.MailBot._ai_chat_completion',
            new=broken_completion,
        ):
            self.env['nextbot.run']._cron_extract_memories()

        self.assertEqual('completed', run.status)
        self.assertIn(run.memory_status, ('failed', 'skipped'))
        self.assertFalse(self.env['nextbot.memory'].sudo().search([('user_id', '=', self.user.id)]))

    def test_compaction_guards_against_garbage(self):
        self._enable_ai()
        Memory = self.env['nextbot.memory'].sudo()
        Memory.create([
            {'user_id': self.user.id, 'content': 'Fact number %s about workflows.' % index}
            for index in range(30)
        ])

        def garbage_completion(bot_self, settings, messages, **kwargs):
            return {'content': 'not json at all'}

        with patch(
            'nwos.addons.mail_bot.models.mail_bot.MailBot._ai_chat_completion',
            new=garbage_completion,
        ):
            self.assertFalse(Memory._compact_user(self.user))
        self.assertEqual(30, Memory.search_count([('user_id', '=', self.user.id)]))

    def test_compaction_merges(self):
        self._enable_ai()
        Memory = self.env['nextbot.memory'].sudo()
        Memory.create([
            {'user_id': self.user.id, 'content': 'Fact number %s about reports.' % index}
            for index in range(30)
        ])

        def merge_completion(bot_self, settings, messages, **kwargs):
            return {'content': '["Cares about reports", "Works with facts", "Merged memory", '
                               '"Fourth fact", "Fifth fact", "Sixth fact"]'}

        with patch(
            'nwos.addons.mail_bot.models.mail_bot.MailBot._ai_chat_completion',
            new=merge_completion,
        ):
            self.assertTrue(Memory._compact_user(self.user))
        active = Memory.search([('user_id', '=', self.user.id)])
        self.assertEqual(6, len(active))
        self.assertTrue(all(memory.source == 'learned' for memory in active))
