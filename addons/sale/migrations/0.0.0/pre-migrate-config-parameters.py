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
        UPDATE ir_ui_view view
           SET arch_db = jsonb_build_object('en_US', $view_arch$
            <data>
                <page name="sales" position="attributes">
                    <attribute name="invisible" remove="1" separator="or"/>
                </page>
                <field name="product_variant_count" position="after">
                    <field name="service_type" widget="radio" invisible="True"/>
                    <field name="visible_expense_policy" invisible="1"/>
                </field>
                <field name="type" position="after">
                    <field
                        name="invoice_policy"
                        required="1"
                        invisible="not sale_ok or type == 'combo'"
                    />
                </field>
                <field name="service_tracking" position="attributes">
                    <attribute name="invisible" add="not sale_ok" separator="or"/>
                </field>
                <group name="description" position="after">
                    <t groups="sales_team.group_sale_salesman">
                        <group string="Warning on Sales Orders" groups="sale.group_warning_sale">
                            <field name="sale_line_warn_msg"
                                   placeholder="e.g. This product is defective."
                                   nolabel="1" colspan="2"/>
                        </group>
                    </t>
                    <group name="expense_info" string="Expense" invisible="not visible_expense_policy">
                        <field name="expense_policy" widget="radio"/>
                    </group>
                </group>
            </data>
            $view_arch$)
          FROM ir_model_data imd
         WHERE imd.module = 'sale'
           AND imd.name = 'product_template_form_view'
           AND imd.model = 'ir.ui.view'
           AND imd.res_id = view.id
           AND view.model = 'product.template'
        """
    )
    cr.execute(
        """
        WITH quotation_action AS (
            SELECT res_id AS action_id
              FROM ir_model_data
             WHERE module = 'sale'
               AND name = 'action_quotations'
               AND model = 'ir.actions.act_window'
        ),
        quotation_views AS (
            SELECT awv.id,
                   CASE
                       WHEN awv.view_mode IN ('tree', 'list') THEN 'action_quotations_tree'
                       WHEN awv.view_mode = 'kanban' THEN 'action_quotations_kanban'
                   END AS xml_name
              FROM ir_act_window_view awv, quotation_action
             WHERE awv.act_window_id = quotation_action.action_id
               AND awv.view_mode IN ('tree', 'list', 'kanban')
        )
        DELETE FROM ir_model_data imd
         USING quotation_views
         WHERE imd.module = 'sale'
           AND imd.name = quotation_views.xml_name
           AND (imd.model != 'ir.actions.act_window.view' OR imd.res_id != quotation_views.id)
        """
    )
    cr.execute(
        """
        WITH quotation_action AS (
            SELECT res_id AS action_id
              FROM ir_model_data
             WHERE module = 'sale'
               AND name = 'action_quotations'
               AND model = 'ir.actions.act_window'
        ),
        quotation_views AS (
            SELECT awv.id,
                   CASE
                       WHEN awv.view_mode IN ('tree', 'list') THEN 'action_quotations_tree'
                       WHEN awv.view_mode = 'kanban' THEN 'action_quotations_kanban'
                   END AS xml_name
              FROM ir_act_window_view awv, quotation_action
             WHERE awv.act_window_id = quotation_action.action_id
               AND awv.view_mode IN ('tree', 'list', 'kanban')
        )
        UPDATE ir_model_data imd
           SET name = quotation_views.xml_name
          FROM quotation_views
         WHERE imd.module = 'sale'
           AND imd.model = 'ir.actions.act_window.view'
           AND imd.res_id = quotation_views.id
           AND imd.name IN (
                'sale_order_action_view_quotation_tree',
                'sale_order_action_view_quotation_kanban',
                quotation_views.xml_name
           )
        """
    )
    cr.execute(
        """
        WITH quotation_action AS (
            SELECT res_id AS action_id
              FROM ir_model_data
             WHERE module = 'sale'
               AND name = 'action_quotations'
               AND model = 'ir.actions.act_window'
        ),
        quotation_views AS (
            SELECT awv.id,
                   CASE
                       WHEN awv.view_mode IN ('tree', 'list') THEN 'action_quotations_tree'
                       WHEN awv.view_mode = 'kanban' THEN 'action_quotations_kanban'
                   END AS xml_name
              FROM ir_act_window_view awv, quotation_action
             WHERE awv.act_window_id = quotation_action.action_id
               AND awv.view_mode IN ('tree', 'list', 'kanban')
        )
        INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
        SELECT 'sale', quotation_views.xml_name, 'ir.actions.act_window.view', quotation_views.id, FALSE
          FROM quotation_views
         WHERE NOT EXISTS (
               SELECT 1
                 FROM ir_model_data imd
                WHERE imd.module = 'sale'
                  AND imd.name = quotation_views.xml_name
                  AND imd.model = 'ir.actions.act_window.view'
         )
        """
    )
    cr.execute(
        """
        WITH quotation_action AS (
            SELECT res_id AS action_id
              FROM ir_model_data
             WHERE module = 'sale'
               AND name = 'action_quotations'
               AND model = 'ir.actions.act_window'
        )
        UPDATE ir_act_window_view awv
           SET view_mode = 'list'
          FROM quotation_action
         WHERE awv.act_window_id = quotation_action.action_id
           AND awv.view_mode = 'tree'
        """
    )
    cr.execute(
        """
        WITH parameter AS (
            SELECT id
              FROM ir_config_parameter
             WHERE key = 'sale.async_emails'
        )
        DELETE FROM ir_model_data imd
         USING parameter
         WHERE imd.module = 'sale'
           AND imd.name = 'async_emails'
           AND imd.model = 'ir.config_parameter'
           AND imd.res_id != parameter.id
        """
    )
    cr.execute(
        """
        WITH parameter AS (
            SELECT id
              FROM ir_config_parameter
             WHERE key = 'sale.async_emails'
        )
        UPDATE ir_model_data imd
           SET module = 'sale',
               name = 'async_emails'
          FROM parameter
         WHERE imd.module = 'sale_async_emails'
           AND imd.name = 'async_emails'
           AND imd.model = 'ir.config_parameter'
           AND imd.res_id = parameter.id
        """
    )
    cr.execute(
        """
        INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
        SELECT 'sale', 'async_emails', 'ir.config_parameter', parameter.id, TRUE
          FROM ir_config_parameter parameter
         WHERE parameter.key = 'sale.async_emails'
           AND NOT EXISTS (
               SELECT 1
                 FROM ir_model_data imd
                WHERE imd.module = 'sale'
                  AND imd.name = 'async_emails'
                  AND imd.model = 'ir.config_parameter'
           )
        """
    )
