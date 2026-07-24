# -*- coding: utf-8 -*-
import base64
import re

from jinja2 import ChainableUndefined
from jinja2.sandbox import SandboxedEnvironment
from markupsafe import Markup, escape

from nwos import _, api, fields, models
from nwos.exceptions import UserError, ValidationError
from nwos.tools import format_amount, format_date, format_datetime

from .econtract_template import PLACEHOLDER_RE, FIELD_TYPES, slugify_key

# The HTML editor escapes special characters inside the body; unescape them
# within Jinja2 delimiters so expressions like {% if x > 3 %} survive.
JINJA_SPAN_RE = re.compile(r'(\{\{.*?\}\}|\{%.*?%\})', re.S)


UNSAFE_RECORD_ATTRS = frozenset((
    'env', 'pool', 'sudo', 'with_user', 'with_env', 'with_context', 'browse',
    'search', 'search_count', 'write', 'create', 'unlink', 'invalidate_cache',
))


class EContractJinjaEnvironment(SandboxedEnvironment):
    """Sandbox that additionally blocks ORM escape hatches on records."""

    def is_safe_attribute(self, obj, attr, value):
        if attr in UNSAFE_RECORD_ATTRS:
            return False
        return super().is_safe_attribute(obj, attr, value)


def _unescape_jinja_spans(body):
    def unescape(match):
        span = match.group(0)
        for entity, char in (('&quot;', '"'), ('&#39;', "'"), ('&#x27;', "'"),
                             ('&lt;', '<'), ('&gt;', '>'), ('&amp;', '&'),
                             (' ', ' ')):
            span = span.replace(entity, char)
        return span
    return JINJA_SPAN_RE.sub(unescape, body or '')


