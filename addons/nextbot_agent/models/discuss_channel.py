# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from nwos import api, models


class DiscussChannel(models.Model):
    """Keep NextBot conversations out of the Discuss UI.

    NextBot chats are persisted as regular Discuss channels (a legacy direct
    chat plus one private group per workspace conversation), but users interact
    with them exclusively through the NextBot workspace. Hide them from the
    Discuss sidebar/messaging menu and never pop a floating chat window when
    the bot answers.
    """

    _inherit = 'discuss.channel'

    def _nextbot_channel_ids(self):
        """Return the subset of ``self`` that are NextBot conversations."""
        bot_partner = self.env.ref('base.partner_root', raise_if_not_found=False)
        if not bot_partner or not self:
            return set()
        candidates = self.filtered(lambda channel: channel.channel_type in ('chat', 'group'))
        if not candidates:
            return set()
        # sudo: discuss.channel.member - checking bot membership of accessible channels
        members = self.env['discuss.channel.member'].sudo().search([
            ('partner_id', '=', bot_partner.id),
            ('channel_id', 'in', candidates.ids),
        ])
        return set(members.channel_id.ids)

    @api.model
    def _get_channels_as_member(self):
        channels = super()._get_channels_as_member()
        hidden_ids = channels._nextbot_channel_ids()
        if hidden_ids:
            channels = channels.filtered(lambda channel: channel.id not in hidden_ids)
        return channels

    def _notify_thread(self, message, msg_vals=False, **kwargs):
        if self._nextbot_channel_ids():
            # Skip the chathub bubble; the workspace polls its own run events.
            kwargs['silent'] = True
        return super()._notify_thread(message, msg_vals=msg_vals, **kwargs)
