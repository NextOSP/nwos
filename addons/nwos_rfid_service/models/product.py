from nwos import api, fields, models, _
from nwos.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    rfid_offer_type = fields.Selection([
        ('standard', 'Normal Item'),
        ('starter_kit', 'Kit Item'),
        ('subscription', 'Subscription'),
    ], string='Default Item Type', default='standard', required=True,
       index=True,
       help='Default item type proposed when this product is added to a sales order. '
            'The salesperson can change it on each order line.')
    rfid_billing_interval_months = fields.Selection([
        ('1', 'Monthly'),
        ('3', 'Every 3 Months'),
        ('6', 'Every 6 Months'),
        ('12', 'Every 12 Months'),
    ], string='Billing Interval', default='1')
    rfid_project_template_id = fields.Many2one(
        'project.project', string='Default Project Template',
        domain="[('is_template', '=', True)]",
        help='Suggested for the installation site when this product is used as a '
             'Kit Item. The salesperson can override the template for each site.')

    @api.constrains('rfid_offer_type', 'type', 'rfid_project_template_id')
    def _check_rfid_offer_configuration(self):
        for product in self:
            if product.rfid_offer_type == 'subscription' and product.type != 'service':
                raise ValidationError(_(
                    'The Subscription item type can only be used with a service product.'))
            if (product.rfid_project_template_id
                    and not product.rfid_project_template_id.is_template):
                raise ValidationError(_(
                    'The selected default project must be a project template.'))