class EContractContract(models.Model):
    _name = 'econtract.contract'
    _description = 'eContract'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    name = fields.Char(
        'Reference', required=True, copy=False, readonly=True,
        default=lambda self: _('New'))
    title = fields.Char('Title', required=True, tracking=True)
    template_id = fields.Many2one(
        'econtract.template', string='Template', required=True,
        ondelete='restrict', tracking=True)
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id)
    partner_id = fields.Many2one('res.partner', string='Customer', tracking=True)
    user_id = fields.Many2one(
        'res.users', string='Responsible', default=lambda self: self.env.user)

    # Generic link back to the record this contract was generated from.
    res_model = fields.Char('Source Model', readonly=True, copy=False)
    res_id = fields.Integer('Source Id', readonly=True, copy=False)
    source_display = fields.Char('Source Document', compute='_compute_source_display')

    body_html = fields.Html(
        'Contract Body', sanitize=True, sanitize_style=True,
        help="Snapshot of the template body taken when the contract was created.")
    rendered_body = fields.Html(
        'Preview', compute='_compute_rendered_body', sanitize=False)
    value_ids = fields.One2many(
        'econtract.contract.value', 'contract_id', string='Field Values', copy=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('signed', 'Signed'),
        ('cancelled', 'Cancelled'),
    ], default='draft', tracking=True, copy=False)

    signed_by = fields.Char('Signed By', readonly=True, copy=False, tracking=True)
    signed_on = fields.Datetime('Signed On', readonly=True, copy=False)
    signature = fields.Binary('Signature', readonly=True, copy=False, attachment=True)
    sign_url = fields.Char('Signing Link', compute='_compute_sign_url')

    # ------------------------------------------------------------------ compute
    def _compute_source_display(self):
        for c in self:
            label = False
            if c.res_model and c.res_id:
                rec = self.env[c.res_model].browse(c.res_id).exists()
                label = rec.display_name if rec else False
            c.source_display = label

    @api.depends('body_html', 'template_id.engine', 'value_ids.display_value',
                 'value_ids.value_signature', 'value_ids.field_type')
    def _compute_rendered_body(self):
        for c in self:
            c.rendered_body = c._render_body()

    def _compute_sign_url(self):
        for c in self:
            c.sign_url = c._get_sign_url() if c.id else False

    def _compute_access_url(self):
        super()._compute_access_url()
        for c in self:
            c.access_url = '/my/econtract/%s' % c.id

    # ------------------------------------------------------------------ create
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('econtract.contract') or _('New')
        records = super().create(vals_list)
        for rec in records:
            if not rec.value_ids and rec.template_id:
                rec._generate_values()
        return records

    # ------------------------------------------------------------------ onchange
    @api.onchange('template_id')
    def _onchange_template_id(self):
        if self.template_id:
            self.body_html = self.template_id.body_html
            if not self.title:
                self.title = self.template_id.name
            self._generate_values()

    # ------------------------------------------------------------------ values
    def _generate_values(self):
        """(Re)build value lines from the template's detected fields, keeping any
        values the user already entered for keys that still exist."""
        self.ensure_one()
        existing = {v.name: v for v in self.value_ids}
        commands = []
        for f in self.template_id.field_ids:
            if f.name in existing:
                continue
            commands.append((0, 0, {
                'name': f.name,
                'label': f.label,
                'field_type': f.field_type,
                'sequence': f.sequence,
                'required': f.required,
                'template_field_id': f.id,
                'value_char': f.default_value if f.field_type in ('text', 'number', 'monetary') else False,
            }))
        # drop values whose key no longer exists on the template
        template_keys = set(self.template_id.field_ids.mapped('name'))
        for name, v in existing.items():
            if name not in template_keys:
                commands.append((2, v.id))
        if commands:
            self.value_ids = commands
        # snapshot body if missing
        if not self.body_html:
            self.body_html = self.template_id.body_html

    def action_regenerate_values(self):
        for c in self:
            c.body_html = c.template_id.body_html
            c._generate_values()
        return True

    # ------------------------------------------------------------------ autofill
    @api.model
    def _traverse_path(self, record, path):
        cur = record
        try:
            for part in path.split('.'):
                if not cur:
                    return False
                cur = cur[part.strip()]
        except (KeyError, AttributeError, TypeError):
            return False
        return cur

    def _autofill_from_record(self, record):
        """Fill mapped values from *record* (sale.order, purchase.order, partner...)."""
        self.ensure_one()
        if not record:
            return
        for v in self.value_ids:
            path = v.template_field_id.mapping
            if not path:
                continue
            resolved = self._traverse_path(record, path)
            if resolved not in (False, None, ''):
                v._set_python_value(resolved)

    # ------------------------------------------------------------------ rendering
    def _render_body(self):
        self.ensure_one()
        values = {v.name: v for v in self.value_ids}

        def repl(match):
            key = slugify_key((match.group(1) or '').strip())
            v = values.get(key)
            if v is None:
                return match.group(0)
            if v.field_type == 'signature':
                if v.value_signature:
                    b64 = v.value_signature
                    if isinstance(b64, bytes):
                        b64 = b64.decode()
                    return ('<img alt="signature" class="econtract-signature" '
                            'style="max-height:90px;max-width:320px;" '
                            'src="data:image/png;base64,%s"/>' % b64)
                return ('<span style="display:inline-block;min-width:220px;height:60px;'
                        'border-bottom:1px solid #000;"></span>')
            return str(escape(v.display_value or ''))

        rendered = PLACEHOLDER_RE.sub(repl, self.body_html or '')
        if self.template_id.engine == 'jinja2':
            rendered = self._render_jinja(rendered)
        return Markup(rendered)

    def _get_jinja_context(self):
        """Variables available to Jinja2 templates."""
        self.ensure_one()
        source = None
        if self.res_model and self.res_id and self.res_model in self.env:
            source = self.env[self.res_model].browse(self.res_id).exists() or None
        values = {v.name: v.display_value for v in self.value_ids}
        return {
            'object': source,
            'contract': self,
            'partner': self.partner_id,
            'company': self.company_id,
            'user': self.env.user,
            'currency': self.currency_id,
            'values': values,
            'today': fields.Date.context_today(self),
            'now': fields.Datetime.context_timestamp(self, fields.Datetime.now()),
            'format_amount': lambda amount, currency=None: format_amount(
                self.env, amount, currency or self.currency_id),
            'format_date': lambda value, fmt=False: format_date(
                self.env, value, date_format=fmt),
            'format_datetime': lambda value, fmt=False: format_datetime(
                self.env, value, dt_format=fmt),
        }

    def _render_jinja(self, body):
        """Render *body* through a sandboxed Jinja2 environment. Errors are
        surfaced inline in the preview instead of crashing the form."""
        self.ensure_one()
        env = EContractJinjaEnvironment(
            autoescape=False,
            undefined=ChainableUndefined,
            trim_blocks=True,
            keep_trailing_newline=True,
            # empty fields (False/None) must print as nothing, not "False"
            finalize=lambda value: '' if value is False or value is None else value,
        )
        try:
            return env.from_string(_unescape_jinja_spans(body)).render(
                **self._get_jinja_context())
        except Exception as exc:  # noqa: BLE001 - template syntax is user input
            return (
                '<div class="alert alert-danger">%s<br/><code>%s</code></div>%s'
                % (escape(_('Jinja2 template error:')), escape(str(exc)), body)
            )

    # ------------------------------------------------------------------ actions
    def action_open_source(self):
        self.ensure_one()
        if not (self.res_model and self.res_id):
            return False
        return {
            'type': 'ir.actions.act_window',
            'res_model': self.res_model,
            'res_id': self.res_id,
            'view_mode': 'form',
        }

    def action_send(self):
        for c in self:
            if c.state == 'draft':
                c.state = 'sent'
            c._portal_ensure_token()
            c.message_post(
                body=Markup(_(
                    'Contract ready for signature: <a href="%s">Open signing page</a>'
                )) % c._get_sign_url())
        return True

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def action_mark_signed(self):
        for c in self:
            c._apply_signature(
                signer=c.partner_id.name or c.env.user.name,
                signature_b64=c.signature)
        return True

    def _apply_signature(self, signer, signature_b64=None):
        self.ensure_one()
        vals = {
            'state': 'signed',
            'signed_by': signer,
            'signed_on': fields.Datetime.now(),
        }
        if signature_b64:
            vals['signature'] = signature_b64
            target = self._get_signature_target()
            if target:
                target.write({'value_signature': signature_b64})
        self.write(vals)
        self.message_post(body=_('Signed by %s.', signer))
        self._attach_pdf()

    def _get_signature_target(self):
        """The signature field the portal signer (the customer) should fill:
        prefer an empty field whose key/label reads as the customer/buyer side,
        else the first empty signature field. Never overwrite a drawn one."""
        self.ensure_one()
        empty = self.value_ids.filtered(
            lambda v: v.field_type == 'signature' and not v.value_signature)
        customer_tokens = ('mua', 'buyer', 'customer', 'khach', 'client')
        for v in empty:
            haystack = ('%s %s' % (v.name or '', v.label or '')).lower()
            if any(tok in haystack for tok in customer_tokens):
                return v
        return empty[:1]

    def _get_sign_url(self):
        self.ensure_one()
        return '/my/econtract/%s?access_token=%s' % (self.id, self._portal_ensure_token())

    # ------------------------------------------------------------------ pdf
    def _render_pdf_bytes(self):
        self.ensure_one()
        pdf, _dummy = self.env['ir.actions.report']._render_qweb_pdf(
            'nwos_econtract.action_report_econtract', self.ids)
        return pdf

    def action_print(self):
        return self.env.ref('nwos_econtract.action_report_econtract').report_action(self)

    # ------------------------------------------------------------------ word (.doc)
    def _render_word_bytes(self):
        """Render the contract as a Microsoft Word document.

        We emit Word-flavoured HTML (the classic ``application/msword`` format
        Word opens natively) rather than a real .docx — it needs no external
        library, reuses the exact ``_render_body()`` output, and keeps tables,
        styles and the embedded signature image intact.
        """
        self.ensure_one()
        body = self._render_body()
        signed_block = ''
        if self.state == 'signed':
            signed_block = (
                '<p style="border-top:1px solid #ccc;margin-top:24pt;padding-top:6pt;'
                'font-size:8.5pt;color:#444;">%s %s %s %s — %s</p>' % (
                    escape(_('Signed electronically by')),
                    escape(self.signed_by or ''),
                    escape(_('on')),
                    escape(self.signed_on and format_datetime(self.env, self.signed_on) or ''),
                    escape(self.name or ''),
                )
            )
        html = Markup(
            '<html xmlns:o="urn:schemas-microsoft-com:office:office" '
            'xmlns:w="urn:schemas-microsoft-com:office:word" '
            'xmlns="http://www.w3.org/TR/REC-html40">'
            '<head><meta charset="utf-8"/>'
            '<title>%(title)s</title>'
            '<!--[if gte mso 9]><xml><w:WordDocument>'
            '<w:View>Print</w:View><w:Zoom>100</w:Zoom>'
            '</w:WordDocument></xml><![endif]-->'
            '<style>'
            '@page { size: A4; margin: 2cm; }'
            'body { font-family: "Times New Roman", serif; font-size: 11pt; '
            'color: #000; line-height: 1.45; }'
            'table { border-collapse: collapse; width: 100%%; }'
            'table[border] td, table[border] th { border: 0.5pt solid #444; padding: 3pt 6pt; }'
            'h1, h2, h3, h4 { font-weight: bold; }'
            'img.econtract-signature { max-height: 90px; }'
            '</style></head><body>%(body)s%(signed)s</body></html>'
        ) % {
            'title': escape(self.title or self.name or 'Contract'),
            'body': body,
            'signed': Markup(signed_block),
        }
        return html.encode('utf-8')

    def _word_filename(self):
        self.ensure_one()
        base = (self.title or self.name or 'contract').strip()
        # keep it filesystem/HTTP-header safe
        safe = re.sub(r'[^\w.\- ]+', '_', base)
        return '%s.doc' % safe

    def action_download_word(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/econtract/%s/word' % self.id,
            'target': 'self',
        }

    def _attach_pdf(self):
        """Store the signed contract PDF and, when it came from a source record,
        attach a copy there too."""
        self.ensure_one()
        try:
            pdf = self._render_pdf_bytes()
        except Exception:  # noqa: BLE001 - never block signing on a render hiccup
            return False
        filename = '%s.pdf' % (self.title or self.name)
        Attachment = self.env['ir.attachment'].sudo()
        Attachment.create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(pdf),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })
        if self.res_model and self.res_id and self.env[self.res_model].browse(self.res_id).exists():
            Attachment.create({
                'name': filename,
                'type': 'binary',
                'datas': base64.b64encode(pdf),
                'res_model': self.res_model,
                'res_id': self.res_id,
                'mimetype': 'application/pdf',
            })
        return True

    # ------------------------------------------------------------------ generation entrypoint
    @api.model
    def create_from_record(self, template, record):
        """Create a contract from *template* pre-filled off *record*."""
        partner = False
        if record._name == 'res.partner':
            partner = record
        elif 'partner_id' in record._fields:
            partner = record.partner_id
        currency = record.currency_id if 'currency_id' in record._fields and record.currency_id \
            else self.env.company.currency_id
        contract = self.create({
            'template_id': template.id,
            'title': '%s - %s' % (template.name, record.display_name),
            'partner_id': partner.id if partner else False,
            'currency_id': currency.id,
            'res_model': record._name,
            'res_id': record.id,
            'body_html': template.body_html,
        })
        contract._autofill_from_record(record)
        return contract


