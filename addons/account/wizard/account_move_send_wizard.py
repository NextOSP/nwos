import json
import re

import requests

from nwos import _, api, fields, models
from nwos.exceptions import UserError
from nwos.tools import format_amount, format_date, html2plaintext, plaintext2html
from nwos.tools.ai import get_ai_settings
from nwos.tools.misc import get_lang
from nwos.addons.mail.tools.parser import parse_res_ids
from nwos.addons.mail.wizard.mail_compose_message import _reopen


AI_EMAIL_CONTEXT_MESSAGE_LIMIT = 8
AI_EMAIL_BODY_LIMIT = 12000


class AccountMoveSendWizard(models.TransientModel):
    """Wizard that handles the sending a single invoice."""
    _name = 'account.move.send.wizard'
    _inherit = ['account.move.send', 'mail.composer.mixin']
    _description = "Account Move Send Wizard"

    move_id = fields.Many2one(comodel_name='account.move', required=True)
    company_id = fields.Many2one(comodel_name='res.company', related='move_id.company_id')
    alerts = fields.Json(compute='_compute_alerts')
    sending_methods = fields.Json(
        compute='_compute_sending_methods',
        inverse='_inverse_sending_methods',
    )
    sending_method_checkboxes = fields.Json(
        compute='_compute_sending_method_checkboxes',
        precompute=True,
        readonly=False,
        store=True,
    )
    # Technical field to display the attachments widget
    display_attachments_widget = fields.Boolean(
        compute='_compute_display_attachments_widget',
    )
    extra_edis = fields.Json(
        compute='_compute_extra_edis',
        inverse='_inverse_extra_edis',
    )
    extra_edi_checkboxes = fields.Json(
        compute='_compute_extra_edi_checkboxes',
        precompute=True,
        readonly=False,
        store=True,
    )
    invoice_edi_format = fields.Selection(
        selection=lambda self: self.env['res.partner']._fields['invoice_edi_format'].selection,
        compute='_compute_invoice_edi_format',
    )
    pdf_report_id = fields.Many2one(
        comodel_name='ir.actions.report',
        string="Invoice report",
        domain="[('id', 'in', available_pdf_report_ids)]",
        compute='_compute_pdf_report_id',
        readonly=False,
        store=True,
    )
    available_pdf_report_ids = fields.One2many(
        comodel_name='ir.actions.report',
        compute="_compute_available_pdf_report_ids",
    )

    display_pdf_report_id = fields.Boolean(compute='_compute_display_pdf_report_id')

    # MAIL
    # Template: override mail.composer.mixin field
    template_id = fields.Many2one(
        domain="[('model', '=', 'account.move')]",
        compute='_compute_template_id',
        compute_sudo=True,
        readonly=False,
        store=True,
    )
    # Language: override mail.composer.mixin field
    lang = fields.Char(compute='_compute_lang', precompute=False, compute_sudo=True)
    mail_partner_ids = fields.Many2many(
        comodel_name='res.partner',
        string="To",
        compute='_compute_mail_partners',
        store=True,
        readonly=False,
    )
    mail_attachments_widget = fields.Json(
        compute='_compute_mail_attachments_widget',
        store=True,
        readonly=False,
    )
    attachments_not_supported = fields.Json(compute='_compute_attachments_not_supported')

    model = fields.Char('Related Document Model', compute='_compute_model', readonly=False, store=True)
    res_ids = fields.Text('Related Document IDs', compute='_compute_res_ids', readonly=False, store=True)
    template_name = fields.Char('Template Name')  # used when saving a new mail template

    # -------------------------------------------------------------------------
    # DEFAULTS
    # -------------------------------------------------------------------------

    @api.model
    def default_get(self, fields):
        # EXTENDS 'base'
        results = super().default_get(fields)
        if 'move_id' in fields and 'move_id' not in results:
            move_id = self.env.context.get('active_ids', [])[0]
            results['move_id'] = move_id
        return results

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------

    @api.depends('sending_methods', 'extra_edis', 'mail_partner_ids')
    def _compute_alerts(self):
        for wizard in self:
            move_data = {
                wizard.move_id: {
                    'sending_methods': wizard.sending_methods or {},
                    'invoice_edi_format': wizard.invoice_edi_format,
                    'extra_edis': wizard.extra_edis or {},
                    'mail_partner_ids': wizard.mail_partner_ids
                }
            }
            wizard.alerts = self._get_alerts(wizard.move_id, move_data)

    @api.depends('sending_method_checkboxes')
    def _compute_sending_methods(self):
        for wizard in self:
            wizard.sending_methods = self._get_selected_checkboxes(wizard.sending_method_checkboxes)

    def _inverse_sending_methods(self):
        for wizard in self:
            wizard.sending_method_checkboxes = {method_key: {'checked': True} for method_key in wizard.sending_methods or {}}

    @api.depends('move_id')
    def _compute_sending_method_checkboxes(self):
        """ Select one applicable sending method given the following priority
        1. preferred method set on partner,
        2. email,
        """
        methods = self.env['ir.model.fields'].get_field_selection('res.partner', 'invoice_sending_method')

        # We never want to display the manual method.
        methods = [method for method in methods if method[0] != 'manual']

        for wizard in self:
            preferred_methods = self._get_default_sending_methods(wizard.move_id)
            wizard.sending_method_checkboxes = {
                method_key: {
                    'checked': (
                        method_key in preferred_methods and (
                            method_key == 'email' or self._is_applicable_to_move(method_key, wizard.move_id, **self._get_default_sending_settings(wizard.move_id))
                        )),  # email method is always ok in single mode since the email can be added if it's missing
                    'label': method_label,
                }
                for method_key, method_label in methods
                if self._is_applicable_to_company(method_key, wizard.company_id)
            }

    @api.depends('invoice_edi_format')
    def _compute_display_attachments_widget(self):
        for wizard in self:
            wizard.display_attachments_widget = wizard._display_attachments_widget(
                edi_format=wizard.invoice_edi_format,
                sending_methods=wizard.sending_methods or [],
            )

    @api.depends('extra_edi_checkboxes')
    def _compute_extra_edis(self):
        for wizard in self:
            wizard.extra_edis = self._get_selected_checkboxes(wizard.extra_edi_checkboxes)

    def _inverse_extra_edis(self):
        for wizard in self:
            wizard.extra_edi_checkboxes = {method_key: {'checked': True} for method_key in wizard.extra_edis or {}}

    @api.depends('move_id')
    def _compute_extra_edi_checkboxes(self):
        all_extra_edis = self._get_all_extra_edis()
        for wizard in self:
            wizard.extra_edi_checkboxes = {
                edi_key: {'checked': True, 'label': all_extra_edis[edi_key]['label'], 'help': all_extra_edis[edi_key].get('help')}
                for edi_key in self._get_default_extra_edis(wizard.move_id)
            }

    @api.depends('move_id', 'sending_methods')
    def _compute_invoice_edi_format(self):
        for wizard in self:
            wizard.invoice_edi_format = self._get_default_invoice_edi_format(wizard.move_id, sending_methods=wizard.sending_methods or {})

    @api.depends('move_id')
    def _compute_pdf_report_id(self):
        for wizard in self:
            wizard.pdf_report_id = self._get_default_pdf_report_id(wizard.move_id)

    @api.depends('move_id')
    def _compute_available_pdf_report_ids(self):
        available_reports = self.move_id._get_available_action_reports()
        for wizard in self:
            wizard.available_pdf_report_ids = available_reports

    @api.depends('move_id')
    def _compute_display_pdf_report_id(self):
        """ Show PDF template selection if there are more than 1 template available for invoices. """
        for wizard in self:
            wizard.display_pdf_report_id = len(wizard.available_pdf_report_ids) > 1 and not wizard.move_id.invoice_pdf_report_id

    @api.depends('move_id')
    def _compute_template_id(self):
        for wizard in self:
            wizard.template_id = self._get_default_mail_template_id(wizard.move_id)

    @api.depends('template_id')
    def _compute_lang(self):
        # OVERRIDE 'mail.composer.mixin'
        for wizard in self:
            wizard.lang = self._get_default_mail_lang(wizard.move_id, wizard.template_id) if wizard.template_id else get_lang(self.env).code

    @api.depends('template_id', 'lang')
    def _compute_mail_partners(self):
        for wizard in self:
            wizard.mail_partner_ids = commercial_partner if (commercial_partner := wizard.move_id.commercial_partner_id).email else None
            if wizard.template_id:
                wizard.mail_partner_ids = self._get_default_mail_partner_ids(wizard.move_id, wizard.template_id, wizard.lang)

    @api.depends('template_id', 'lang')
    def _compute_subject(self):
        # OVERRIDE 'mail.composer.mixin'
        for wizard in self:
            wizard.subject = None

            if wizard.template_id:
                wizard.subject = self._get_default_mail_subject(wizard.move_id, wizard.template_id, wizard.lang)

    @api.depends('template_id', 'lang')
    def _compute_body(self):
        # OVERRIDE 'mail.composer.mixin'
        for wizard in self:
            wizard.body = None

            if wizard.template_id:
                wizard.body = self._get_default_mail_body(wizard.move_id, wizard.template_id, wizard.lang)

    @api.depends('template_id', 'invoice_edi_format', 'extra_edis', 'pdf_report_id')
    def _compute_mail_attachments_widget(self):
        for wizard in self:
            manual_attachments_data = [x for x in wizard.mail_attachments_widget or [] if x.get('manual')]
            wizard.mail_attachments_widget = (
                self._get_default_mail_attachments_widget(
                    wizard.move_id,
                    wizard.template_id,
                    invoice_edi_format=wizard.invoice_edi_format,
                    extra_edis=wizard.extra_edis or {},
                    pdf_report=wizard.pdf_report_id,
                )
                + manual_attachments_data
            )

    # Similar of mail.compose.message
    @api.depends('template_id')
    def _compute_res_ids(self):
        for wizard in self:
            wizard.res_ids = wizard.move_id.ids

    # Similar of mail.compose.message
    @api.depends('template_id')
    def _compute_model(self):
        for wizard in self:
            if wizard.model:
                continue
            wizard.model = self.env.context.get('active_model')

    # Similar of mail.compose.message
    @api.depends('sending_methods')
    def _compute_can_edit_body(self):
        for record in self:
            record.can_edit_body = record.sending_methods and 'email' in record.sending_methods

    @api.depends('model')  # Fake trigger otherwise not computed in new mode
    def _compute_render_model(self):
        # OVERRIDE 'mail.composer.mixin'
        self.render_model = 'account.move'

    # Similar of mail.compose.message
    def open_template_creation_wizard(self):
        """ Hit save as template button: opens a wizard that prompts for the template's subject.
            `create_mail_template` is called when saving the new wizard. """

        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'view_id': self.env.ref('mail.mail_compose_message_view_form_template_save').id,
            'name': _('Create a Mail Template'),
            'res_model': 'account.move.send.wizard',
            'context': {'dialog_size': 'medium'},
            'target': 'new',
            'res_id': self.id,
        }

    # Similar of mail.compose.message
    def create_mail_template(self):
        """ Creates a mail template with the current mail composer's fields. """
        self.ensure_one()
        if not self.model or not self.model in self.env:
            raise UserError(_('Template creation from composer requires a valid model.'))
        model_id = self.env['ir.model']._get_id(self.model)
        values = {
            'name': self.template_name or self.subject,
            'subject': self.subject,
            'body_html': self.body,
            'model_id': model_id,
            'use_default_to': True,
            'user_id': self.env.uid,
        }
        template = self.env['mail.template'].create(values)

        # generate the saved template
        self.write({'template_id': template.id})
        return _reopen(self, self.id, self.model, context={**self.env.context, 'dialog_size': 'large'})

    # Similar of mail.compose.message
    def cancel_save_template(self):
        """ Restore old subject when canceling the 'save as template' action
            as it was erased to let user give a more custom input. """
        self.ensure_one()
        return _reopen(self, self.id, self.model, context={**self.env.context, 'dialog_size': 'large'})

    @api.depends('invoice_edi_format', 'mail_attachments_widget')
    def _compute_attachments_not_supported(self):
        for wizard in self:
            wizard.attachments_not_supported = {}

    # -------------------------------------------------------------------------
    # CONSTRAINS
    # -------------------------------------------------------------------------

    @api.constrains('move_id')
    def _check_move_id_constraints(self):
        for wizard in self:
            self._check_move_constraints(wizard.move_id)

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    @api.model
    def _get_selected_checkboxes(self, json_checkboxes):
        if not json_checkboxes:
            return {}
        return [checkbox_key for checkbox_key, checkbox_vals in json_checkboxes.items() if checkbox_vals['checked']]

    def _ai_get_settings(self):
        return get_ai_settings(self.env, profile='email')

    def _ai_configuration_error(self, settings):
        if not settings['enabled']:
            return _('AI is not enabled. Enable it in Settings > Integrations > AI.')
        if not settings['endpoint']:
            return _('AI is missing a Base URL in Settings > Integrations > AI.')
        if not settings['model']:
            return _('AI is missing a model in Settings > Integrations > AI.')
        if not settings['api_key']:
            return _('AI is missing an API key in Settings > Integrations > AI.')
        return False

    @staticmethod
    def _ai_chat_url(endpoint):
        endpoint = (endpoint or '').strip().rstrip('/')
        if endpoint.endswith('/chat/completions'):
            return endpoint
        if endpoint.endswith('/models'):
            endpoint = endpoint[:-len('/models')]
        return f'{endpoint}/chat/completions'

    def _ai_chat_completion(self, settings, messages):
        response = requests.post(
            self._ai_chat_url(settings['endpoint']),
            headers={
                'Authorization': f"Bearer {settings['api_key']}",
                'Content-Type': 'application/json',
            },
            json={
                'model': settings['model'],
                'messages': messages,
                'temperature': 0.25,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        choices = data.get('choices') or []
        if not choices:
            raise UserError(_('The AI provider returned no choices.'))
        message = choices[0].get('message') or {}
        if not isinstance(message, dict):
            raise UserError(_('The AI provider returned an invalid message.'))
        return (message.get('content') or '').strip()

    def _ai_document_type_label(self):
        return {
            'out_invoice': _('customer invoice'),
            'out_refund': _('credit note'),
            'in_invoice': _('vendor bill'),
            'in_refund': _('vendor credit note'),
        }.get(self.move_id.move_type, self.move_id._description)

    def _ai_payment_state_label(self):
        return dict(self.move_id._fields['payment_state'].selection).get(self.move_id.payment_state) or self.move_id.payment_state or ''

    def _ai_invoice_line_context(self):
        lines = []
        invoice_lines = self.move_id.invoice_line_ids.filtered(lambda line: line.display_type not in ('line_section', 'line_note'))
        for index, line in enumerate(invoice_lines[:20], start=1):
            quantity = f"{line.quantity:g}" if isinstance(line.quantity, float) else line.quantity
            uom = line.product_uom_id.name or ''
            price_unit = format_amount(self.env, line.price_unit, self.move_id.currency_id)
            subtotal = format_amount(self.env, line.price_subtotal, self.move_id.currency_id)
            lines.append(
                f"{index}. {line.name or line.product_id.display_name or '[no description]'}; "
                f"quantity: {quantity} {uom}; unit price: {price_unit}; subtotal: {subtotal}"
            )
        if len(invoice_lines) > 20:
            lines.append(_('%s more lines not shown.', len(invoice_lines) - 20))
        return lines

    def _ai_recent_chatter_context(self):
        messages = self.env['mail.message'].search([
            ('model', '=', 'account.move'),
            ('res_id', '=', self.move_id.id),
            ('message_type', 'in', ('comment', 'email')),
        ], order='id desc', limit=AI_EMAIL_CONTEXT_MESSAGE_LIMIT)
        result = []
        for message in reversed(messages):
            body = html2plaintext(message.body or '').strip()
            if len(body) > 700:
                body = f"{body[:700].rstrip()}..."
            if not body:
                continue
            author = message.author_id.display_name if message.author_id else _('System')
            result.append(f"- {author}: {body}")
        return result

    def _ai_prepare_email_messages(self):
        self.ensure_one()
        move = self.move_id
        partner = move.partner_id
        lang = self.lang or self.env.context.get('lang') or get_lang(self.env).code
        document_lines = [
            f"UI/user language: {lang}",
            f"Company: {move.company_id.display_name}",
            f"Document type: {self._ai_document_type_label()}",
            f"Document number: {move.name or '[draft/no number]'}",
            f"Customer: {partner.display_name or '[missing]'}",
            f"Customer email: {partner.email or '[missing]'}",
            f"Invoice date: {format_date(self.env, move.invoice_date) if move.invoice_date else '[missing]'}",
            f"Due date: {format_date(self.env, move.invoice_date_due) if move.invoice_date_due else '[missing]'}",
            f"Origin/reference: {move.invoice_origin or move.ref or '[none]'}",
            f"Payment state: {self._ai_payment_state_label()}",
            f"Payment reference: {move.payment_reference or '[none]'}",
            f"Total: {format_amount(self.env, move.amount_total, move.currency_id)}",
            f"Amount due: {format_amount(self.env, move.amount_residual, move.currency_id)}",
            f"Current draft subject: {self.subject or '[empty]'}",
            f"Current draft body: {html2plaintext(self.body or '').strip() or '[empty]'}",
        ]
        line_context = self._ai_invoice_line_context()
        chatter_context = self._ai_recent_chatter_context()
        if line_context:
            document_lines.append('Invoice lines:')
            document_lines.extend(line_context)
        if chatter_context:
            document_lines.append('Recent document chatter:')
            document_lines.extend(chatter_context)

        return [
            {
                'role': 'system',
                'content': (
                    "You write customer-facing accounting emails inside NWOS/Flectra. "
                    "Use only the facts provided by the ERP context. Do not invent bank details, "
                    "payment status, contact details, invoice lines, discounts, or attachments. "
                    "If the UI/user language starts with vi, write natural Vietnamese. "
                    "Keep the tone professional, clear, and warm. "
                    "For invoices, mention payment only when unpaid and use due date/payment reference when present. "
                    "For credit notes, do not request payment; explain that the attached credit note adjusts the earlier document. "
                    "Mention that the PDF is attached. "
                    "Return only a JSON object with keys subject and body_html. "
                    "body_html must use simple HTML tags only: p, br, ul, li, strong."
                ),
            },
            {
                'role': 'user',
                'content': "\n".join(document_lines),
            },
        ]

    def _ai_parse_email_response(self, content):
        content = (content or '').strip()
        content = re.sub(r'^```(?:json|html)?\s*', '', content)
        content = re.sub(r'\s*```$', '', content)
        json_match = re.search(r'\{.*\}', content, flags=re.S)
        payload_text = json_match.group(0) if json_match else content
        try:
            payload = json.loads(payload_text)
        except ValueError:
            payload = {'subject': '', 'body_html': content}
        if not isinstance(payload, dict):
            raise UserError(_('The AI provider returned an invalid email draft.'))

        subject = str(payload.get('subject') or '').strip()
        body_html = str(payload.get('body_html') or payload.get('body') or '').strip()
        if not subject:
            subject = self.subject or _('%(company)s - %(document)s %(number)s', company=self.move_id.company_id.name, document=self._ai_document_type_label(), number=self.move_id.name or '')
        if not body_html:
            raise UserError(_('The AI provider returned an empty email body.'))
        if '<' not in body_html or '>' not in body_html:
            body_html = str(plaintext2html(body_html))
        if len(body_html) > AI_EMAIL_BODY_LIMIT:
            body_html = body_html[:AI_EMAIL_BODY_LIMIT]
        return subject, body_html

    # -------------------------------------------------------------------------
    # BUSINESS METHODS
    # -------------------------------------------------------------------------

    def _get_sending_settings(self):
        self.ensure_one()
        send_settings = {
            'sending_methods': self.sending_methods or [],
            'invoice_edi_format': self.invoice_edi_format,
            'extra_edis': self.extra_edis or [],
            'pdf_report': self.pdf_report_id,
            'author_user_id': self.env.user.id,
            'author_partner_id': self.env.user.partner_id.id,
        }
        if self.sending_methods and 'email' in self.sending_methods:
            send_settings.update({
                'mail_template': self.template_id,
                'mail_lang': self.lang,
                'mail_body': self.body,
                'mail_subject': self.subject,
                'mail_partner_ids': self.mail_partner_ids.ids,
            })
        if self.display_attachments_widget:
            send_settings['mail_attachments_widget'] = self.mail_attachments_widget
        return send_settings

    def _update_preferred_settings(self):
        """If the partner's settings are not set, we use them as partner's default."""
        self.ensure_one()
        if not self.move_id.partner_id.invoice_template_pdf_report_id and self.pdf_report_id != self._get_default_pdf_report_id(self.move_id):
            self.move_id.partner_id.sudo().invoice_template_pdf_report_id = self.pdf_report_id

    # -------------------------------------------------------------------------
    # BUSINESS ACTIONS
    # -------------------------------------------------------------------------

    @api.model
    def _action_download(self, attachments):
        """ Download the PDF attachment, or a zip of attachments if there are more than one. """
        return {
            'type': 'ir.actions.act_url',
            'url': f'/account/download_invoice_attachments/{",".join(map(str, attachments.ids))}',
            'close': True,
        }

    def action_send_and_print(self, allow_fallback_pdf=False):
        """ Create invoice documents and send them."""
        self.ensure_one()
        if self.alerts:
            self._raise_danger_alerts(self.alerts)
        self._update_preferred_settings()
        attachments = self._generate_and_send_invoices(
            self.move_id,
            **self._get_sending_settings(),
            allow_fallback_pdf=allow_fallback_pdf,
        )
        if attachments and self.sending_methods and 'manual' in self.sending_methods:
            return self._action_download(attachments)
        else:
            return {'type': 'ir.actions.act_window_close'}

    def action_ai_write_email(self):
        """Generate a better customer email for the current accounting document."""
        self.ensure_one()
        if not self.sending_methods or 'email' not in self.sending_methods:
            raise UserError(_('Select the email sending method before using AI.'))

        settings = self._ai_get_settings()
        if error := self._ai_configuration_error(settings):
            raise UserError(error)

        try:
            content = self._ai_chat_completion(settings, self._ai_prepare_email_messages())
            subject, body_html = self._ai_parse_email_response(content)
        except requests.RequestException as error:
            raise UserError(_('The AI provider request failed: %s', error)) from error

        self.write({
            'subject': subject,
            'body': body_html,
        })
        return _reopen(self, self.id, self.model or 'account.move', context={**self.env.context, 'dialog_size': 'large'})
