# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    cr.execute(
        """
        WITH purchase_action AS (
            SELECT res_id
              FROM ir_model_data
             WHERE module = 'purchase'
               AND name = 'act_res_partner_2_purchase_order'
               AND model = 'ir.actions.act_window'
        )
        UPDATE ir_ui_view view
           SET arch_db = jsonb_build_object(
                'en_US',
                format($view_arch$<data>
                    <div name="button_box" position="inside">
                        <button class="oe_stat_button" name="%s" type="action"
                            groups="purchase.group_purchase_user"
                            icon="fa-credit-card">
                            <field string="Purchases" name="purchase_order_count" widget="statinfo"/>
                        </button>
                    </div>
                    <group name="warnings" position="inside">
                        <group groups="purchase.group_warning_purchase" col="2">
                            <separator string="Warning on Purchase Orders and Bills" colspan="2"/>
                            <field name="purchase_warn_msg"
                                   placeholder="e.g. This vendor is on vacation until the end of August."
                                   nolabel="1" colspan="2"/>
                        </group>
                    </group>
                </data>$view_arch$, purchase_action.res_id),
                'vi_VN',
                format($view_arch$<data>
                    <div name="button_box" position="inside">
                        <button class="oe_stat_button" name="%s" type="action"
                            groups="purchase.group_purchase_user"
                            icon="fa-credit-card">
                            <field string="Purchases" name="purchase_order_count" widget="statinfo"/>
                        </button>
                    </div>
                    <group name="warnings" position="inside">
                        <group groups="purchase.group_warning_purchase" col="2">
                            <separator string="Warning on Purchase Orders and Bills" colspan="2"/>
                            <field name="purchase_warn_msg"
                                   placeholder="e.g. This vendor is on vacation until the end of August."
                                   nolabel="1" colspan="2"/>
                        </group>
                    </group>
                </data>$view_arch$, purchase_action.res_id)
           )
          FROM ir_model_data imd, purchase_action
         WHERE imd.module = 'purchase'
           AND imd.name = 'res_partner_view_purchase_buttons'
           AND imd.model = 'ir.ui.view'
           AND imd.res_id = view.id
           AND view.model = 'res.partner'
        """
    )
