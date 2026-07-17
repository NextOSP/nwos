# Part of the web_carbon theme addon.

from nwos import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    logo_white = fields.Binary(
        string="Company Logo (White)",
        attachment=False,
        help="Light company logo used on dark Carbon headers.",
    )
