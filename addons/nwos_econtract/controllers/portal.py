# -*- coding: utf-8 -*-
import base64
import binascii

from nwos import http, _
from nwos.http import request
from nwos.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from nwos.exceptions import AccessError, MissingError


class EContractPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'econtract_count' in counters:
            partner = request.env.user.partner_id
            values['econtract_count'] = request.env['econtract.contract'].search_count(
                [('partner_id', 'child_of', partner.commercial_partner_id.id)]
            ) if not request.env.user._is_public() else 0
        return values

    # ------------------------------------------------------------- list
    @http.route(['/my/contracts', '/my/contracts/page/<int:page>'],
                type='http', auth='user', website=True)
    def portal_my_contracts(self, page=1, **kw):
        partner = request.env.user.partner_id
        Contract = request.env['econtract.contract']
        domain = [('partner_id', 'child_of', partner.commercial_partner_id.id)]
        total = Contract.search_count(domain)
        pager = portal_pager(
            url='/my/contracts', total=total, page=page, step=self._items_per_page)
        contracts = Contract.search(
            domain, limit=self._items_per_page, offset=pager['offset'],
            order='create_date desc')
        values = {
            'contracts': contracts,
            'pager': pager,
            'page_name': 'econtract',
            'default_url': '/my/contracts',
        }
        return request.render('nwos_econtract.portal_my_contracts', values)

    # ------------------------------------------------------------- view / sign page
    @http.route(['/my/econtract/<int:contract_id>'],
                type='http', auth='public', website=True)
    def portal_econtract(self, contract_id, access_token=None, message=None, **kw):
        try:
            contract = self._document_check_access('econtract.contract', contract_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')
        values = {
            'contract': contract,
            'access_token': access_token,
            'message': message,
            'page_name': 'econtract',
        }
        return request.render('nwos_econtract.portal_econtract_page', values)

    # ------------------------------------------------------------- word download
    @http.route(['/econtract/<int:contract_id>/word'],
                type='http', auth='public', website=False)
    def portal_econtract_word(self, contract_id, access_token=None, **kw):
        try:
            contract = self._document_check_access('econtract.contract', contract_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')
        content = contract._render_word_bytes()
        return request.make_response(content, headers=[
            ('Content-Type', 'application/msword'),
            ('Content-Length', len(content)),
            ('Content-Disposition',
             http.content_disposition(contract._word_filename())),
        ])

    # ------------------------------------------------------------- submit signature
    @http.route(['/my/econtract/<int:contract_id>/sign'],
                type='http', auth='public', website=True, methods=['POST'], csrf=True)
    def portal_econtract_sign(self, contract_id, access_token=None,
                              signer_name=None, signature=None, **kw):
        try:
            contract = self._document_check_access('econtract.contract', contract_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')

        if contract.state == 'signed':
            return request.redirect(contract._get_sign_url())

        if not signer_name or not signature or not signature.startswith('data:image'):
            return request.redirect(
                '/my/econtract/%s?access_token=%s&message=missing'
                % (contract_id, access_token or ''))

        try:
            b64 = signature.split(',', 1)[1]
            base64.b64decode(b64)  # validate
        except (IndexError, binascii.Error):
            return request.redirect(
                '/my/econtract/%s?access_token=%s&message=invalid'
                % (contract_id, access_token or ''))

        contract._apply_signature(signer=signer_name.strip(), signature_b64=b64)
        return request.redirect(
            '/my/econtract/%s?access_token=%s&message=signed'
            % (contract_id, access_token or ''))
