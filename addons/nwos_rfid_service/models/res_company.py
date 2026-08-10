from nwos import api, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    rfid_require_payment_before_delivery = fields.Boolean(
        string='Require Kit Payment Before Delivery',
        default=True,
        help='When enabled, Kit deliveries and installation tasks remain blocked '
             'until all Kit Item invoices are fully paid.')
    rfid_project_template_id = fields.Many2one(
        'project.project', string='Default Installation Project Template',
        domain=[('is_template', '=', True)])
    rfid_helpdesk_team_id = fields.Many2one(
        'helpdesk.team', string='Default Nextwaves Kit Helpdesk Team')

    def write(self, vals):
        result = super().write(vals)
        if (
            'rfid_require_payment_before_delivery' in vals
            and not vals['rfid_require_payment_before_delivery']
        ):
            waiting_sites = self.env['rfid.service.site'].search([
                ('company_id', 'in', self.ids),
                ('state', '=', 'awaiting_payment'),
                ('payment_released', '=', False),
            ])
            waiting_sites._refresh_payment_release()
        return result


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    rfid_require_payment_before_delivery = fields.Boolean(
        related='company_id.rfid_require_payment_before_delivery',
        readonly=False)
    rfid_project_template_id = fields.Many2one(
        related='company_id.rfid_project_template_id', readonly=False)
    rfid_helpdesk_team_id = fields.Many2one(
        related='company_id.rfid_helpdesk_team_id', readonly=False)
    rfid_kit_product_ids = fields.Many2many(
        'product.template', string='Kit Item Products',
        compute='_compute_rfid_offer_products', inverse='_inverse_rfid_kit_product_ids',
        readonly=False, domain=[('sale_ok', '=', True)],
        help='Products proposed as Kit Item on sales order lines. Editing this list '
             'updates the Default Item Type of each product.')
    rfid_subscription_product_ids = fields.Many2many(
        'product.template', string='Subscription Products',
        compute='_compute_rfid_offer_products', inverse='_inverse_rfid_subscription_product_ids',
        readonly=False, domain=[('sale_ok', '=', True), ('type', '=', 'service')],
        help='Service products proposed as Subscription on sales order lines. Editing '
             'this list updates the Default Item Type of each product.')

    @api.depends('company_id')
    def _compute_rfid_offer_products(self):
        products = self.env['product.template'].search(
            [('rfid_offer_type', 'in', ('starter_kit', 'subscription'))])
        kits = products.filtered(lambda p: p.rfid_offer_type == 'starter_kit')
        for settings in self:
            settings.rfid_kit_product_ids = kits
            settings.rfid_subscription_product_ids = products - kits

    def _apply_rfid_offer_type(self, field_name, offer_type):
        for settings in self:
            selected = settings[field_name]
            current = self.env['product.template'].search(
                [('rfid_offer_type', '=', offer_type)])
            (current - selected).write({'rfid_offer_type': 'standard'})
            (selected - current).write({'rfid_offer_type': offer_type})

    def _inverse_rfid_kit_product_ids(self):
        self._apply_rfid_offer_type('rfid_kit_product_ids', 'starter_kit')

    def _inverse_rfid_subscription_product_ids(self):
        self._apply_rfid_offer_type('rfid_subscription_product_ids', 'subscription')
