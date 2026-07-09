# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    cr.execute(
        """
        UPDATE account_journal
           SET invoice_reference_model = 'nwos'
         WHERE invoice_reference_model = 'odoo'
        """
    )
