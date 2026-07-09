# Part of NextOSP. See LICENSE file for full copyright and licensing details.
from nwos import models, fields


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    invoice_reference_model = fields.Selection(selection_add=[
        ('fi', 'Finnish Standard Reference (2024000068)'),
        ('fi_rf', 'Finnish Creditor Reference (RF) (RF952024000071)'),
    ], ondelete={'fi': lambda recs: recs.write({'invoice_reference_model': 'nwos'}),
                 'fi_rf': lambda recs: recs.write({'invoice_reference_model': 'nwos'})})
