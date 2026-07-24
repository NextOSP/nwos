from datetime import timedelta

from nwos import api, fields, models, _
from nwos.exceptions import UserError, ValidationError


LINE_ROLES = [
    ('standard', 'Normal Item'),
    ('starter_kit', 'Kit Item'),
    ('subscription', 'Subscription'),
]


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    rfid_site_ids = fields.One2many(
        'rfid.service.site', 'sale_order_id', string='Nextwaves Kit Sites',
        copy=True)
    rfid_site_count = fields.Integer(compute='_compute_rfid_site_count')
    has_rfid_starter_kit = fields.Boolean(
        string='Has Nextwaves Kit', compute='_compute_has_rfid_starter_kit')

    @api.depends('rfid_site_ids')
    def _compute_rfid_site_count(self):
        for order in self:
            order.rfid_site_count = len(order.rfid_site_ids)

    @api.depends('order_line.rfid_line_role')
    def _compute_has_rfid_starter_kit(self):
        for order in self:
            order.has_rfid_starter_kit = any(
                line.rfid_line_role == 'starter_kit'
                for line in order.order_line if not line.display_type)

    def _validate_rfid_confirmation(self):
        for order in self:
            kit_lines = order.order_line.filtered(
                lambda line: not line.display_type
                and line.rfid_line_role == 'starter_kit')
            if kit_lines and not order.rfid_site_ids:
                raise UserError(_(
                    'Create at least one installation site on the sales order.'))
            for line in kit_lines:
                if not line.rfid_site_id:
                    raise UserError(_(
                        "Assign Kit Item '%s' to an installation site.",
                        line.product_id.display_name))
            empty_sites = order.rfid_site_ids.filtered(
                lambda site: not site.kit_sale_line_ids)
            if empty_sites:
                raise UserError(_(
                    'Each installation site must have at least one order line marked as a Kit Item: %s',
                    ', '.join(empty_sites.mapped('site_name'))))
            if any(not site.planned_delivery_date or not site.planned_installation_date
                   for site in order.rfid_site_ids):
                raise UserError(_(
                    'Enter the promised delivery date and planned installation date for every installation site.'))
            order.rfid_site_ids._sync_project_template_from_kit_lines()
            conflicting_sites = order.rfid_site_ids.filtered(
                'project_template_conflict')
            if conflicting_sites:
                raise UserError(_(
                    'Kit Items suggest different project templates for these '
                    'sites: %s. Select one project template for each site.',
                    ', '.join(conflicting_sites.mapped('site_name')),
                ))
            missing_templates = order.rfid_site_ids.filtered(
                lambda site: not site.project_template_id)
            if missing_templates:
                raise UserError(_(
                    'Select a project template for these installation sites: %s.',
                    ', '.join(missing_templates.mapped('site_name')),
                ))

            subscription_lines = order.order_line.filtered(
                lambda line: not line.display_type
                and line.rfid_line_role == 'subscription')
            for line in subscription_lines:
                if not line.rfid_site_id or line.rfid_site_id.sale_order_id != order:
                    raise UserError(_(
                        'Assign every Subscription line to an installation site on this sales order.'))
                if line.product_uom_qty != 1:
                    raise UserError(_('Use one Subscription line per installation site.'))

            assigned_lines = order.order_line.filtered('rfid_site_id')
            if any(line.rfid_site_id.sale_order_id != order for line in assigned_lines):
                raise ValidationError(_(
                    'An order line can only target a site on the same sales order.'))

    def action_confirm(self):
        self._validate_rfid_confirmation()
        result = super().action_confirm()
        for order in self:
            for site in order.rfid_site_ids:
                site._create_installation_project()
                site.write({'state': 'awaiting_payment', 'payment_released': False})
                if not site.company_id.rfid_require_payment_before_delivery:
                    site._refresh_payment_release()
                site.picking_ids.write({'project_id': site.installation_project_id.id})
            for line in order.order_line.filtered(
                    lambda record: not record.display_type
                    and record.rfid_line_role == 'subscription'):
                self.env['rfid.subscription'].sudo().create_from_sale_line(line)
        return result

    def _action_cancel(self):
        result = super()._action_cancel()
        for order in self:
            order.rfid_site_ids.filtered(
                lambda site: site.state not in ('active', 'closed')
            ).write({'state': 'cancelled'})
            order.rfid_site_ids.subscription_ids.filtered(
                lambda subscription: subscription.state in ('pending', 'active', 'paused')
            ).action_close()
        return result

    def action_view_rfid_sites(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id(
            'nwos_rfid_service.action_rfid_site')
        action['domain'] = [('sale_order_id', '=', self.id)]
        action['context'] = {
            'create': False,
            'default_sale_order_id': self.id,
            'default_partner_id': self.partner_id.id,
            'default_company_id': self.company_id.id,
        }
        return action


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    rfid_line_role = fields.Selection(
        LINE_ROLES, string='Item Type', required=True, default='standard',
        copy=True, index=True,
        help='A Normal Item follows the standard sales workflow. A Kit Item triggers '
             'delivery, installation, and payment controls. Subscription billing '
             'begins after customer acceptance.')
    rfid_site_id = fields.Many2one(
        'rfid.service.site', string='Installation Site', copy=True, index=True,
        domain="[('sale_order_id', '=', order_id)]",
        help='Required for Kit Items and Subscriptions; optional for Normal Items.')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('product_id') and not vals.get('rfid_line_role'):
                product = self.env['product.product'].browse(vals['product_id'])
                vals['rfid_line_role'] = product.product_tmpl_id.rfid_offer_type
        lines = super().create(vals_list)
        lines.mapped('rfid_site_id')._sync_project_template_from_kit_lines()
        return lines

    def write(self, vals):
        sites = self.mapped('rfid_site_id')
        result = super().write(vals)
        if {'product_id', 'rfid_line_role', 'rfid_site_id'} & vals.keys():
            (sites | self.mapped('rfid_site_id'))._sync_project_template_from_kit_lines()
        return result

    def unlink(self):
        sites = self.mapped('rfid_site_id')
        result = super().unlink()
        sites.exists()._sync_project_template_from_kit_lines()
        return result

    @api.onchange('product_id')
    def _onchange_product_id_rfid_role(self):
        for line in self.filtered('product_id'):
            line.rfid_line_role = line.product_template_id.rfid_offer_type or 'standard'

    @api.depends('qty_invoiced', 'qty_delivered', 'product_uom_qty', 'state',
                 'rfid_line_role')
    def _compute_qty_to_invoice(self):
        super()._compute_qty_to_invoice()
        self.filtered(
            lambda line: line.rfid_line_role == 'subscription'
        ).qty_to_invoice = 0

    def _rfid_site_procurement_values(self, values, site):
        date_deadline = site.planned_delivery_date or values.get('date_deadline')
        date_planned = date_deadline
        if date_deadline:
            date_planned = fields.Datetime.to_datetime(date_deadline) - timedelta(
                days=self.order_id.company_id.security_lead)
        return {
            **values,
            'rfid_site_id': site.id,
            'partner_id': site.installation_address_id.id,
            'location_final_id': site.installation_address_id.property_stock_customer,
            'date_deadline': date_deadline,
            'date_planned': date_planned,
            'origin': '%s / %s' % (self.order_id.name, site.name),
        }

    def _create_procurements(self, product_qty, procurement_uom, values):
        self.ensure_one()
        if self.rfid_site_id:
            values = self._rfid_site_procurement_values(values, self.rfid_site_id)
            return [self.env['stock.rule'].Procurement(
                self.product_id, product_qty, procurement_uom,
                self.rfid_site_id.installation_address_id.property_stock_customer,
                self.product_id.display_name,
                values['origin'], self.order_id.company_id, values,
            )]
        return super()._create_procurements(product_qty, procurement_uom, values)
