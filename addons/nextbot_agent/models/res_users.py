# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from nwos import models


class ResUsers(models.Model):
    _inherit = 'res.users'

    def _init_nwosbot(self):
        """Never seed a Discuss DM with the bot; NextBot lives in its workspace."""
        self.ensure_one()
        self.sudo().odoobot_state = 'disabled'
        return self.env['discuss.channel']
