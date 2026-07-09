# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    cr.execute(
        """
        WITH RECURSIVE obsolete_views(id) AS (
            SELECT imd.res_id
              FROM ir_model_data imd
             WHERE imd.module = 'sales_team'
               AND imd.name = 'res_partner_view_team'
               AND imd.model = 'ir.ui.view'
            UNION
            SELECT child.id
              FROM ir_ui_view child
              JOIN obsolete_views parent ON parent.id = child.inherit_id
        ),
        deleted_views AS (
            DELETE FROM ir_ui_view view
                  WHERE view.id IN (SELECT id FROM obsolete_views)
              RETURNING view.id
        )
        DELETE FROM ir_model_data imd
              WHERE imd.model = 'ir.ui.view'
                AND imd.res_id IN (SELECT id FROM deleted_views)
        """
    )
