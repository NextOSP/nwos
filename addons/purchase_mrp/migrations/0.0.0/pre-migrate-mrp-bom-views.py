# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    cr.execute(
        """
        WITH obsolete_views AS (
            SELECT imd.res_id
              FROM ir_model_data imd
             WHERE imd.module = 'mrp_account'
               AND imd.name = 'mrp_bom_form_view_inherited'
               AND imd.model = 'ir.ui.view'
        ),
        deleted_views AS (
            DELETE FROM ir_ui_view view
                  WHERE view.id IN (SELECT res_id FROM obsolete_views)
              RETURNING view.id
        )
        DELETE FROM ir_model_data imd
              WHERE imd.module = 'mrp_account'
                AND imd.name = 'mrp_bom_form_view_inherited'
                AND imd.model = 'ir.ui.view'
                AND imd.res_id IN (SELECT id FROM deleted_views)
        """
    )
    cr.execute(
        """
        UPDATE ir_ui_view view
           SET arch_db = jsonb_build_object('en_US', $view_arch$
            <xpath expr="//field[@name='bom_line_ids']/list//field[@name='operation_id']" position="after">
                <field name="cost_share" optional="hidden" column_invisible="parent.type != 'phantom'"/>
            </xpath>
            $view_arch$)
          FROM ir_model_data imd
         WHERE imd.module = 'purchase_mrp'
           AND imd.name = 'mrp_bom_form_view'
           AND imd.model = 'ir.ui.view'
           AND imd.res_id = view.id
           AND view.model = 'mrp.bom'
        """
    )
