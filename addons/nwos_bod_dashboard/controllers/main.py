# Part of NextOSP. See LICENSE file for full copyright and licensing details.
from nwos import http
from nwos.http import request


class BodDashboardController(http.Controller):

    @http.route('/nwos_bod/data', type='jsonrpc', auth='user', readonly=True)
    def dashboard_data(self, period='last90'):
        return request.env['bod.dashboard'].get_dashboard_data(period=period)

    @http.route('/nwos_bod/ask_ai', type='jsonrpc', auth='user')
    def ask_ai(self, question, context=None):
        return request.env['bod.dashboard'].ask_ai(question, dashboard_context=context)
