# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.
"""Mark the lines of already-purchased requests as sourced, and reattach the
moves their Replenish lines launched.

`is_sourced` is what now keeps "Generate Purchase" from running twice. Requests
that reached `done` before this release were sourced by the old code, so flag
their lines — otherwise the button reappears on them and a second click would
duplicate the purchase orders / procurements.

Those old replenishments ran without a stock reference, so nothing pointed back
at the request. The moves do carry the request name as `origin`, which is enough
to rebuild the link and make the receipts visible again.
"""
import logging

from nwos import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def _relink_replenishments(env):
    requests = env['stock.request'].search([
        ('state', '=', 'done'),
        ('stock_reference_id', '=', False),
        ('line_ids.source_action', '=', 'replenish'),
    ])
    for request in requests:
        moves = env['stock.move'].search([
            ('origin', '=', request.name),
            ('company_id', '=', request.company_id.id),
        ])
        if moves:
            request._get_stock_reference().move_ids = [(6, 0, moves.ids)]
            _logger.info("stock.request %s: reattached %s replenishment move(s)",
                         request.name, len(moves))
        # A Buy route turned the replenishment into a purchase order (possibly
        # merged into an existing RFQ): the request name is in its `origin`.
        orders = env['purchase.order'].search([
            ('origin', 'ilike', request.name),
            ('stock_request_id', '=', False),
            ('company_id', '=', request.company_id.id),
        ])
        if orders:
            orders.stock_request_id = request.id
            _logger.info("stock.request %s: reattached purchase order(s) %s",
                         request.name, ", ".join(orders.mapped('name')))


def migrate(cr, version):
    cr.execute("""
        UPDATE stock_request_line l
           SET is_sourced = TRUE
          FROM stock_request r
         WHERE l.request_id = r.id
           AND r.state = 'done'
           AND COALESCE(l.is_sourced, FALSE) IS FALSE
    """)
    _logger.info("stock.request: flagged %s line(s) as already sourced",
                 cr.rowcount)
    _relink_replenishments(api.Environment(cr, SUPERUSER_ID, {}))
