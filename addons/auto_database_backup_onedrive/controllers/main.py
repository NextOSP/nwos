# Part of NextOSP. See LICENSE file for full copyright & licensing details.

##############################################################################
#
#    NextOSP.
#    Copyright (C) 2017-TODAY NextOSP(<https://github.com/NextOSP>).
#
##############################################################################

import json

from nwos import http
from nwos.http import request


class OneDriveAuth(http.Controller):

    @http.route('/onedrive/authentication', type='http', auth="public")
    def oauth2callback(self, **kw):
        state = json.loads(kw['state'])
        backup_config = (request.env['db.backup.configure'].
                         sudo().browse(state.get('backup_config_id')))
        backup_config.get_onedrive_tokens(kw.get('code'))
        url_return = state.get('url_return')
        return request.redirect(url_return)
