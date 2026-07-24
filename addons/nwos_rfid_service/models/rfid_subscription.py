from collections import defaultdict

from dateutil.relativedelta import relativedelta

from nwos import api, fields, models, Command, _
from nwos.exceptions import UserError


class RfidSubscription(models.Model):
    _name = 'rfid.subscription'
    _description = 'Nextwaves Kit Subscription'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(required=True, readonly=True, copy=False,
                       default=lambda self: _('New'), index=True)
    site_id = fields.Many2one(
        'rfid.service.site', required=True, ondelete='cascade', index=True,
        tracking=True)
    partner_id = fields.Many2one(
        related='site_id.partner_id', store=True, index=True)
    company_id = fields.Many2one(
        related='site_id.company_id', store=True, index=True)
    source_sale_line_id = fields.Many2one(
        'sale.order.line', required=True, ondelete='restrict', index=True)
    product_id = fields.Many2one(
        related='source_sale_line_id.product_id', store=True)
    currency_id = fields.Many2one(
        related='source_sale_line_id.currency_id', store=True)
    price_unit = fields.Monetary(required=True, currency_field='currency_id')
    discount = fields.Float()
    tax_ids = fields.Many2many('account.tax', string='Taxes')
    payment_term_id = fields.Many2one('account.payment.term')
    billing_interval_months = fields.Integer(required=True, default=1)
    start_date = fields.Date(readonly=True, tracking=True)
    next_invoice_date = fields.Date(readonly=True, tracking=True, index=True)
    state = fields.Selection([
        ('pending', 'Pending Activation'),
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('closed', 'Closed'),
    ], default='pending', required=True, tracking=True, index=True)
    collection_state = fields.Selection([
        ('current', 'Current'), ('overdue', 'Overdue')
    ], compute='_compute_collection_state', search='_search_collection_state')
    period_ids = fields.One2many(
        'rfid.subscription.period', 'subscription_id', string='Billing Periods')
    invoice_count = fields.Integer(compute='_compute_invoice_count')
    mrr = fields.Monetary(compute='_compute_mrr', currency_field='currency_id')

    _positive_interval = models.Constraint(
        'CHECK(billing_interval_months IN (1, 3, 6, 12))',
        'Billing interval must be 1, 3, 6 or 12 months.',
    )
    _source_line_unique = models.Constraint(
        'UNIQUE(source_sale_line_id)',
        'A Nextwaves Kit subscription already exists for this sales order line.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'rfid.subscription') or _('New')
        return super().create(vals_list)

    @api.model
    def create_from_sale_line(self, line):
        existing = self.search([('source_sale_line_id', '=', line.id)], limit=1)
        if existing:
            return existing
        interval = int(line.product_template_id.rfid_billing_interval_months or '1')
        return self.create({
            'site_id': line.rfid_site_id.id,
            'source_sale_line_id': line.id,
            'price_unit': line.price_unit,
            'discount': line.discount,
            'tax_ids': [Command.set(line.tax_ids.ids)],
            'payment_term_id': line.order_id.payment_term_id.id,
            'billing_interval_months': interval,
        })

    @api.depends('period_ids.invoice_line_id.move_id.payment_state',
                 'period_ids.invoice_line_id.move_id.invoice_date_due')
    def _compute_collection_state(self):
        today = fields.Date.context_today(self)
        for subscription in self:
            invoices = subscription.period_ids.invoice_line_id.move_id.filtered(
                lambda move: move.state == 'posted'
                and move.payment_state not in ('paid', 'reversed')
                and move.invoice_date_due and move.invoice_date_due < today
            )
            subscription.collection_state = 'overdue' if invoices else 'current'

    @api.model
    def _search_collection_state(self, operator, value):
        if operator not in ('=', '!=') or value not in ('current', 'overdue'):
            raise UserError(_('Unsupported collection status search.'))
        overdue_ids = self.env['rfid.subscription.period'].search([
            ('invoice_line_id.move_id.state', '=', 'posted'),
            ('invoice_line_id.move_id.payment_state', 'not in', ('paid', 'reversed')),
            ('invoice_line_id.move_id.invoice_date_due', '<', fields.Date.context_today(self)),
        ]).subscription_id.ids
        wants_overdue = (operator == '=' and value == 'overdue') or (
            operator == '!=' and value == 'current')
        return [('id', 'in' if wants_overdue else 'not in', overdue_ids)]

    @api.depends('period_ids.invoice_line_id')
    def _compute_invoice_count(self):
        for subscription in self:
            subscription.invoice_count = len(subscription.period_ids.invoice_line_id.move_id)

    @api.depends('price_unit')
    def _compute_mrr(self):
        for subscription in self:
            subscription.mrr = subscription.price_unit

    def action_activate(self, start_date=None):
        start_date = fields.Date.to_date(start_date or fields.Date.context_today(self))
        for subscription in self:
            if subscription.site_id.state != 'active':
                raise UserError(_('The installation site must be active before activating its subscription.'))
            subscription.write({
                'state': 'active',
                'start_date': start_date,
                'next_invoice_date': start_date,
            })
        periods = self._generate_due_periods(today=start_date)
        periods._create_grouped_invoices()
        return True

    def action_pause(self):
        self.filtered(lambda sub: sub.state == 'active').state = 'paused'
        return True

    def action_resume(self):
        self.filtered(lambda sub: sub.state == 'paused').state = 'active'
        return True

    def action_close(self):
        self.write({'state': 'closed', 'next_invoice_date': False})
        return True

    def _generate_due_periods(self, today=None):
        today = fields.Date.to_date(today or fields.Date.context_today(self))
        Period = self.env['rfid.subscription.period']
        result = Period
        for subscription in self.filtered(
                lambda sub: sub.state == 'active' and sub.next_invoice_date):
            next_date = subscription.next_invoice_date
            iterations = 0
            while next_date <= today and iterations < 24:
                period = Period.search([
                    ('subscription_id', '=', subscription.id),
                    ('date_start', '=', next_date),
                ], limit=1)
                date_end = next_date + relativedelta(
                    months=subscription.billing_interval_months, days=-1)
                if not period:
                    period = Period.create({
                        'subscription_id': subscription.id,
                        'date_start': next_date,
                        'date_end': date_end,
                        'billing_months': subscription.billing_interval_months,
                        'state': 'due',
                    })
                result |= period
                next_date += relativedelta(months=subscription.billing_interval_months)
                iterations += 1
            subscription.next_invoice_date = next_date
        return result.filtered(lambda period: period.state == 'due')

    @api.model
    def _cron_generate_invoices(self):
        canceled = self.env['rfid.subscription.period'].search([
            ('state', '=', 'invoiced'), ('invoice_line_id.move_id.state', '=', 'cancel')
        ], limit=500)
        canceled.write({'state': 'due', 'invoice_line_id': False})
        due_subscriptions = self.search([
            ('state', '=', 'active'),
            ('next_invoice_date', '<=', fields.Date.context_today(self)),
        ], limit=1000)
        periods = due_subscriptions._generate_due_periods()
        periods._create_grouped_invoices()
        self._schedule_overdue_activities()

    def _schedule_overdue_activities(self):
        overdue = self.filtered(lambda sub: sub.collection_state == 'overdue')
        activity_type = self.env.ref('mail.mail_activity_data_todo')
        for subscription in overdue:
            if not subscription.activity_ids.filtered(
                    lambda activity: activity.activity_type_id == activity_type):
                subscription.activity_schedule(
                    activity_type.id,
                    summary=_('Overdue Nextwaves Kit subscription invoice'),
                    user_id=subscription.source_sale_line_id.order_id.user_id.id or self.env.user.id,
                )

    def action_view_invoices(self):
        self.ensure_one()
        invoices = self.period_ids.invoice_line_id.move_id
        action = self.env['ir.actions.actions']._for_xml_id('account.action_move_out_invoice_type')
        action['domain'] = [('id', 'in', invoices.ids)]
        return action


class RfidSubscriptionPeriod(models.Model):
    _name = 'rfid.subscription.period'
    _description = 'Nextwaves Kit Subscription Billing Period'
    _order = 'date_start desc, id desc'

    subscription_id = fields.Many2one(
        'rfid.subscription', required=True, ondelete='cascade', index=True)
    site_id = fields.Many2one(related='subscription_id.site_id', store=True, index=True)
    company_id = fields.Many2one(related='subscription_id.company_id', store=True)
    currency_id = fields.Many2one(related='subscription_id.currency_id', store=True)
    date_start = fields.Date(required=True, index=True)
    date_end = fields.Date(required=True)
    billing_months = fields.Integer(required=True)
    state = fields.Selection([
        ('due', 'Due'), ('invoiced', 'Invoiced'), ('cancelled', 'Cancelled')
    ], default='due', required=True, index=True)
    invoice_line_id = fields.Many2one(
        'account.move.line', copy=False, readonly=True, ondelete='set null')
    invoice_id = fields.Many2one(
        related='invoice_line_id.move_id', string='Invoice', store=True)
    amount = fields.Monetary(compute='_compute_amount', currency_field='currency_id')

    _period_unique = models.Constraint(
        'UNIQUE(subscription_id, date_start)',
        'A subscription billing period already exists for this date.',
    )

    @api.depends('subscription_id.price_unit', 'subscription_id.discount', 'billing_months')
    def _compute_amount(self):
        for period in self:
            gross = period.subscription_id.price_unit * period.billing_months
            period.amount = gross * (1 - period.subscription_id.discount / 100.0)

    def _create_grouped_invoices(self):
        due = self.filtered(lambda period: period.state == 'due' and not period.invoice_line_id)
        groups = defaultdict(lambda: self.env['rfid.subscription.period'])
        for period in due:
            subscription = period.subscription_id
            key = (
                subscription.company_id.id,
                subscription.partner_id.commercial_partner_id.id,
                subscription.currency_id.id,
                subscription.payment_term_id.id,
            )
            groups[key] |= period
        for (company_id, partner_id, currency_id, payment_term_id), periods in groups.items():
            commands = []
            for period in periods.sorted(lambda rec: (rec.site_id.name, rec.date_start)):
                subscription = period.subscription_id
                commands.append(Command.create({
                    'product_id': subscription.product_id.id,
                    'name': _(
                        '%(plan)s - %(site)s (%(start)s to %(end)s)',
                        plan=subscription.product_id.display_name,
                        site=subscription.site_id.display_name,
                        start=period.date_start,
                        end=period.date_end,
                    ),
                    'quantity': period.billing_months,
                    'price_unit': subscription.price_unit,
                    'discount': subscription.discount,
                    'tax_ids': [Command.set(subscription.tax_ids.ids)],
                    'rfid_subscription_period_id': period.id,
                }))
            invoice = self.env['account.move'].with_company(company_id).create({
                'move_type': 'out_invoice',
                'company_id': company_id,
                'partner_id': partner_id,
                'currency_id': currency_id,
                'invoice_date': fields.Date.context_today(self),
                'invoice_payment_term_id': payment_term_id or False,
                'invoice_origin': ', '.join(periods.subscription_id.source_sale_line_id.order_id.mapped('name')),
                'invoice_line_ids': commands,
            })
            for line in invoice.invoice_line_ids.filtered('rfid_subscription_period_id'):
                line.rfid_subscription_period_id.write({
                    'invoice_line_id': line.id,
                    'state': 'invoiced',
                })
        return True
