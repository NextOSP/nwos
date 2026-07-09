# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from nwos import api, models, _


class DiscussChannel(models.Model):
    _inherit = 'discuss.channel'

    def execute_command_help(self, **kwargs):
        super().execute_command_help(**kwargs)
        self.env['mail.bot']._apply_logic(self, kwargs, command="help")  # kwargs are not usefull but...

    def execute_command_clear(self, **kwargs):
        self.env['mail.bot']._apply_logic(self, kwargs, command="clear")

    def _message_post_after_hook(self, message, msg_vals):
        self.env["mail.bot"]._apply_logic(self, msg_vals, message=message)
        return super()._message_post_after_hook(message, msg_vals)
