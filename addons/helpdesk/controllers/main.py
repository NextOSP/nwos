# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from nwos import http
from nwos.http import request


class HelpdeskController(http.Controller):

    @http.route('/helpdesk/rating/<int:ticket_id>/<token>', type='http', auth='public', website=True)
    def helpdesk_rating(self, ticket_id, token, **kw):
        ticket = request.env['helpdesk.ticket'].sudo().browse(ticket_id).exists()
        if not ticket or ticket._portal_ensure_token() != token:
            return request.not_found()
        return request.render('helpdesk.helpdesk_ticket_rating_page', {
            'ticket': ticket,
            'token': token,
        })

    @http.route('/helpdesk/rating/submit', type='http', auth='public', website=True, methods=['POST'])
    def helpdesk_rating_submit(self, ticket_id, token, rating=3, feedback='', **kw):
        ticket = request.env['helpdesk.ticket'].sudo().browse(int(ticket_id)).exists()
        if not ticket or ticket._portal_ensure_token() != token:
            return request.not_found()
        request.env['rating.rating'].sudo().create({
            'res_model': 'helpdesk.ticket',
            'res_id': ticket.id,
            'res_name': ticket.name,
            'parent_res_model': 'helpdesk.team',
            'parent_res_id': ticket.team_id.id,
            'partner_id': ticket.partner_id.id,
            'rated_partner_id': ticket.user_id.partner_id.id if ticket.user_id else False,
            'rating': int(rating),
            'feedback': feedback,
            'consumed': True,
        })
        return request.render('helpdesk.helpdesk_ticket_rating_thanks')
