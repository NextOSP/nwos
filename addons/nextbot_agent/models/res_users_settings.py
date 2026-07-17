# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from nwos import fields, models


class ResUsersSettings(models.Model):
    _inherit = 'res.users.settings'

    nextbot_memory_enabled = fields.Boolean(
        string='NextBot memory', default=True,
        help='Let NextBot remember durable facts and preferences from your chats.',
    )
