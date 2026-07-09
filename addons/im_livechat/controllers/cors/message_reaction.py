# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from nwos.http import route
from nwos.addons.mail.controllers.message_reaction import MessageReactionController
from nwos.addons.im_livechat.tools.misc import force_guest_env


class LivechatMessageReactionController(MessageReactionController):
    @route("/im_livechat/cors/message/reaction", methods=["POST"], type="jsonrpc", auth="public", cors="*")
    def livechat_message_reaction(self, guest_token, message_id, content, action, **kwargs):
        force_guest_env(guest_token)
        return self.mail_message_reaction(message_id, content, action, **kwargs)
