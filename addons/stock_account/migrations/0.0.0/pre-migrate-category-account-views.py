# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    cr.execute(
        """
        WITH obsolete_views AS (
            SELECT imd.res_id
              FROM ir_model_data imd
             WHERE imd.module = 'mrp_account'
               AND imd.name = 'view_category_property_form'
               AND imd.model = 'ir.ui.view'
        ),
        deleted_views AS (
            DELETE FROM ir_ui_view view
                  WHERE view.id IN (SELECT res_id FROM obsolete_views)
              RETURNING view.id
        )
        DELETE FROM ir_model_data imd
              WHERE imd.module = 'mrp_account'
                AND imd.name = 'view_category_property_form'
                AND imd.model = 'ir.ui.view'
                AND imd.res_id IN (SELECT id FROM deleted_views)
        """
    )
    cr.execute(
        """
        WITH obsolete_views AS (
            SELECT imd.res_id
              FROM ir_model_data imd
             WHERE imd.module = 'stock_account'
               AND imd.name = 'stock_valuation_layer_picking'
               AND imd.model = 'ir.ui.view'
        ),
        deleted_views AS (
            DELETE FROM ir_ui_view view
                  WHERE view.id IN (SELECT res_id FROM obsolete_views)
              RETURNING view.id
        )
        DELETE FROM ir_model_data imd
              WHERE imd.module = 'stock_account'
                AND imd.name = 'stock_valuation_layer_picking'
                AND imd.model = 'ir.ui.view'
                AND imd.res_id IN (SELECT id FROM deleted_views)
        """
    )
    cr.execute(
        """
        WITH obsolete_views AS (
            SELECT imd.res_id
              FROM ir_model_data imd
             WHERE imd.module = 'stock_account'
               AND imd.name = 'view_move_form_inherit'
               AND imd.model = 'ir.ui.view'
        ),
        deleted_views AS (
            DELETE FROM ir_ui_view view
                  WHERE view.id IN (SELECT res_id FROM obsolete_views)
              RETURNING view.id
        )
        DELETE FROM ir_model_data imd
              WHERE imd.module = 'stock_account'
                AND imd.name = 'view_move_form_inherit'
                AND imd.model = 'ir.ui.view'
                AND imd.res_id IN (SELECT id FROM deleted_views)
        """
    )
    cr.execute(
        """
        UPDATE ir_ui_view view
           SET arch_db = jsonb_build_object('en_US', $view_arch$<field name="property_account_expense_categ_id" position="after">
                    <field name="property_stock_valuation_account_id" string="Stock Account" options="{'no_create': True}"/>
                    <field name="account_stock_variation_id" string="Stock Variation" options="{'no_create': True}"/>
                    <field name="property_price_difference_account_id" options="{'no_create': True}" invisible="not (property_cost_method == 'standard' and property_valuation == 'real_time')"/>
                </field>$view_arch$)
          FROM ir_model_data imd
         WHERE imd.module = 'stock_account'
           AND imd.name = 'view_category_property_form'
           AND imd.model = 'ir.ui.view'
           AND imd.res_id = view.id
           AND view.model = 'product.category'
        """
    )
