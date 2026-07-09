# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from nwos import api, models


class WebsitePage(models.Model):
    _inherit = 'website.page'

    @api.model
    def _allow_to_use_cache(self, request):
        if request.httprequest.path == '/job-thank-you':
            return False
        return super()._allow_to_use_cache(request)
