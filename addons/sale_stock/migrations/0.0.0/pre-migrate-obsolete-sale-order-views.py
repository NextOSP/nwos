# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    cr.execute(
        """
        WITH obsolete_views AS (
            SELECT imd.res_id
              FROM ir_model_data imd
             WHERE imd.module = 'mail_bot'
               AND imd.name = 'res_users_view_form_preferences'
               AND imd.model = 'ir.ui.view'
        ),
        deleted_views AS (
            DELETE FROM ir_ui_view view
                  WHERE view.id IN (SELECT res_id FROM obsolete_views)
              RETURNING view.id
        )
        DELETE FROM ir_model_data imd
              WHERE imd.module = 'mail_bot'
                AND imd.name = 'res_users_view_form_preferences'
                AND imd.model = 'ir.ui.view'
                AND imd.res_id IN (SELECT id FROM deleted_views)
        """
    )
    cr.execute(
        """
        WITH obsolete_views AS (
            SELECT imd.res_id
              FROM ir_model_data imd
             WHERE imd.module = 'sale_stock'
               AND imd.name = 'view_order_form_inherit_sale_stock_qty'
               AND imd.model = 'ir.ui.view'
        ),
        deleted_views AS (
            DELETE FROM ir_ui_view view
                  WHERE view.id IN (SELECT res_id FROM obsolete_views)
              RETURNING view.id
        )
        DELETE FROM ir_model_data imd
              WHERE imd.module = 'sale_stock'
                AND imd.name = 'view_order_form_inherit_sale_stock_qty'
                AND imd.model = 'ir.ui.view'
                AND imd.res_id IN (SELECT id FROM deleted_views)
        """
    )
