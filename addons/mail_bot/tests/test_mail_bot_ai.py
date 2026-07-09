# Part of NextOSP. See LICENSE file for full copyright and licensing details.

import base64
import json
from unittest.mock import patch

from markupsafe import Markup

from nwos.tests import TransactionCase, tagged
from nwos.tools import html2plaintext


@tagged('mail_bot_ai')
class TestMailBotAI(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not cls.env['res.lang'].search([('code', '=', 'vi_VN'), ('active', '=', True)], limit=1):
            cls.env['res.lang']._activate_lang('vi_VN')
        cls.user = cls.env.ref('base.user_admin')
        cls.partner = cls.user.partner_id
        cls.nwosbot_partner = cls.env.ref('base.partner_root')
        cls.channel = cls.env['discuss.channel'].with_user(cls.user)._get_or_create_chat([
            cls.nwosbot_partner.id,
            cls.partner.id,
        ])
        cls.user.sudo().odoobot_state = 'disabled'

    def setUp(self):
        super().setUp()
        self.env['ir.config_parameter'].sudo().search([
            '|',
            ('key', 'like', 'mail_bot.ai.pending_action.%'),
            ('key', 'like', 'mail_bot.ai.last_record.%'),
        ]).unlink()
        self.user.sudo().lang = 'vi_VN'
        self._enable_ai()

    def _enable_ai(self):
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('base.ai.enabled', True)
        ICP.set_param('base.ai.provider', 'openai')
        ICP.set_param('base.ai.endpoint', 'https://api.openai.example/v1')
        ICP.set_param('base.ai.model', 'gpt-test')
        ICP.set_param('base.ai.model.intelligent', 'gpt-test')
        ICP.set_param('base.ai.api_key', 'test-key')

    def _disable_ai(self):
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('base.ai.enabled', False)
        ICP.set_param('base.ai.api_key', False)

    def _mock_ai_response(self, content=None, tool_calls=None):
        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                message = {}
                if content is not None:
                    message['content'] = content
                if tool_calls is not None:
                    message['tool_calls'] = tool_calls
                return {'choices': [{'message': message}]}

        return Response()

    def _post_as_employee(self, body, **kwargs):
        return self.channel.with_user(self.user).with_context(lang=self.user.lang or 'en_US').message_post(
            body=Markup('<p>%s</p>') % body,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
            **kwargs,
        )

    def _create_partner(self, values):
        values = dict(values)
        if 'autopost_bills' in self.env['res.partner']._fields:
            values.setdefault('autopost_bills', 'ask')
        return self.env['res.partner'].create(values)

    def _last_bot_body(self):
        message = self._last_bot_message()
        return html2plaintext(message.body)

    def _last_bot_message(self):
        message = self.env['mail.message'].search([
            ('model', '=', 'discuss.channel'),
            ('res_id', '=', self.channel.id),
            ('author_id', '=', self.nwosbot_partner.id),
        ], order='id desc', limit=1)
        return message

    def test_nextbot_uses_shared_ai_settings(self):
        with patch('nwos.addons.mail_bot.models.mail_bot.requests.post') as mock_post:
            mock_post.return_value = self._mock_ai_response(content='Hello from configured AI.')

            self._post_as_employee('Hi NextBot')

        self.assertEqual('https://api.openai.example/v1/chat/completions', mock_post.call_args.args[0])
        self.assertEqual('Bearer test-key', mock_post.call_args.kwargs['headers']['Authorization'])
        self.assertEqual('gpt-test', mock_post.call_args.kwargs['json']['model'])
        self.assertIn('Hello from configured AI.', self._last_bot_body())
        self.assertEqual(1, mock_post.call_count, 'Bot-authored messages must not recursively call AI.')

    def test_nextbot_strips_markdown_from_ai_text(self):
        with patch('nwos.addons.mail_bot.models.mail_bot.requests.post') as mock_post:
            mock_post.return_value = self._mock_ai_response(content=(
                'Doanh thu đã xác nhận là **$400,00**.\n'
                '- **S00009** - Anh Hưng: **$375,00**\n'
                'Lưu ý: Báo giá **S00015** vẫn là **Quotation**.'
            ))

            self._post_as_employee('cho tôi tóm tắt nhanh')

        body = self._last_bot_body()
        self.assertIn('$400,00', body)
        self.assertIn('S00009', body)
        self.assertIn('S00015', body)
        self.assertNotIn('**', body)

    def test_nextbot_sends_image_attachments_to_ai(self):
        image_raw = b'\x89PNG\r\n\x1a\nnextbot-test-image'
        attachment = self.env['ir.attachment'].create({
            'name': 'screenshot.png',
            'raw': image_raw,
            'mimetype': 'image/png',
            'res_model': 'discuss.channel',
            'res_id': self.channel.id,
        })

        with patch('nwos.addons.mail_bot.models.mail_bot.requests.post') as mock_post:
            mock_post.return_value = self._mock_ai_response(content='Có 4 mục trong ảnh.')

            self._post_as_employee(
                'đây là gì có bao nhiêu mục',
                attachment_ids=[attachment.id],
            )

        payload = mock_post.call_args.kwargs['json']
        user_content = payload['messages'][1]['content']
        self.assertIsInstance(user_content, list)
        self.assertEqual('text', user_content[0]['type'])
        self.assertIn('User message: đây là gì có bao nhiêu mục', user_content[0]['text'])
        self.assertIn('screenshot.png', user_content[0]['text'])
        self.assertEqual('image_url', user_content[1]['type'])
        self.assertEqual('auto', user_content[1]['image_url']['detail'])
        self.assertEqual(
            'data:image/png;base64,%s' % base64.b64encode(image_raw).decode('ascii'),
            user_content[1]['image_url']['url'],
        )
        self.assertIn('Có 4 mục trong ảnh.', self._last_bot_body())

    def test_nextbot_reports_missing_ai_settings(self):
        self._disable_ai()

        with patch('nwos.addons.mail_bot.models.mail_bot.requests.post') as mock_post:
            self._post_as_employee('Hi NextBot')

        self.assertFalse(mock_post.called)
        self.assertIn('AI is not enabled', self._last_bot_body())

    def test_write_tool_requires_confirmation(self):
        partner = self.partner
        tool_calls = [{
            'id': 'call_comment',
            'type': 'function',
            'function': {
                'name': 'prepare_post_comment',
                'arguments': json.dumps({
                    'model': 'res.partner',
                    'res_id': partner.id,
                    'body': 'Prepared by NextBot',
                }),
            },
        }]

        with patch('nwos.addons.mail_bot.models.mail_bot.requests.post') as mock_post:
            mock_post.return_value = self._mock_ai_response(tool_calls=tool_calls)

            self._post_as_employee('Post a note on the partner')

        pending_message = self._last_bot_message()
        self.assertIn('Chuẩn bị ghi chú', html2plaintext(pending_message.body))
        self.assertIn('o_nextbot_action_card', pending_message.body)
        self.assertFalse(partner.message_ids.filtered(lambda message: 'Prepared by NextBot' in html2plaintext(message.body)))

        self._post_as_employee('confirm')

        self.assertTrue(partner.message_ids.filtered(lambda message: 'Prepared by NextBot' in html2plaintext(message.body)))
        result_message = self._last_bot_message()
        self.assertIn('Đã ghi chú', html2plaintext(result_message.body))
        self.assertIn('o_nextbot_action_card', result_message.body)

    def test_update_tool_uses_vietnamese_card(self):
        partner = self.partner
        tool_calls = [{
            'id': 'call_update',
            'type': 'function',
            'function': {
                'name': 'prepare_update_record',
                'arguments': json.dumps({
                    'model': 'res.partner',
                    'res_id': partner.id,
                    'values': {'phone': '0869630830'},
                }),
            },
        }]

        with patch('nwos.addons.mail_bot.models.mail_bot.requests.post') as mock_post:
            mock_post.return_value = self._mock_ai_response(tool_calls=tool_calls)

            self._post_as_employee('cập nhật số điện thoại anh Hưng 0869630830')

        pending_message = self._last_bot_message()
        pending_body = html2plaintext(pending_message.body)
        self.assertIn('Chuẩn bị cập nhật khách hàng', pending_body)
        self.assertIn('0869630830', pending_body)
        self.assertIn('o_nextbot_action_card', pending_message.body)
        self.assertIn('o_nextbot_record_modal', pending_message.body)
        self.assertNotIn('I can update', pending_body)

        self._post_as_employee('confirm')

        partner.invalidate_recordset(['phone'])
        self.assertEqual('0869630830', partner.phone)
        result_message = self._last_bot_message()
        result_body = html2plaintext(result_message.body)
        self.assertIn('Đã cập nhật khách hàng', result_body)
        self.assertIn('o_nextbot_action_card', result_message.body)

    def test_followup_source_updates_last_created_customer_tag(self):
        partner = self.partner
        self.env['mail.bot']._ai_store_last_record(self.channel, partner)

        with patch('nwos.addons.mail_bot.models.mail_bot.requests.post') as mock_post:
            self._post_as_employee('them la source Facebook B2B')

        self.assertFalse(mock_post.called)
        pending_message = self._last_bot_message()
        pending_body = html2plaintext(pending_message.body)
        self.assertIn('Chuẩn bị gắn nguồn khách hàng', pending_body)
        self.assertIn('Facebook B2B', pending_body)
        self.assertIn('o_nextbot_action_card', pending_message.body)

        with patch('nwos.addons.mail_bot.models.mail_bot.requests.post') as mock_post:
            self._post_as_employee('ok')

        self.assertFalse(mock_post.called)
        partner.invalidate_recordset(['category_id'])
        self.assertIn('Source: Facebook B2B', partner.category_id.mapped('name'))
        result_message = self._last_bot_message()
        self.assertIn('Đã gắn nguồn khách hàng', html2plaintext(result_message.body))

    def test_followup_source_reasks_customer_and_continues(self):
        partner = self.partner

        with patch('nwos.addons.mail_bot.models.mail_bot.requests.post') as mock_post:
            self._post_as_employee('them la source Facebook B2B')

        self.assertFalse(mock_post.called)
        missing_message = self._last_bot_message()
        missing_body = html2plaintext(missing_message.body)
        self.assertIn('Nguồn này cho khách hàng nào?', missing_body)
        self.assertIn('Facebook B2B', missing_body)
        self.assertIn('o_nextbot_source_clarify_card', missing_message.body)

        with patch('nwos.addons.mail_bot.models.mail_bot.requests.post') as mock_post:
            self._post_as_employee(partner.display_name)

        self.assertFalse(mock_post.called)
        pending_message = self._last_bot_message()
        pending_body = html2plaintext(pending_message.body)
        self.assertIn('Chuẩn bị gắn nguồn khách hàng', pending_body)
        self.assertIn('Facebook B2B', pending_body)

        with patch('nwos.addons.mail_bot.models.mail_bot.requests.post') as mock_post:
            self._post_as_employee('ok')

        self.assertFalse(mock_post.called)
        partner.invalidate_recordset(['category_id'])
        self.assertIn('Source: Facebook B2B', partner.category_id.mapped('name'))

    def test_followup_source_recovers_customer_reply_from_recent_history(self):
        partner = self.partner
        self._post_as_employee('them la source Facebook B2B')
        self.channel.sudo().message_post(
            author_id=self.nwosbot_partner.id,
            body=Markup('<p>Mình chưa biết cần thêm nguồn cho khách hàng nào. Hãy nói rõ tên khách hàng.</p>'),
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )

        with patch('nwos.addons.mail_bot.models.mail_bot.requests.post') as mock_post:
            self._post_as_employee(partner.display_name)

        self.assertFalse(mock_post.called)
        pending_body = html2plaintext(self._last_bot_message().body)
        self.assertIn('Chuẩn bị gắn nguồn khách hàng', pending_body)
        self.assertIn('Facebook B2B', pending_body)

    def test_clear_command_removes_pending_action_without_ai(self):
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param(self.env['mail.bot']._ai_pending_action_key(self.channel), json.dumps({
            'tool': 'prepare_create_record',
            'arguments': {'model': 'res.partner', 'values': {'name': 'Pending'}},
        }))

        with patch('nwos.addons.mail_bot.models.mail_bot.requests.post') as mock_post:
            self._post_as_employee('clear')

        self.assertFalse(mock_post.called)
        self.assertFalse(ICP.get_param(self.env['mail.bot']._ai_pending_action_key(self.channel)))
        self.assertIn('Đã xóa lệnh NextBot', self._last_bot_body())

    def test_slash_clear_command_removes_pending_action(self):
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param(self.env['mail.bot']._ai_pending_action_key(self.channel), json.dumps({
            'tool': 'prepare_create_record',
            'arguments': {'model': 'res.partner', 'values': {'name': 'Pending'}},
        }))

        self.channel.with_user(self.user).execute_command_clear(body='/clear')

        self.assertFalse(ICP.get_param(self.env['mail.bot']._ai_pending_action_key(self.channel)))
        self.assertIn('Đã xóa lệnh NextBot', self._last_bot_body())

    def test_vietnamese_quotation_flow_uses_ai_tool_and_cards(self):
        if 'sale.order' not in self.env:
            self.skipTest('Sales is not installed.')

        product = self.env['product.product'].create({
            'name': 'Mẫu',
            'list_price': 25,
            'sale_ok': True,
        })
        tool_calls = [{
            'id': 'call_quote',
            'type': 'function',
            'function': {
                'name': 'prepare_create_sale_quotation',
                'arguments': json.dumps({
                    'partner_name': 'Anh Hưng',
                    'product_query': 'mau',
                    'quantity': 15,
                }),
            },
        }]

        with patch('nwos.addons.mail_bot.models.mail_bot.requests.post') as mock_post:
            mock_post.return_value = self._mock_ai_response(tool_calls=tool_calls)

            self._post_as_employee('tạo quotation mẫu 15 cái cho anh Hưng')

        self.assertTrue(mock_post.called)
        self.assertEqual(
            'prepare_create_sale_quotation',
            mock_post.call_args.kwargs['json']['tool_choice']['function']['name'],
        )
        pending_message = self._last_bot_message()
        self.assertIn('Chuẩn bị báo giá', html2plaintext(pending_message.body))
        self.assertIn('o_nextbot_quotation_card', pending_message.body)

        with patch('nwos.addons.mail_bot.models.mail_bot.requests.post') as mock_post:
            self._post_as_employee('ok làm đi')

        self.assertFalse(mock_post.called)
        order = self.env['sale.order'].search([
            ('partner_id.name', '=', 'Anh Hưng'),
            ('order_line.product_id', '=', product.id),
        ], order='id desc', limit=1)
        self.assertTrue(order)
        self.assertEqual(15, order.order_line.product_uom_qty)

        result_message = self._last_bot_message()
        self.assertIn('Đã tạo báo giá', html2plaintext(result_message.body))
        self.assertIn('Mở báo giá', html2plaintext(result_message.body))
        self.assertIn('o_nextbot_record_modal', result_message.body)

    def test_vietnamese_quotation_flow_supports_multiple_items(self):
        if 'sale.order' not in self.env:
            self.skipTest('Sales is not installed.')

        product_a = self.env['product.product'].create({
            'name': 'Mẫu A',
            'list_price': 25,
            'sale_ok': True,
        })
        product_b = self.env['product.product'].create({
            'name': 'Mẫu B',
            'list_price': 10,
            'sale_ok': True,
        })
        tool_calls = [{
            'id': 'call_quote',
            'type': 'function',
            'function': {
                'name': 'prepare_create_sale_quotation',
                'arguments': json.dumps({
                    'partner_name': 'Anh Hưng',
                    'order_lines': [
                        {'product_query': 'Mẫu A', 'quantity': 15},
                        {'product_query': 'Mẫu B', 'quantity': 20},
                    ],
                }),
            },
        }]

        with patch('nwos.addons.mail_bot.models.mail_bot.requests.post') as mock_post:
            mock_post.return_value = self._mock_ai_response(tool_calls=tool_calls)

            self._post_as_employee('tạo quotation mẫu A 15 cái và mẫu B 20 cái cho anh Hưng')

        pending_message = self._last_bot_message()
        pending_body = html2plaintext(pending_message.body)
        self.assertIn('Chuẩn bị báo giá', pending_body)
        self.assertIn('Mẫu A', pending_body)
        self.assertIn('Mẫu B', pending_body)
        self.assertIn('15 ×', pending_body)
        self.assertIn('20 ×', pending_body)

        with patch('nwos.addons.mail_bot.models.mail_bot.requests.post') as mock_post:
            self._post_as_employee('ok làm đi')

        self.assertFalse(mock_post.called)
        order = self.env['sale.order'].search([
            ('partner_id.name', '=', 'Anh Hưng'),
            ('order_line.product_id', 'in', [product_a.id, product_b.id]),
        ], order='id desc', limit=1)
        self.assertTrue(order)
        lines_by_product = {line.product_id.id: line for line in order.order_line.filtered(lambda line: not line.display_type)}
        self.assertEqual({product_a.id, product_b.id}, set(lines_by_product))
        self.assertEqual(15, lines_by_product[product_a.id].product_uom_qty)
        self.assertEqual(20, lines_by_product[product_b.id].product_uom_qty)
        result_body = html2plaintext(self._last_bot_message().body)
        self.assertIn('Đã tạo báo giá', result_body)
        self.assertIn('Mẫu A', result_body)
        self.assertIn('Mẫu B', result_body)

    def test_vietnamese_quotation_customer_count_is_local_card(self):
        if 'sale.order' not in self.env:
            self.skipTest('Sales is not installed.')

        product = self.env['product.product'].create({
            'name': 'Mẫu đếm báo giá',
            'list_price': 25,
            'sale_ok': True,
        })
        partners = [
            self._create_partner({'name': 'Anh Hưng'}),
            self._create_partner({'name': 'TNHH'}),
            self._create_partner({'name': 'Administrator'}),
        ]
        for partner, quantity in [
            (partners[0], 15),
            (partners[1], 1),
            (partners[1], 2),
            (partners[2], 3),
        ]:
            self.env['sale.order'].create({
                'partner_id': partner.id,
                'user_id': self.user.id,
                'order_line': [(
                    0,
                    0,
                    {
                        'product_id': product.id,
                        'product_uom_qty': quantity,
                        'price_unit': 25,
                    },
                )],
            })

        with patch('nwos.addons.mail_bot.models.mail_bot.requests.post') as mock_post:
            self._post_as_employee('báo giá nay có bao nhiêu khách?')

        self.assertFalse(mock_post.called)
        message = self._last_bot_message()
        body = html2plaintext(message.body)
        self.assertIn('Báo giá hôm nay', body)
        self.assertIn('3 khách', body)
        self.assertIn('4 báo giá', body)
        self.assertIn('Anh Hưng', body)
        self.assertIn('TNHH', body)
        self.assertIn('Administrator', body)
        self.assertNotIn('**', body)
        self.assertIn('o_nextbot_quotation_summary_card', message.body)

    def test_vietnamese_quotation_product_search_is_local_card(self):
        if 'sale.order' not in self.env:
            self.skipTest('Sales is not installed.')

        partner = self._create_partner({'name': 'Emily'})
        product = self.env['product.product'].create({
            'name': 'Đồ nội thất',
            'list_price': 120,
            'sale_ok': True,
        })
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'user_id': self.user.id,
            'order_line': [(
                0,
                0,
                {
                    'product_id': product.id,
                    'product_uom_qty': 15,
                    'price_unit': 120,
                },
            )],
        })

        with patch('nwos.addons.mail_bot.models.mail_bot.requests.post') as mock_post:
            self._post_as_employee('tìm báo giá có chứa Đồ nội thất')

        self.assertFalse(mock_post.called)
        message = self._last_bot_message()
        body = html2plaintext(message.body)
        self.assertIn('Báo giá phù hợp', body)
        self.assertIn(order.name, body)
        self.assertIn('Emily', body)
        self.assertIn('Đồ nội thất', body)
        self.assertIn('15 ×', body)
        self.assertNotIn('I could not produce an answer from the AI provider.', body)
        self.assertIn('o_nextbot_quotation_search_card', message.body)
        self.assertIn('o_nextbot_record_modal', message.body)

    def test_vietnamese_quotation_missing_customer_reasks_and_continues(self):
        if 'sale.order' not in self.env:
            self.skipTest('Sales is not installed.')

        partner = self._create_partner({'name': 'Anh Hưng'})
        product = self.env['product.product'].create({
            'name': 'Mẫu 15',
            'list_price': 25,
            'sale_ok': True,
        })
        tool_calls = [{
            'id': 'call_quote',
            'type': 'function',
            'function': {
                'name': 'prepare_create_sale_quotation',
                'arguments': json.dumps({
                    'product_query': 'Mẫu 15',
                    'quantity': 1000,
                }),
            },
        }]

        with patch('nwos.addons.mail_bot.models.mail_bot.requests.post') as mock_post:
            mock_post.return_value = self._mock_ai_response(tool_calls=tool_calls)

            self._post_as_employee('tạo báo giá mẫu 15, 1000 cái')

        self.assertTrue(mock_post.called)
        missing_message = self._last_bot_message()
        missing_body = html2plaintext(missing_message.body)
        self.assertIn('Báo giá này cho khách hàng nào?', missing_body)
        self.assertIn('Mẫu 15', missing_body)
        self.assertIn('1000', missing_body)
        self.assertNotIn('AI chưa xác định', missing_body)
        self.assertIn('o_nextbot_quotation_clarify_card', missing_message.body)
        self.assertIn('o_nextbot_suggestion', missing_message.body)

        with patch('nwos.addons.mail_bot.models.mail_bot.requests.post') as mock_post:
            self._post_as_employee('confirm')

        self.assertFalse(mock_post.called)
        self.assertIn('Báo giá này cho khách hàng nào?', self._last_bot_body())

        with patch('nwos.addons.mail_bot.models.mail_bot.requests.post') as mock_post:
            self._post_as_employee('cho Anh Hưng')

        self.assertFalse(mock_post.called)
        pending_message = self._last_bot_message()
        self.assertIn('Chuẩn bị báo giá', html2plaintext(pending_message.body))
        self.assertIn('o_nextbot_quotation_card', pending_message.body)

        self._post_as_employee('ok làm đi')

        order = self.env['sale.order'].search([
            ('partner_id', '=', partner.id),
            ('order_line.product_id', '=', product.id),
        ], order='id desc', limit=1)
        self.assertTrue(order)
        self.assertEqual(1000, order.order_line.product_uom_qty)
        self.assertIn('Đã tạo báo giá', self._last_bot_body())

    def test_vietnamese_quotation_missing_product_suggests_products(self):
        if 'sale.order' not in self.env:
            self.skipTest('Sales is not installed.')

        partner = self._create_partner({'name': 'Anh Hưng'})
        product = self.env['product.product'].create({
            'name': 'Mẫu 15',
            'list_price': 25,
            'sale_ok': True,
        })
        self.env['product.product'].create({
            'name': 'Mẫu khác',
            'list_price': 10,
            'sale_ok': True,
        })
        tool_calls = [{
            'id': 'call_quote',
            'type': 'function',
            'function': {
                'name': 'prepare_create_sale_quotation',
                'arguments': json.dumps({
                    'partner_name': 'Anh Hưng',
                    'product_query': 'mẫu 15 mô tả tem mẫu 15',
                    'quantity': 1000,
                }),
            },
        }]

        with patch('nwos.addons.mail_bot.models.mail_bot.requests.post') as mock_post:
            mock_post.return_value = self._mock_ai_response(tool_calls=tool_calls)

            self._post_as_employee('tạo báo giá mẫu 15 mô tả tem mẫu 15, 1000 cái')

        self.assertTrue(mock_post.called)
        missing_message = self._last_bot_message()
        missing_body = html2plaintext(missing_message.body)
        self.assertIn('Bạn muốn dùng sản phẩm nào cho báo giá?', missing_body)
        self.assertIn('Anh Hưng', missing_body)
        self.assertIn('1000', missing_body)
        self.assertIn('Mẫu 15', missing_body)
        self.assertIn('o_nextbot_suggestion', missing_message.body)
        self.assertIn('sản phẩm Mẫu 15', missing_message.body)

        with patch('nwos.addons.mail_bot.models.mail_bot.requests.post') as mock_post:
            self._post_as_employee('sản phẩm Mẫu 15')

        self.assertFalse(mock_post.called)
        pending_message = self._last_bot_message()
        self.assertIn('Chuẩn bị báo giá', html2plaintext(pending_message.body))
        self.assertIn('o_nextbot_quotation_card', pending_message.body)

        self._post_as_employee('ok làm đi')

        order = self.env['sale.order'].search([
            ('partner_id', '=', partner.id),
            ('order_line.product_id', '=', product.id),
        ], order='id desc', limit=1)
        self.assertTrue(order)
        self.assertEqual(1000, order.order_line.product_uom_qty)

    def test_english_user_gets_english_quotation_clarification_card(self):
        self.user.sudo().lang = 'en_US'
        bot = self.env['mail.bot'].with_user(self.user).with_context(lang='en_US')
        card = bot._ai_sale_quotation_clarification_card({
            'missing': ['product'],
            'partner_name': 'Emily',
            'order_lines': [{'product_query': 'Fees', 'quantity': 15}],
        })
        body = html2plaintext(card)

        self.assertIn('Which product should I use for this quotation?', body)
        self.assertIn('Reply with the product name or internal reference.', body)
        self.assertIn('Customer', body)
        self.assertIn('Line 1', body)
        self.assertIn('Emily', body)
        self.assertIn('Fees × 15', body)
        self.assertNotIn('Bạn muốn dùng sản phẩm nào', body)

        messages = bot._ai_prepare_messages(self.channel, {}, 'Make Quotation Emily for Fees 15 pcs at $12.3')
        self.assertIn('ERP UI language is English', messages[0]['content'])

    def test_vietnamese_sales_report_is_local_card(self):
        if 'sale.order' not in self.env:
            self.skipTest('Sales is not installed.')

        partner = self._create_partner({'name': 'Anh Hưng'})
        product = self.env['product.product'].create({
            'name': 'Mẫu báo cáo',
            'list_price': 25,
            'sale_ok': True,
        })
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'user_id': self.user.id,
            'order_line': [(
                0,
                0,
                {
                    'product_id': product.id,
                    'product_uom_qty': 15,
                    'price_unit': 25,
                },
            )],
        })
        order.action_confirm()

        with patch('nwos.addons.mail_bot.models.mail_bot.requests.post') as mock_post:
            self._post_as_employee('nay doanh số tôi bao nhiêu')

        self.assertFalse(mock_post.called)
        message = self._last_bot_message()
        body = html2plaintext(message.body)
        self.assertIn('Báo cáo doanh số hôm nay', body)
        self.assertIn(order.name, body)
        self.assertIn('%g' % order.amount_total, body)
        self.assertNotIn('**', body)
        self.assertIn('o_nextbot_sales_report_card', message.body)

    def test_vietnamese_revenue_status_is_local_card(self):
        if 'sale.order' not in self.env:
            self.skipTest('Sales is not installed.')

        partner = self._create_partner({'name': 'Anh Hưng'})
        product = self.env['product.product'].create({
            'name': 'Mẫu doanh thu',
            'list_price': 25,
            'sale_ok': True,
        })
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'user_id': self.user.id,
            'order_line': [(
                0,
                0,
                {
                    'product_id': product.id,
                    'product_uom_qty': 15,
                    'price_unit': 25,
                },
            )],
        })
        order.action_confirm()

        with patch('nwos.addons.mail_bot.models.mail_bot.requests.post') as mock_post:
            self._post_as_employee('Doanh thu tôi thế nào')

        self.assertFalse(mock_post.called)
        message = self._last_bot_message()
        body = html2plaintext(message.body)
        self.assertIn('Báo cáo doanh số tháng này', body)
        self.assertIn(order.name, body)
        self.assertNotIn('**', body)
        self.assertIn('o_nextbot_sales_report_card', message.body)

    def test_sales_report_reasks_when_period_is_missing(self):
        with patch('nwos.addons.mail_bot.models.mail_bot.requests.post') as mock_post:
            self._post_as_employee('tạo báo cáo doanh số')

        self.assertFalse(mock_post.called)
        message = self._last_bot_message()
        body = html2plaintext(message.body)
        self.assertIn('Bạn muốn báo cáo nào?', body)
        self.assertIn('Hôm nay của tôi', body)
        self.assertIn('Xuất file hôm nay', body)
        self.assertIn('o_nextbot_clarify_card', message.body)
        self.assertIn('o_nextbot_suggestion', message.body)
        self.assertIn('#nextbot-message=', message.body)

    def test_sales_report_export_prepares_text_attachment(self):
        if 'sale.order' not in self.env:
            self.skipTest('Sales is not installed.')

        partner = self._create_partner({'name': 'Anh Hưng'})
        product = self.env['product.product'].create({
            'name': 'Mẫu file báo cáo',
            'list_price': 25,
            'sale_ok': True,
        })
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'user_id': self.user.id,
            'order_line': [(
                0,
                0,
                {
                    'product_id': product.id,
                    'product_uom_qty': 15,
                    'price_unit': 25,
                },
            )],
        })
        order.action_confirm()

        with patch('nwos.addons.mail_bot.models.mail_bot.requests.post') as mock_post:
            self._post_as_employee('xuất báo cáo doanh số hôm nay')

        self.assertFalse(mock_post.called)
        pending_message = self._last_bot_message()
        pending_body = html2plaintext(pending_message.body)
        self.assertIn('Chuẩn bị đính kèm tệp', pending_body)
        self.assertIn('sales_report_today.txt', pending_body)
        self.assertIn('o_nextbot_action_card', pending_message.body)

        self._post_as_employee('confirm')

        attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'discuss.channel'),
            ('res_id', '=', self.channel.id),
            ('name', '=', 'sales_report_today.txt'),
        ], order='id desc', limit=1)
        self.assertTrue(attachment)
        self.assertIn(order.name, attachment.raw.decode())
        result_message = self._last_bot_message()
        self.assertIn('Đã đính kèm tệp', html2plaintext(result_message.body))
        self.assertIn('/web/content/%s?download=true' % attachment.id, result_message.body)
