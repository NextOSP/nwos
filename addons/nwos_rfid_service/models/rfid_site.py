from nwos import api, fields, models, _
from nwos.exceptions import UserError, ValidationError
from nwos.addons.project.models.project_task import CLOSED_STATES


SITE_STATES = [
    ('draft', 'Draft Order'),
    ('awaiting_payment', 'Awaiting Payment'),
    ('ready', 'Ready'),
    ('in_delivery', 'In Delivery'),
    ('in_installation', 'In Installation'),
    ('awaiting_acceptance', 'Awaiting Acceptance'),
    ('active', 'Active'),
    ('suspended', 'Suspended'),
    ('closed', 'Closed'),
    ('cancelled', 'Cancelled'),
]


class RfidServiceSite(models.Model):
    _name = 'rfid.service.site'
    _description = 'Nextwaves Kit Installation Site'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(
        string='Site Reference', required=True, readonly=True, copy=False,
        default=lambda self: _('New'), index=True)
    site_name = fields.Char(string='Site Name', required=True, tracking=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company,
        index=True)
    partner_id = fields.Many2one(
        'res.partner', string='Customer', required=True, tracking=True,
        index=True)
    contact_id = fields.Many2one('res.partner', string='Site Contact')
    installation_address_id = fields.Many2one(
        'res.partner', string='Installation and Delivery Address', required=True,
        tracking=True)
    sale_order_id = fields.Many2one(
        'sale.order', string='Quotation or Sales Order', required=True,
        ondelete='cascade', index=True)
    sale_line_ids = fields.One2many(
        'sale.order.line', 'rfid_site_id', string='Assigned Order Lines')
    kit_sale_line_ids = fields.Many2many(
        'sale.order.line', compute='_compute_assigned_lines',
        string='Kit Items')
    kit_product_ids = fields.Many2many(
        'product.product', compute='_compute_assigned_lines',
        string='Kit Products')
    state = fields.Selection(
        SITE_STATES, default='draft', required=True, tracking=True,
        index=True)

    requested_delivery_date = fields.Datetime(string='Requested Delivery Date')
    planned_delivery_date = fields.Datetime(
        string='Promised Delivery Date', required=True, tracking=True)
    actual_delivery_date = fields.Datetime(
        string='Actual Delivery Date', compute='_compute_delivery_data')
    planned_installation_date = fields.Datetime(
        string='Planned Installation Date', required=True, tracking=True)
    activation_date = fields.Date(string='Activation Date', readonly=True, tracking=True)

    target_read_rate = fields.Float(string='Target Read Rate (%)', default=95.0)
    actual_read_rate = fields.Float(string='Actual Read Rate (%)')

    installation_project_id = fields.Many2one(
        'project.project', copy=False, readonly=True)
    project_template_id = fields.Many2one(
        'project.project', string='Project Template', copy=True,
        domain="[('is_template', '=', True)]",
        help='Template used to create this site project, including its tasks, '
             'subtasks, and checklist content. Kit Item defaults are suggested '
             'automatically and can be overridden before confirmation.')
    project_template_manual = fields.Boolean(copy=True, default=False)
    project_template_conflict = fields.Boolean(
        compute='_compute_project_template_conflict')
    payment_released = fields.Boolean(
        string='Kit Payment Released', readonly=True, copy=False, tracking=True)
    payment_blocked = fields.Boolean(
        compute='_compute_payment_blocked', store=True)
    kit_payment_state = fields.Selection([
        ('not_invoiced', 'Not Invoiced'),
        ('unpaid', 'Unpaid'),
        ('partial', 'Partially Paid'),
        ('paid', 'Paid'),
    ], compute='_compute_kit_payment_state')

    picking_ids = fields.One2many('stock.picking', 'rfid_site_id', string='Site Deliveries')
    picking_count = fields.Integer(compute='_compute_counts')
    ticket_ids = fields.One2many('helpdesk.ticket', 'rfid_site_id', string='Helpdesk Tickets')
    ticket_count = fields.Integer(compute='_compute_counts')
    subscription_ids = fields.One2many(
        'rfid.subscription', 'site_id', string='Subscriptions')
    subscription_count = fields.Integer(compute='_compute_counts')
    installed_lot_ids = fields.Many2many(
        'stock.lot', compute='_compute_installed_lots', string='Installed Serials / Lots')

    delivery_completed = fields.Boolean(compute='_compute_delivery_data')
    configuration_tested = fields.Boolean(string='Configuration / Connectivity Tested')
    training_completed = fields.Boolean(string='Customer Training Completed')
    commissioning_notes = fields.Text()
    acceptance_photo_ids = fields.Many2many(
        'ir.attachment', 'rfid_site_acceptance_attachment_rel',
        'site_id', 'attachment_id', string='Acceptance Photos / Documents')
    accepted_by = fields.Char(string='Accepted By')
    acceptance_signature = fields.Image(string='Customer Signature', max_width=1024, max_height=512)
    accepted_on = fields.Datetime(string='Accepted On', readonly=True)

    _read_rate_range = models.Constraint(
        'CHECK(target_read_rate >= 0 AND target_read_rate <= 100 '
        'AND actual_read_rate >= 0 AND actual_read_rate <= 100)',
        'Read rates must be between 0 and 100 percent.',
    )

    @api.depends(
        'payment_released',
        'state',
        'company_id.rfid_require_payment_before_delivery',
    )
    def _compute_payment_blocked(self):
        for site in self:
            site.payment_blocked = bool(
                site.state not in ('draft', 'cancelled', 'closed')
                and site.company_id.rfid_require_payment_before_delivery
                and not site.payment_released
            )

    @api.depends('sale_line_ids.rfid_line_role', 'sale_line_ids.product_id')
    def _compute_assigned_lines(self):
        for site in self:
            lines = site.sale_line_ids.filtered(
                lambda line: line.rfid_line_role == 'starter_kit')
            site.kit_sale_line_ids = lines
            site.kit_product_ids = lines.product_id

    @api.depends(
        'sale_line_ids.rfid_line_role',
        'sale_line_ids.product_template_id.rfid_project_template_id',
        'project_template_manual',
    )
    def _compute_project_template_conflict(self):
        for site in self:
            candidates = site.kit_sale_line_ids.mapped(
                'product_template_id.rfid_project_template_id')
            site.project_template_conflict = bool(
                len(candidates) > 1 and not site.project_template_manual)

    def _automatic_project_template(self):
        self.ensure_one()
        candidates = self.kit_sale_line_ids.mapped(
            'product_template_id.rfid_project_template_id')
        if len(candidates) == 1:
            return candidates
        if len(candidates) > 1:
            return self.env['project.project']
        return self.company_id.rfid_project_template_id

    def _sync_project_template_from_kit_lines(self):
        for site in self.filtered(
                lambda record: not record.installation_project_id
                and not record.project_template_manual):
            template = site._automatic_project_template()
            if site.project_template_id != template:
                site.with_context(nextwaves_auto_project_template=True).write({
                    'project_template_id': template.id,
                })
        return True

    def _get_kit_invoices(self):
        self.ensure_one()
        return self.kit_sale_line_ids.invoice_lines.move_id.filtered(
            lambda move: move.move_type in ('out_invoice', 'out_refund')
            and move.state != 'cancel'
        )

    def _get_kit_payment_state(self):
        self.ensure_one()
        lines = self.kit_sale_line_ids
        if not lines:
            return 'not_invoiced'
        invoices = self._get_kit_invoices()
        posted = invoices.filtered(lambda move: move.state == 'posted')
        if not posted or not any(line.qty_invoiced > 0 for line in lines):
            return 'not_invoiced'
        if any(line.qty_invoiced < line.product_uom_qty for line in lines):
            return 'partial'
        if all(move.payment_state == 'paid' for move in posted):
            return 'paid'
        if any(move.payment_state in ('partial', 'in_payment', 'paid') for move in posted):
            return 'partial'
        return 'unpaid'

    def _compute_kit_payment_state(self):
        for site in self:
            site.kit_payment_state = site._get_kit_payment_state()

    @api.depends('picking_ids.state', 'picking_ids.date_done')
    def _compute_delivery_data(self):
        for site in self:
            outgoing = site.picking_ids.filtered(
                lambda picking: picking.picking_type_id.code == 'outgoing'
                and picking.state != 'cancel'
            )
            site.delivery_completed = bool(outgoing) and all(
                picking.state == 'done' for picking in outgoing)
            done_dates = outgoing.filtered('date_done').mapped('date_done')
            site.actual_delivery_date = max(done_dates) if done_dates else False

    @api.depends('picking_ids', 'ticket_ids', 'subscription_ids')
    def _compute_counts(self):
        for site in self:
            site.picking_count = len(site.picking_ids)
            site.ticket_count = len(site.ticket_ids)
            site.subscription_count = len(site.subscription_ids)

    @api.depends('picking_ids.state', 'picking_ids.move_ids.move_line_ids.lot_id')
    def _compute_installed_lots(self):
        for site in self:
            outbound_lines = site.picking_ids.filtered(
                lambda picking: picking.state == 'done'
                and picking.picking_type_id.code == 'outgoing'
            ).move_ids.move_line_ids.filtered('lot_id')
            returned_lines = site.picking_ids.filtered(
                lambda picking: picking.state == 'done'
                and picking.picking_type_id.code == 'incoming'
            ).move_ids.move_line_ids.filtered('lot_id')
            site.installed_lot_ids = outbound_lines.lot_id - returned_lines.lot_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('partner_id') and vals.get('sale_order_id'):
                vals['partner_id'] = self.env['sale.order'].browse(
                    vals['sale_order_id']
                ).partner_id.id
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'rfid.service.site') or _('New')
            if vals.get('project_template_id'):
                vals['project_template_manual'] = True
        sites = super().create(vals_list)
        sites._validate_order_consistency()
        sites._sync_project_template_from_kit_lines()
        return sites

    def write(self, vals):
        if any(site.sale_order_id.state not in ('draft', 'sent') for site in self) and any(
                key in vals for key in (
                    'sale_order_id', 'installation_address_id', 'project_template_id')):
            raise UserError(_('Core site allocation fields cannot be changed after order confirmation.'))
        template_changed_manually = (
            'project_template_id' in vals
            and not self.env.context.get('nextwaves_auto_project_template')
        )
        if template_changed_manually:
            vals['project_template_manual'] = bool(vals['project_template_id'])
        result = super().write(vals)
        self._validate_order_consistency()
        if template_changed_manually and not vals['project_template_manual']:
            self._sync_project_template_from_kit_lines()
        return result

    def _validate_order_consistency(self):
        for site in self:
            if site.partner_id.commercial_partner_id != site.sale_order_id.partner_id.commercial_partner_id:
                raise ValidationError(_('The site customer must match the quotation customer.'))
            if site.installation_address_id.commercial_partner_id != site.partner_id.commercial_partner_id:
                raise ValidationError(_('The installation address must belong to the site customer.'))
            if site.project_template_id and not site.project_template_id.is_template:
                raise ValidationError(_('The selected project is not a project template.'))
            if (site.project_template_id.company_id
                    and site.project_template_id.company_id != site.company_id):
                raise ValidationError(_(
                    'The project template must belong to the same company as the installation site.'))

    def _create_installation_project(self):
        for site in self.filtered(lambda record: not record.installation_project_id):
            template = site.project_template_id
            if not template:
                raise UserError(_(
                    'Select a project template for the installation site %s.',
                    site.site_name,
                ))
            values = {
                'name': _('%(order)s - %(site)s', order=site.sale_order_id.name,
                          site=site.site_name),
                'partner_id': site.partner_id.id,
                'company_id': site.company_id.id,
                'rfid_site_id': site.id,
                'date_start': fields.Date.context_today(site),
                'date': fields.Date.to_date(site.planned_installation_date),
            }
            project = template.action_create_from_template(values)
            if not project.account_id:
                project._create_analytic_account()
            project.task_ids.write({
                'rfid_site_id': site.id,
                'partner_id': site.partner_id.id,
                'state': '04_waiting_normal',
            })
            site.installation_project_id = project

    def _refresh_payment_release(self):
        for site in self.filtered(lambda record: not record.payment_released):
            payment_required = (
                site.company_id.rfid_require_payment_before_delivery
            )
            if payment_required and site._get_kit_payment_state() != 'paid':
                continue
            site.write({'payment_released': True, 'state': 'ready'})
            first_tasks = site.installation_project_id.task_ids.filtered(
                lambda task: task.rfid_task_kind == 'delivery')
            first_tasks.write({'state': '01_in_progress'})
            if payment_required:
                message = _(
                    'Kit payment verified; delivery and installation released.')
            else:
                message = _(
                    'Kit payment is not required; delivery and installation released.')
            site.message_post(body=message)
        return True

    @api.model
    def _cron_refresh_payment_release(self):
        sites = self.search([
            ('state', '=', 'awaiting_payment'), ('payment_released', '=', False)
        ], limit=500)
        sites._refresh_payment_release()

    def action_refresh_payment(self):
        self._refresh_payment_release()
        return True

    def action_accept_installation(self):
        for site in self:
            if site.payment_blocked:
                raise UserError(_('Kit payment has not been released.'))
            if not site.delivery_completed:
                raise UserError(_('Complete all site deliveries before acceptance.'))
            if site.installation_project_id.task_ids.filtered(
                    lambda task: task.rfid_task_kind != 'acceptance'
                    and task.state not in CLOSED_STATES):
                raise UserError(_('Complete all implementation tasks before acceptance.'))
            tracked_products = site.picking_ids.move_ids.product_id.filtered(
                lambda product: product.tracking == 'serial')
            installed_products = site.installed_lot_ids.product_id
            if tracked_products - installed_products:
                raise UserError(_('Record all required device serial numbers on the site delivery.'))
            if not site.configuration_tested or not site.training_completed:
                raise UserError(_('Complete configuration testing and customer training.'))
            if site.actual_read_rate < site.target_read_rate:
                raise UserError(_('The actual RFID read rate is below the approved target.'))
            if not site.acceptance_signature or not site.accepted_by:
                raise UserError(_('Capture the customer name and signature before acceptance.'))
            site.write({
                'state': 'active',
                'activation_date': fields.Date.context_today(site),
                'accepted_on': fields.Datetime.now(),
            })
            site.subscription_ids.filtered(
                lambda subscription: subscription.state == 'pending'
            ).action_activate(site.activation_date)
            acceptance_tasks = site.installation_project_id.task_ids.filtered(
                lambda task: task.rfid_task_kind == 'acceptance'
            )
            acceptance_tasks.filtered(
                lambda task: task.state not in CLOSED_STATES
            ).write({'state': '1_done'})
            site.message_post(body=_('Installation accepted and site activated.'))
        return True

    def action_print_acceptance(self):
        return self.env.ref(
            'nwos_rfid_service.action_report_rfid_acceptance'
        ).report_action(self)

    def action_view_pickings(self):
        return self._linked_action('stock.action_picking_tree_all', 'stock.picking', self.picking_ids)

    def action_view_project(self):
        self.ensure_one()
        if not self.installation_project_id:
            return False
        return {
            'type': 'ir.actions.act_window', 'name': _('Installation Project'),
            'res_model': 'project.project', 'res_id': self.installation_project_id.id,
            'view_mode': 'form', 'target': 'current',
        }

    def action_view_tickets(self):
        return self._linked_action('helpdesk.action_helpdesk_ticket_all', 'helpdesk.ticket', self.ticket_ids,
                                   {'default_rfid_site_id': self.id, 'default_partner_id': self.partner_id.id})

    def action_view_subscriptions(self):
        return self._linked_action('nwos_rfid_service.action_rfid_subscription', 'rfid.subscription', self.subscription_ids,
                                   {'default_site_id': self.id})

    def _linked_action(self, xmlid, model, records, context=None):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id(xmlid)
        action['domain'] = [('id', 'in', records.ids)]
        action['context'] = context or {}
        if len(records) == 1:
            action.update({'view_mode': 'form', 'res_id': records.id, 'views': [(False, 'form')]})
        return action
