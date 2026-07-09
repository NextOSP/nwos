# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    cr.execute(
        """
        WITH obsolete_views AS (
            SELECT imd.res_id
              FROM ir_model_data imd
             WHERE imd.module = 'purchase_stock'
               AND imd.name IN (
                   'product_template_form_view',
                   'view_category_property_form'
               )
               AND imd.model = 'ir.ui.view'
        ),
        deleted_views AS (
            DELETE FROM ir_ui_view view
                  WHERE view.id IN (SELECT res_id FROM obsolete_views)
              RETURNING view.id
        )
        DELETE FROM ir_model_data imd
              WHERE imd.module = 'purchase_stock'
                AND imd.name IN (
                    'product_template_form_view',
                    'view_category_property_form'
                )
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
        WITH obsolete_views AS (
            SELECT imd.res_id
              FROM ir_model_data imd
             WHERE imd.module = 'purchase_stock'
               AND imd.name = 'stock_reorder_report_search_inherited_purchase_stock'
               AND imd.model = 'ir.ui.view'
        ),
        deleted_views AS (
            DELETE FROM ir_ui_view view
                  WHERE view.id IN (SELECT res_id FROM obsolete_views)
              RETURNING view.id
        )
        DELETE FROM ir_model_data imd
              WHERE imd.module = 'purchase_stock'
                AND imd.name = 'stock_reorder_report_search_inherited_purchase_stock'
                AND imd.model = 'ir.ui.view'
                AND imd.res_id IN (SELECT id FROM deleted_views)
        """
    )
    cr.execute(
        """
        UPDATE ir_ui_view view
           SET arch_db = jsonb_build_object('en_US', $view_arch$<xpath expr="//app[@name='purchase']" position="inside">
                <field name="is_installed_sale" invisible="1"/>
                <block title="Logistics" invisible="not is_installed_sale" name="request_vendor_setting_container">
                    <setting title="This adds a dropshipping route to apply on products in order to request your vendors to deliver to your customers. A product to dropship will generate a purchase request for quotation once the sales order confirmed. This is a on-demand flow. The requested delivery address will be the customer delivery address and not your warehouse." help="Request your vendors to deliver to your customers"
                             documentation="/applications/inventory_and_mrp/inventory/shipping/operation/dropshipping.html">
                        <field name="module_stock_dropshipping"/>
                    </setting>
                    <setting title="This adds a Replenish On Order (MTO) route to apply on products in order to generate on-demand replenishment linked to your sales orders (for example) as soon as they are confirmed, with a direct link. Purchase orders, manufacturing orders, etc. are triggered based on what way to replenish is set on the product (Buy or Manufacture route)."
                             help="Allow Make to Order, or automate PO, when a product is sold and get direct links between documents."
                             documentation="/applications/inventory_and_mrp/inventory/warehouses_storage/replenishment/mto.html"
                             groups="stock.group_stock_manager">
                        <field name="replenish_on_order"/>
                    </setting>
                </block>
            </xpath>$view_arch$)
          FROM ir_model_data imd
         WHERE imd.module = 'purchase_stock'
           AND imd.name = 'res_config_settings_view_form_purchase'
           AND imd.model = 'ir.ui.view'
           AND imd.res_id = view.id
           AND view.model = 'res.config.settings'
        """
    )
    cr.execute(
        """
        UPDATE ir_ui_view view
           SET arch_db = jsonb_build_object('en_US', $view_arch$<div id="purchase_po_lead" position="replace">
                <setting company_dependent="1" help="Days needed to confirm a PO">
                    <field name="days_to_purchase" class="oe_inline"/><span> days</span>
                </setting>
            </div>$view_arch$)
          FROM ir_model_data imd
         WHERE imd.module = 'purchase_stock'
           AND imd.name = 'res_config_settings_view_form_stock'
           AND imd.model = 'ir.ui.view'
           AND imd.res_id = view.id
           AND view.model = 'res.config.settings'
        """
    )