class EContractContractValue(models.Model):
    _name = 'econtract.contract.value'
    _description = 'eContract Field Value'
    _order = 'sequence, id'

    contract_id = fields.Many2one(
        'econtract.contract', string='Contract', required=True, ondelete='cascade')
    template_field_id = fields.Many2one(
        'econtract.template.field', string='Template Field', ondelete='set null')
    sequence = fields.Integer(default=10)
    # snapshot of the template field so the contract stays self-contained
    name = fields.Char('Key', required=True)
    label = fields.Char('Label', required=True)
    field_type = fields.Selection(FIELD_TYPES, string='Type', required=True, default='text')
    required = fields.Boolean('Required')

    value_char = fields.Char('Value')
    value_number = fields.Float('Number')
    value_date = fields.Date('Date')
    value_datetime = fields.Datetime('Date & Time')
    value_boolean = fields.Boolean('Yes/No')
    value_signature = fields.Binary('Signature', attachment=True)

    display_value = fields.Char('Display', compute='_compute_display_value',
                                inverse='_inverse_display_value')
    currency_id = fields.Many2one(related='contract_id.currency_id')

    @api.depends('field_type', 'value_char', 'value_number', 'value_date',
                 'value_datetime', 'value_boolean', 'value_signature', 'currency_id')
    def _compute_display_value(self):
        for v in self:
            t = v.field_type
            if t == 'boolean':
                v.display_value = _('Yes') if v.value_boolean else _('No')
            elif t == 'number':
                v.display_value = ('%g' % v.value_number) if v.value_number else (v.value_char or '')
            elif t == 'monetary':
                v.display_value = v.currency_id.format(v.value_number) if v.currency_id \
                    else ('%.2f' % v.value_number)
            elif t == 'date':
                v.display_value = format_date(v.env, v.value_date) if v.value_date else ''
            elif t == 'datetime':
                v.display_value = format_datetime(v.env, v.value_datetime) if v.value_datetime else ''
            elif t == 'signature':
                v.display_value = _('Signed') if v.value_signature else ''
            else:
                v.display_value = v.value_char or ''

    def _inverse_display_value(self):
        """Allow typing the value straight into the list's Value column."""
        for v in self:
            raw = (v.display_value or '').strip()
            t = v.field_type
            if t == 'signature':
                continue  # drawn in the row dialog, not typed
            if t == 'boolean':
                v.value_boolean = raw.lower() in ('yes', 'y', 'true', '1', 'có', 'co', 'x')
                continue
            if not raw:
                v.value_char = False
                v.value_number = 0.0
                v.value_date = False
                v.value_datetime = False
                continue
            if t in ('number', 'monetary'):
                cleaned = re.sub(r'[^0-9,.\-]', '', raw).replace(',', '')
                try:
                    v.value_number = float(cleaned)
                except ValueError:
                    raise UserError(_('"%s" is not a valid number for %s.', raw, v.label))
                if t == 'number':
                    v.value_char = raw
            elif t == 'date':
                try:
                    v.value_date = fields.Date.to_date(raw)
                except ValueError:
                    raise UserError(_('"%s" is not a valid date for %s — use YYYY-MM-DD.',
                                      raw, v.label))
            elif t == 'datetime':
                try:
                    v.value_datetime = fields.Datetime.to_datetime(raw)
                except ValueError:
                    raise UserError(_('"%s" is not a valid date & time for %s — use '
                                      'YYYY-MM-DD HH:MM:SS.', raw, v.label))
            else:
                v.value_char = raw

    def _set_python_value(self, value):
        """Coerce an arbitrary Python/ORM value into the right typed column."""
        self.ensure_one()
        t = self.field_type
        if t == 'boolean':
            self.value_boolean = bool(value)
        elif t in ('number', 'monetary'):
            try:
                self.value_number = float(value)
            except (TypeError, ValueError):
                self.value_char = self._as_text(value)
        elif t == 'date':
            try:
                self.value_date = fields.Date.to_date(value)
            except (TypeError, ValueError):
                self.value_char = self._as_text(value)
        elif t == 'datetime':
            try:
                self.value_datetime = fields.Datetime.to_datetime(value)
            except (TypeError, ValueError):
                self.value_char = self._as_text(value)
        elif t == 'signature':
            pass  # signatures are captured, not mapped
        else:
            self.value_char = self._as_text(value)

    @staticmethod
    def _as_text(value):
        if hasattr(value, 'display_name'):
            return value.display_name
        if value in (False, None):
            return ''
        return str(value)
