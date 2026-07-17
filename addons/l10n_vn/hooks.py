# Part of NextOSP. See LICENSE file for full copyright and licensing details.
import logging

_logger = logging.getLogger(__name__)


def _l10n_vn_set_price_precision(env):
    """Vietnamese đồng (VND) has no minor unit in practice, so product and unit
    prices should neither store nor display fractional digits.

    The Sales/Purchase "Unit Price" field uses ``min_display_digits='Product
    Price'``, so with the default precision of 2 a whole-đồng price renders as
    e.g. ``10,500,000.00``. Aligning the 'Product Price' decimal accuracy to 0
    on install makes unit prices show as clean integers (``10,500,000``) and
    matches the VND currency, which is what setting up a Vietnamese company
    should do out of the box.

    Runs at install time; only lowered from a positive value so it is a no-op
    if already configured.
    """
    precision = env.ref('product.decimal_price', raise_if_not_found=False)
    if precision and precision.digits > 0:
        precision.digits = 0
        _logger.info("l10n_vn: set 'Product Price' decimal precision to 0 (VND has no minor unit)")
