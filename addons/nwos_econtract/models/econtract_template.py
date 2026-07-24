# -*- coding: utf-8 -*-
import re

from lxml import html as lhtml

from nwos import _, api, fields, models

# ---------------------------------------------------------------------------
# Placeholder parsing helpers (shared with econtract.contract rendering)
# ---------------------------------------------------------------------------
# Matches {{ Label }} or {{ Label : type }}.  The label part forbids ':' and
# braces so nested/adjacent placeholders don't get swallowed.
PLACEHOLDER_RE = re.compile(r'\{\{\s*([^{}:]+?)\s*(?::\s*([^{}]+?)\s*)?\}\}')

TYPE_ALIASES = {
    'text': 'text', 'string': 'text', 'char': 'text', 'str': 'text',
    'number': 'number', 'num': 'number', 'int': 'number', 'integer': 'number',
    'float': 'number', 'decimal': 'number', 'amount': 'number',
    'qty': 'number', 'quantity': 'number',
    'money': 'monetary', 'monetary': 'monetary', 'currency': 'monetary', 'price': 'monetary',
    'date': 'date', 'day': 'date',
    'datetime': 'datetime', 'time': 'datetime',
    'bool': 'boolean', 'boolean': 'boolean', 'checkbox': 'boolean',
    'yesno': 'boolean', 'check': 'boolean',
    'sign': 'signature', 'signature': 'signature', 'esign': 'signature',
}

FIELD_TYPES = [
    ('text', 'Text'),
    ('number', 'Number'),
    ('monetary', 'Monetary'),
    ('date', 'Date'),
    ('datetime', 'Date & Time'),
    ('boolean', 'Yes / No'),
    ('signature', 'Signature'),
]


def slugify_key(label):
    """Turn a human label into a stable field key: 'Customer Name' -> 'customer_name'."""
    key = re.sub(r'[^0-9a-zA-Z]+', '_', (label or '').strip().lower()).strip('_')
    return key or 'field'


def normalize_type(raw, key=None):
    if raw:
        return TYPE_ALIASES.get(raw.strip().lower(), 'text')
    # No explicit type: infer signature from a telling key, otherwise text.
    if key in ('signature', 'sign', 'esign'):
        return 'signature'
    return 'text'


def parse_placeholders(body, typed_only=False):
    """Return an ordered list of unique {key,label,type} dicts found in *body*.

    With *typed_only* (Jinja2 templates), only ``{{Label:type}}`` placeholders
    become smart fields; untyped ``{{ ... }}`` are left to the Jinja2 engine.
    """
    result, seen = [], set()
    for m in PLACEHOLDER_RE.finditer(body or ''):
        if typed_only and not m.group(2):
            continue
        label = (m.group(1) or '').strip()
        key = slugify_key(label)
        if key in seen:
            continue
        seen.add(key)
        result.append({
            'key': key,
            'label': label or key,
            'type': normalize_type(m.group(2), key),
        })
    return result


def convert_pasted_source(body):
    """If *body* is HTML source pasted as plain text into the visual editor
    (tags displayed literally, i.e. escaped), return the decoded HTML;
    otherwise return *body* unchanged.

    Heuristic: the visible text of the body starts with a '<tag' and contains
    closing tags — no real document reads like that.
    """
    if not body or '&lt;' not in body:
        return body
    try:
        text = lhtml.fromstring('<div>%s</div>' % body).text_content().strip()
    except Exception:  # noqa: BLE001 - malformed input: keep as-is
        return body
    if re.match(r'<[a-zA-Z]', text) and re.search(r'</[a-zA-Z]+>', text):
        return text
    return body


