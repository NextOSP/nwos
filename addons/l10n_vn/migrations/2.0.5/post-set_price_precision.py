# Part of NextOSP. See LICENSE file for full copyright and licensing details.
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Converge existing Vietnamese databases to a 0-digit 'Product Price'
    decimal accuracy so unit prices stop rendering a trailing '.00' (VND has no
    minor unit). Mirrors the install-time _l10n_vn_set_price_precision hook.
    One-time, idempotent: only lowers a still-positive precision.
    """
    cr.execute("""
        UPDATE decimal_precision
           SET digits = 0
         WHERE name = 'Product Price'
           AND digits > 0
    """)
    if cr.rowcount:
        _logger.info("l10n_vn: lowered 'Product Price' decimal precision to 0 (VND has no minor unit)")
