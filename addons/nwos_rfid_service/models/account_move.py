from nwos import fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    rfid_subscription_period_id = fields.Many2one(
        'rfid.subscription.period', string='Kit Billing Period',
        index=True, copy=False)
    rfid_subscription_id = fields.Many2one(
        related='rfid_subscription_period_id.subscription_id', store=True,
        string='Kit Subscription')
    rfid_site_id = fields.Many2one(
        related='rfid_subscription_period_id.site_id', store=True,
        string='Nextwaves Kit Site')


class AccountMove(models.Model):
    _inherit = 'account.move'

    def button_cancel(self):
        periods = self.invoice_line_ids.rfid_subscription_period_id
        result = super().button_cancel()
        periods.write({'state': 'due', 'invoice_line_id': False})
        return result