class EContractTemplate(models.Model):
    _name = 'econtract.template'
    _description = 'eContract Template'
    _inherit = ['mail.thread']
    _order = 'name'

    name = fields.Char('Template Name', required=True, tracking=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company)
    note = fields.Char('Internal Note')
    engine = fields.Selection([
        ('placeholder', 'Smart Fields'),
        ('jinja2', 'Jinja2'),
    ], string='Template Engine', default='placeholder', required=True, tracking=True,
        help="Smart Fields: only {{Label}} / {{Label:type}} placeholders, filled per "
             "contract.\n"
             "Jinja2: full Jinja2 syntax with access to the source document — "
             "expressions like {{ object.amount_total }}, {% for line in "
             "object.order_line %} loops, {% if %} conditions. {{Label:type}} smart "
             "fields still work and stay hand-fillable.")
    body_html = fields.Html(
        'Contract Body', sanitize=True, sanitize_style=True,
        help="Write the document and drop {{Smart Fields}} where values should go. "
             "Use {{Label:type}} to type a field, e.g. {{Sign Date:date}}.")
    field_ids = fields.One2many(
        'econtract.template.field', 'template_id', string='Detected Fields',
        copy=True)
    field_count = fields.Integer(compute='_compute_field_count')
    contract_count = fields.Integer(compute='_compute_contract_count')

    def _compute_field_count(self):
        for tmpl in self:
            tmpl.field_count = len(tmpl.field_ids)

    def _compute_contract_count(self):
        data = self.env['econtract.contract']._read_group(
            [('template_id', 'in', self.ids)], ['template_id'], ['__count'])
        mapping = {t.id: c for t, c in data}
        for tmpl in self:
            tmpl.contract_count = mapping.get(tmpl.id, 0)

    # -- field detection ----------------------------------------------------
    def _sync_fields(self):
        """Reconcile field_ids with the placeholders currently in body_html.
        Adds new keys, drops removed ones, keeps user-tuned type/label/mapping
        for keys that still exist."""
        for tmpl in self:
            parsed = parse_placeholders(tmpl.body_html, typed_only=tmpl.engine == 'jinja2')
            keys = [p['key'] for p in parsed]
            existing = {f.name: f for f in tmpl.field_ids}
            commands, seq = [], 10
            for p in parsed:
                found = existing.get(p['key'])
                if found:
                    commands.append((1, found.id, {'sequence': seq}))
                else:
                    commands.append((0, 0, {
                        'name': p['key'],
                        'label': p['label'],
                        'field_type': p['type'],
                        'sequence': seq,
                    }))
                seq += 10
            for name, found in existing.items():
                if name not in keys:
                    commands.append((2, found.id))
            if commands:
                tmpl.with_context(econtract_syncing=True).write({'field_ids': commands})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('body_html'):
                vals['body_html'] = convert_pasted_source(vals['body_html'])
        records = super().create(vals_list)
        records._sync_fields()
        return records

    def write(self, vals):
        if vals.get('body_html'):
            vals['body_html'] = convert_pasted_source(vals['body_html'])
        res = super().write(vals)
        if not self.env.context.get('econtract_syncing') and \
                ('body_html' in vals or 'engine' in vals):
            self._sync_fields()
        return res

    def action_detect_fields(self):
        self._sync_fields()
        return True

    def action_view_contracts(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Contracts'),
            'res_model': 'econtract.contract',
            'view_mode': 'list,form',
            'domain': [('template_id', '=', self.id)],
            'context': {'default_template_id': self.id},
        }

    def action_new_contract(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Contract'),
            'res_model': 'econtract.contract',
            'view_mode': 'form',
            'target': 'current',
            'context': {'default_template_id': self.id},
        }


class EContractTemplateField(models.Model):
    _name = 'econtract.template.field'
    _description = 'eContract Template Field'
    _order = 'sequence, id'

    template_id = fields.Many2one(
        'econtract.template', string='Template', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(
        'Key', required=True,
        help="Placeholder key as it appears in the body, e.g. customer_name.")
    label = fields.Char('Label', required=True)
    field_type = fields.Selection(FIELD_TYPES, string='Type', required=True, default='text')
    required = fields.Boolean('Required')
    default_value = fields.Char('Default Value')
    mapping = fields.Char(
        'Auto-fill Path',
        help="Dotted path on the source record to pre-fill this field, "
             "e.g. partner_id.name, amount_total, date_order. Leave empty to fill by hand.")

    _sql_constraints = [
        ('key_uniq', 'unique(template_id, name)',
         'A field key must be unique within a template.'),
    ]
