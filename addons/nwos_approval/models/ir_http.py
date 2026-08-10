# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.
from nwos import models
from nwos.http import request


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        """Tell the client which models carry an approval flow.

        The injected form banner uses this as a synchronous fast path: models
        that are not listed never trigger an RPC or render anything.
        """
        result = super().session_info()
        if request and request.session.uid:
            result['approval_models'] = self.env['approval.request'].sudo(
            ).approval_models()
        return result
