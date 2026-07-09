# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from nwos.addons.bus.controllers.websocket import WebsocketController
from nwos.http import request, route, SessionExpiredException


class WebsocketControllerPresence(WebsocketController):
    """Override of websocket controller to add mail features (presence in particular)."""

    @route("/websocket/update_bus_presence", type="jsonrpc", auth="public", cors="*")
    def update_bus_presence(self, inactivity_period):
        """Manually update presence of current user, useful when implementing custom websocket code.
        This is mainly used by NWOS.sh."""
        if "is_websocket_session" not in request.session:
            raise SessionExpiredException()
        request.env["ir.websocket"]._update_mail_presence(int(inactivity_period))
        return {}
