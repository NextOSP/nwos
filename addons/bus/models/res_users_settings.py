# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from nwos import models


class ResUsersSettings(models.Model):
    _name = 'res.users.settings'
    _inherit = ["res.users.settings", "bus.listener.mixin"]

    def _bus_channel(self):
        return self.user_id
