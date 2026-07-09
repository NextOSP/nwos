# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    cr.execute(
        """
        UPDATE ir_ui_view view
           SET arch_db = (
                SELECT jsonb_object_agg(
                       elem.key,
                       replace(
                           replace(
                               replace(elem.value, '<tree', '<list'),
                               '</tree>', '</list>'
                           ),
                           '//tree', '//list'
                       )
                   )
                  FROM jsonb_each_text(view.arch_db) AS elem
           )
         WHERE view.arch_db::text LIKE '%<tree%'
            OR view.arch_db::text LIKE '%</tree>%'
            OR view.arch_db::text LIKE '%//tree%'
        """
    )
    cr.execute(
        """
        WITH obsolete_views AS (
            SELECT imd.res_id
              FROM ir_model_data imd
             WHERE imd.module = 'stock'
               AND imd.name = 'product_product_view_form_easy_inherit_stock'
               AND imd.model = 'ir.ui.view'
        ),
        deleted_views AS (
            DELETE FROM ir_ui_view view
                  WHERE view.id IN (SELECT res_id FROM obsolete_views)
              RETURNING view.id
        )
        DELETE FROM ir_model_data imd
              WHERE imd.module = 'stock'
                AND imd.name = 'product_product_view_form_easy_inherit_stock'
                AND imd.model = 'ir.ui.view'
                AND imd.res_id IN (SELECT id FROM deleted_views)
        """
    )
    cr.execute(
        """
        UPDATE ir_ui_view view
           SET arch_db = jsonb_build_object('en_US', $view_arch$<data>
            <group name="warnings" position="inside">
                <group groups="stock.group_warning_stock" col="2">
                    <separator string="Instructions on the Stock Operations" colspan="2"/>
                    <field name="picking_warn_msg"
                           placeholder="e.g. The delivery area is at the back of the building."
                           nolabel="1" colspan="2"/>
                </group>
            </group>

            <xpath expr="//div[@name='button_box']" position="inside">
                <button type="object"
                    name="action_view_stock_serial"
                    context="{'create': False}"
                    class="oe_stat_button" icon="fa-bars" groups="stock.group_production_lot">
                    <div class="o_stat_info">
                        <span class="o_stat_text">Lots/Serial Numbers</span>
                    </div>
                </button>
            </xpath>
           </data>$view_arch$)
          FROM ir_model_data imd
         WHERE imd.module = 'stock'
           AND imd.name = 'view_partner_stock_warnings_form'
           AND imd.model = 'ir.ui.view'
           AND imd.res_id = view.id
           AND view.model = 'res.partner'
        """
    )
    cr.execute(
        """
        UPDATE ir_ui_view view
           SET arch_db = jsonb_build_object(
                'en_US',
                format($view_arch$<data>
                    <div name="button_box" position="inside">
                        <t groups="stock.group_stock_user">
                            <field name="tracking" invisible="1"/>
                            <field name="show_on_hand_qty_status_button" invisible="1"/>
                            <field name="show_forecasted_qty_status_button" invisible="1"/>
                            <button type="object"
                                name="action_product_forecast_report"
                                invisible="not show_forecasted_qty_status_button"
                                context="{'default_product_id': id, 'active_model': 'product.template'}"
                                class="oe_stat_button" icon="fa-area-chart">
                                <div class="d-flex flex-row gap-1 ms-1">
                                    <div class="o_field_widget o_stat_info flex-column align-items-end gap-1">
                                        <span class="o_stat_value">
                                            <field name="qty_available" widget="statinfo" nolabel="1"/>
                                        </span>
                                        <span class="o_stat_value" invisible="virtual_available != 0">
                                            <field name="virtual_available" nolabel="1"/>
                                        </span>
                                        <span class="o_stat_value text-info" invisible="virtual_available &lt;= 0">
                                            <field name="virtual_available" nolabel="1"/>
                                        </span>
                                        <span class="o_stat_value text-danger" invisible="virtual_available &gt;= 0">
                                            <field name="virtual_available" nolabel="1"/>
                                        </span>
                                    </div>
                                    <div class="o_field_widget o_stat_info flex-column align-items-start gap-1">
                                        <span class="o_stat_value">
                                            <field name="uom_name" widget="statinfo" nolabel="1" groups="uom.group_uom"/>
                                            <span groups="!uom.group_uom">On Hand</span>
                                        </span>
                                        <span class="o_stat_value text-muted">
                                            Forecasted
                                        </span>
                                    </div>
                                </div>
                            </button>
                            <button type="object"
                                name="action_view_stock_move_lines"
                                invisible="type != 'consu'"
                                class="oe_stat_button" icon="fa-exchange"
                                groups="stock.group_stock_user">
                                <div class="d-flex flex-column">
                                    <div class="o_field_widget o_stat_info align-items-baseline flex-row gap-1 me-1">
                                        <span class="o_stat_text">In:</span>
                                        <span class="o_stat_value"><field name="nbr_moves_in"/></span>
                                    </div>
                                    <div class="o_field_widget o_stat_info align-items-baseline flex-row gap-1 me-1">
                                        <span class="o_stat_text">Out:</span>
                                        <span class="o_stat_value"><field name="nbr_moves_out"/></span>
                                    </div>
                                </div>
                            </button>
                            <button name="action_view_orderpoints" type="object"
                                invisible="type != 'consu' or nbr_reordering_rules != 1"
                                class="oe_stat_button" icon="fa-refresh">
                                <div class="d-flex flex-column">
                                    <div class="o_field_widget o_stat_info align-items-baseline flex-row gap-1 me-1">
                                        <span class="o_stat_text">Min:</span>
                                        <span class="o_stat_value"><field name="reordering_min_qty"/></span>
                                    </div>
                                    <div class="o_field_widget o_stat_info align-items-baseline flex-row gap-1 me-1">
                                        <span class="o_stat_text">Max:</span>
                                        <span class="o_stat_value"><field name="reordering_max_qty"/></span>
                                    </div>
                                </div>
                            </button>
                            <button type="object"
                                name="action_view_orderpoints"
                                invisible="not is_storable or nbr_reordering_rules == 1"
                                class="oe_stat_button" icon="fa-refresh">
                                <field name="nbr_reordering_rules" widget="statinfo"/>
                            </button>
                            <button type="object"
                                name="action_open_product_lot"
                                invisible="tracking == 'none'"
                                class="oe_stat_button" icon="fa-bars" groups="stock.group_production_lot">
                                <div class="o_stat_info">
                                    <span class="o_stat_text">Lot/Serial Numbers</span>
                                </div>
                            </button>
                            <button type="object"
                                name="action_view_related_putaway_rules"
                                class="oe_stat_button" icon="fa-random" groups="stock.group_stock_multi_locations"
                                invisible="type == 'service'"
                                context="{
                                    'invisible_handle': True,
                                    'single_product': product_variant_count == 1,
                                }">
                                    <div class="o_stat_info">
                                        <span class="o_stat_text">Putaway Rules</span>
                                    </div>
                             </button>
                            <button type="object" string="Storage Capacities"
                                name="action_view_storage_category_capacity"
                                groups="stock.group_stock_multi_locations"
                                invisible="type == 'service'"
                                class="oe_stat_button"
                                icon="fa-cubes"/>
                        </t>
                    </div>
                    <xpath expr="//button[@name='%s']" position="attributes">
                        <attribute name="context">
                            {'default_product_id': id}
                        </attribute>
                    </xpath>
                </data>$view_arch$, action_imd.res_id::text)
           )
          FROM ir_model_data imd
          JOIN ir_model_data action_imd
            ON action_imd.module = 'stock'
           AND action_imd.name = 'action_open_routes'
         WHERE imd.module = 'stock'
           AND imd.name = 'product_form_view_procurement_button'
           AND imd.model = 'ir.ui.view'
           AND imd.res_id = view.id
           AND view.model = 'product.product'
        """
    )
    cr.execute(
        """
        UPDATE ir_ui_view view
           SET arch_db = jsonb_build_object('en_US', $view_arch$<data>
                    <button name="action_open_documents" position="before">
                        <t groups="stock.group_stock_user">
                            <field name="tracking" invisible="1"/>
                            <field name="show_on_hand_qty_status_button" invisible="1"/>
                            <field name="show_forecasted_qty_status_button" invisible="1"/>
                            <button type="object"
                                name="action_product_tmpl_forecast_report"
                                invisible="not show_forecasted_qty_status_button"
                                context="{'default_product_tmpl_id': id}"
                                class="oe_stat_button" icon="fa-area-chart">
                                <div class="d-flex flex-row gap-1 ms-1">
                                    <div class="o_field_widget o_stat_info flex-column align-items-end gap-1">
                                        <span class="o_stat_value">
                                            <field name="qty_available" widget="statinfo" nolabel="1"/>
                                        </span>
                                        <span class="o_stat_value" invisible="virtual_available != 0">
                                            <field name="virtual_available" nolabel="1"/>
                                        </span>
                                        <span class="o_stat_value text-info" invisible="virtual_available &lt;= 0">
                                            <field name="virtual_available" nolabel="1"/>
                                        </span>
                                        <span class="o_stat_value text-danger" invisible="virtual_available &gt;= 0">
                                            <field name="virtual_available" nolabel="1"/>
                                        </span>
                                    </div>
                                    <div class="o_field_widget o_stat_info flex-column align-items-start gap-1">
                                        <span class="o_stat_value">
                                            <field name="uom_name" widget="statinfo" nolabel="1" groups="uom.group_uom"/>
                                            <span groups="!uom.group_uom">On Hand</span>
                                        </span>
                                        <span class="o_stat_value text-muted">
                                            Forecasted
                                        </span>
                                    </div>
                                </div>
                            </button>
                        </t>
                    </button>
                    <button name="action_open_documents" position="after">
                        <t groups="stock.group_stock_user">
                            <button type="object"
                                name="action_view_orderpoints"
                                invisible="not is_storable or nbr_reordering_rules != 1"
                                class="oe_stat_button" icon="fa-refresh">
                                <div class="d-flex flex-column">
                                    <div class="o_field_widget o_stat_info align-items-baseline flex-row gap-1 me-1">
                                        <span class="o_stat_text">Min:</span>
                                        <span class="o_stat_value"><field name="reordering_min_qty"/></span>
                                    </div>
                                    <div class="o_field_widget o_stat_info align-items-baseline flex-row gap-1 me-1">
                                        <span class="o_stat_text">Max:</span>
                                        <span class="o_stat_value"><field name="reordering_max_qty"/></span>
                                    </div>
                                </div>
                            </button>
                            <button type="object"
                                name="action_view_orderpoints"
                                invisible="not is_storable or nbr_reordering_rules == 1"
                                class="oe_stat_button"
                                icon="fa-refresh">
                                <field name="nbr_reordering_rules" widget="statinfo"/>
                            </button>
                            <button type="object"
                                name="action_view_stock_move_lines"
                                invisible="type != 'consu'"
                                class="oe_stat_button" icon="fa-exchange"
                                groups="stock.group_stock_user">
                                <div class="d-flex flex-column">
                                    <div class="o_field_widget o_stat_info align-items-baseline flex-row gap-1 me-1">
                                        <span class="o_stat_text">In:</span>
                                        <span class="o_stat_value"><field name="nbr_moves_in"/></span>
                                    </div>
                                    <div class="o_field_widget o_stat_info align-items-baseline flex-row gap-1 me-1">
                                        <span class="o_stat_text">Out:</span>
                                        <span class="o_stat_value"><field name="nbr_moves_out"/></span>
                                    </div>
                                </div>
                            </button>
                            <button type="object"
                                name="action_open_product_lot"
                                invisible="tracking == 'none'"
                                class="oe_stat_button" icon="fa-bars" groups="stock.group_production_lot">
                                <div class="o_stat_info">
                                    <span class="o_stat_text">Lot/Serial Numbers</span>
                                </div>
                            </button>
                            <button type="object"
                                name="action_view_related_putaway_rules"
                                class="oe_stat_button" icon="fa-random" groups="stock.group_stock_multi_locations"
                                invisible="type == 'service'"
                                context="{
                                    'invisible_handle': True,
                                    'single_product': product_variant_count == 1,
                                }">
                                    <div class="o_stat_info">
                                        <span class="o_stat_text">Putaway Rules</span>
                                    </div>
                             </button>
                             <button type="object"
                                name="action_view_storage_category_capacity"
                                groups="stock.group_stock_multi_locations"
                                invisible="type == 'service'"
                                class="oe_stat_button"
                                icon="fa-cubes">
                                <div class="o_stat_info">
                                    <span class="o_stat_text">Storage Capacities</span>
                                </div>
                            </button>
                        </t>
                    </button>

                    <xpath expr="//label[@for='weight']" position="before">
                        <field name="responsible_id" domain="[('share', '=', False)]" widget="many2one_avatar_user" groups="stock.group_stock_user"/>
                    </xpath>
           </data>$view_arch$)
          FROM ir_model_data imd
         WHERE imd.module = 'stock'
           AND imd.name = 'product_template_form_view_procurement_button'
           AND imd.model = 'ir.ui.view'
           AND imd.res_id = view.id
           AND view.model = 'product.template'
        """
    )
    cr.execute(
        """
        UPDATE ir_ui_view view
           SET arch_db = jsonb_build_object('en_US', $view_arch$<data>
                <field name="product_tooltip" position="after">
                    <label for="is_storable" class="oe_inline" invisible="type != 'consu'"/>
                    <div class="o_row w-100" invisible="type != 'consu'">
                        <field name="is_storable"/>
                        <field name="tracking" invisible="not is_storable" groups="stock.group_production_lot"/>
                    </div>
                    <field name="show_qty_update_button" invisible="1"/>
                    <label for="qty_available" class="oe_inline" invisible="not is_storable or not product_variant_id" groups="stock.group_stock_user"/>
                    <div class="o_row" invisible="not is_storable or not product_variant_id" groups="stock.group_stock_user">
                        <a type="object" name="action_open_quants"
                           invisible="not show_qty_update_button" groups="stock.group_stock_manager">
                            <field name="qty_available" readonly="True"/>
                        </a>
                        <field name="qty_available" invisible="show_qty_update_button" groups="stock.group_stock_manager" style="max-width: fit-content;"/>
                        <field name="qty_available" readonly="True" groups="!stock.group_stock_manager" style="max-width: fit-content;"/>
                        <span name="uom_span" groups="uom.group_uom">
                            <field name="uom_name" class="oe_inline"/>
                        </span>
                    </div>
                </field>
                <xpath expr="//group[@name='group_lots_and_weight']" position="inside">
                    <label for="sale_delay" invisible="not sale_ok"/>
                    <div invisible="not sale_ok">
                        <field name="sale_delay" class="oe_inline" style="vertical-align:baseline"/> days
                    </div>
                </xpath>
                <xpath expr="//group[@name='group_lots_and_weight']" position="before">
                    <field name="has_available_route_ids" invisible="1"/>
                    <group string="Operations" name="operations" invisible="not (has_available_route_ids or route_from_categ_ids)">
                        <label for="route_ids" invisible="not has_available_route_ids"/>
                        <div invisible="not has_available_route_ids">
                            <field name="route_ids" class="mb-0" widget="many2many_checkboxes"/>
                            <button id="stock.view_diagram_button" string="View Diagram" type="action" name="stock.action_open_routes" icon="oi-arrow-right"
                                class="btn btn-link pt-0" context="{'default_product_tmpl_id': id}"/>
                        </div>
                        <field name="route_from_categ_ids" widget="many2many_tags" invisible="not route_from_categ_ids"/>
                    </group>
                </xpath>
                <xpath expr="//group[@name='group_lots_and_weight']" position="after">
                    <group string="Traceability" name="traceability" groups="stock.group_production_lot" invisible="tracking == 'none'">
                        <label for="serial_prefix_format" string="Custom Lot/Serial" invisible="tracking == 'none'"/>
                        <div class="d-flex" invisible="tracking == 'none'">
                            <field name="serial_prefix_format" style="max-width: 150px;"/>
                            <field name="next_serial" style="max-width: 150px;"/>
                        </div>
                    </group>
                     <group string="Counterpart Locations" name="stock_property" groups="base.group_no_one">
                        <field name="property_stock_production"/>
                        <field name="property_stock_inventory"/>
                    </group>
                </xpath>
                <page name="inventory" position="inside">
                    <group>
                        <group string="Description for Receipts">
                            <field name="description_pickingin" nolabel="1" colspan="2" placeholder="This note is added to receipt orders (e.g. where to store the product in the warehouse)."/>
                        </group>
                        <group string="Description for Delivery Orders">
                            <field name="description_pickingout" nolabel="1" colspan="2" placeholder="This note is added to delivery orders."/>
                        </group>
                        <group string="Description for Internal Transfers" groups="stock.group_stock_multi_locations">
                            <field name="description_picking" nolabel="1" colspan="2" placeholder="This note is added to internal transfer orders (e.g. where to pick the product in the warehouse)."/>
                        </group>
                    </group>
                </page>
                <xpath expr="//page[@name='inventory']" position="attributes">
                    <attribute name="groups" add="stock.group_stock_user" separator=","/>
                </xpath>
           </data>$view_arch$)
          FROM ir_model_data imd
         WHERE imd.module = 'stock'
           AND imd.name = 'view_template_property_form'
           AND imd.model = 'ir.ui.view'
           AND imd.res_id = view.id
           AND view.model = 'product.template'
        """
    )
