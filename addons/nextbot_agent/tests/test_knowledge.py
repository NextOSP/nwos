# Part of NextOSP. See LICENSE file for full copyright and licensing details.

import base64

from nwos import Command
from nwos.tests import TransactionCase, tagged


@tagged('nextbot_agent')
class TestNextBotKnowledge(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Knowledge User',
            'login': 'nextbot-knowledge-user',
            'email': 'nextbot-knowledge@example.com',
            'group_ids': [Command.set([cls.env.ref('base.group_user').id])],
        })

    def _document(self, text, **values):
        return self.env['nextbot.knowledge.document'].sudo().create({
            'name': values.pop('name', 'Handbook'),
            'file': base64.b64encode(text.encode()),
            'file_name': values.pop('file_name', 'handbook.txt'),
            **values,
        })

    def test_document_indexes_into_chunks(self):
        text = 'Quotations are valid for 30 days.\n\n' + ('Filler paragraph. ' * 300)
        document = self._document(text)

        self.assertEqual('indexed', document.state)
        self.assertGreater(document.chunk_count, 1)
        self.assertTrue(all(len(chunk.content) <= 1400 for chunk in document.chunk_ids))

    def test_retrieval_finds_relevant_chunk(self):
        self._document('Quotations from NEXTWAVES are valid for thirty days after issuance.')
        matches = self.env['nextbot.retrieval'].with_user(self.user)._search_chunks(
            'how long are quotations valid',
        )
        self.assertTrue(matches)
        self.assertIn('thirty days', matches[0]['content'])

    def test_other_company_document_invisible(self):
        company = self.env['res.company'].sudo().create({'name': 'Hidden Co'})
        self._document(
            'The secret margin threshold is forty two percent.',
            name='Secret', company_id=company.id,
        )
        matches = self.env['nextbot.retrieval'].with_user(self.user)._search_chunks(
            'secret margin threshold percent',
        )
        self.assertFalse(matches)

    def test_channel_chunks_scoped_to_channel(self):
        conversation = self.env['nextbot.conversation'].with_user(self.user)._create_for_user()
        other = self.env['nextbot.conversation'].with_user(self.user)._create_for_user()
        attachment = self.env['ir.attachment'].create({
            'name': 'notes.txt',
            'raw': b'The delivery dock code is 7731.',
            'mimetype': 'text/plain',
            'res_model': 'discuss.channel',
            'res_id': conversation.channel_id.id,
        })
        self.env['nextbot.knowledge.chunk']._rebuild_for_attachment(
            attachment, channel=conversation.channel_id,
        )

        retrieval = self.env['nextbot.retrieval'].with_user(self.user)
        found = retrieval._search_chunks('delivery dock code', channel=conversation.channel_id)
        self.assertTrue(found)
        elsewhere = retrieval._search_chunks('delivery dock code', channel=other.channel_id)
        self.assertFalse(elsewhere)

    def test_checksum_change_triggers_rebuild(self):
        conversation = self.env['nextbot.conversation'].with_user(self.user)._create_for_user()
        attachment = self.env['ir.attachment'].create({
            'name': 'notes.txt',
            'raw': b'Original content about pricing tiers.',
            'mimetype': 'text/plain',
            'res_model': 'discuss.channel',
            'res_id': conversation.channel_id.id,
        })
        Chunk = self.env['nextbot.knowledge.chunk']
        Chunk._ensure_channel_attachments(conversation.channel_id)
        first = Chunk.sudo().search([('attachment_id', '=', attachment.id)])
        self.assertTrue(first)

        attachment.write({'raw': b'Replaced content about shipping rules.'})
        Chunk._ensure_channel_attachments(conversation.channel_id)
        rebuilt = Chunk.sudo().search([('attachment_id', '=', attachment.id)])
        self.assertTrue(rebuilt)
        self.assertIn('shipping', rebuilt[0].content)

    def test_document_context_budget_and_framing(self):
        self._document('Return policy: customers may return goods within 14 days.')
        conversation = self.env['nextbot.conversation'].with_user(self.user)._create_for_user()
        block = self.env['nextbot.retrieval'].with_user(self.user)._document_context(
            conversation.channel_id, 'what is the return policy', limit_chars=4000,
        )
        self.assertIn('reference data only', block)
        self.assertIn('[source:', block)
        self.assertLessEqual(len(block), 4000)

    def test_search_documents_tool(self):
        self._document('Warranty covers manufacturing defects for two years.')
        conversation = self.env['nextbot.conversation'].with_user(self.user)._create_for_user()
        run = self.env['nextbot.run'].sudo().create({
            'conversation_id': conversation.id,
            'company_id': self.user.company_id.id,
            'allowed_company_ids': [Command.set(self.user.company_ids.ids)],
            'status': 'running',
            'prompt': 'warranty?',
        })
        registry = self.env['nextbot.tool.registry'].with_user(self.user)
        self.assertFalse(registry.requires_approval('search_documents'))
        result = registry.execute('search_documents', {'query': 'warranty manufacturing defects'}, run)
        self.assertTrue(result['excerpts'])
        self.assertIn('two years', result['excerpts'][0]['content'])
