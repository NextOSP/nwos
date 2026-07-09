# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from nwos import models, fields


class MailActivityType(models.Model):
    _inherit = "mail.activity.type"

    category = fields.Selection(selection_add=[('meeting', 'Meeting')])
