# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    cr.execute(
        """
        WITH old_actions AS (
            SELECT imd.res_id
              FROM ir_model_data imd
             WHERE imd.module = 'account'
               AND imd.name = 'action_account_unreconcile'
               AND imd.model = 'ir.actions.act_window'
        ),
        deleted_actions AS (
            DELETE FROM ir_actions action
                  WHERE action.id IN (SELECT res_id FROM old_actions)
              RETURNING action.id
        )
        DELETE FROM ir_model_data imd
              WHERE imd.module = 'account'
                AND imd.name = 'action_account_unreconcile'
                AND imd.model = 'ir.actions.act_window'
                AND imd.res_id IN (SELECT id FROM deleted_actions)
        """
    )
    cr.execute(
        """
        UPDATE ir_ui_view view
           SET arch_db = jsonb_build_object('en_US', $view_arch$<data>
                <xpath expr="//field[@name='company_id']" position="after">
                    <field name="fiscal_country_codes" invisible="1"/>
                </xpath>
                <xpath expr="//sheet" position="before">
                    <div groups="account.group_account_invoice,account.group_account_readonly" class="alert alert-warning" role="alert"
                         invisible="not duplicate_bank_partner_ids">
                        <span>One or more Bank Accounts set on this partner are also used by others:</span>
                        <field name="duplicate_bank_partner_ids" widget="x2many_buttons" string="Partners with same bank"/>
                    </div>
                </xpath>
                <page name="sales_purchases" position="after">
                    <page string="Invoicing" name="accounting" invisible="not is_company and parent_id" groups="account.group_account_invoice,account.group_account_readonly">
                        <group>
                            <group string="General" name="general" groups="account.group_account_invoice,account.group_account_readonly">
                                <field name="bank_ids"
                                       string="Bank accounts"
                                       context="{'default_partner_id': id}"
                                       domain="[('partner_id','=', id)]"
                                       widget="many2many_tags_banks"
                                       options="{'color_field': 'color', 'allow_out_payment_field': 'allow_out_payment', 'edit_tags': True}"/>
                                <field name="property_account_receivable_id" required="True" groups="account.group_account_user"/>
                                <field name="property_account_payable_id" required="True" groups="account.group_account_user"/>
                                <field name="autopost_bills" groups="account.group_account_user"/>
                                <field name="ignore_abnormal_invoice_amount" groups="base.group_no_one"/>
                                <field name="ignore_abnormal_invoice_date" groups="base.group_no_one"/>
                            </group>
                            <group id="invoice_send_settings"
                                   string="Customer Invoices"
                                   groups="account.group_account_invoice,account.group_account_readonly">
                                <field name="invoice_sending_method"
                                       groups="base.group_no_one"
                                       placeholder="e-Invoicing &amp; Email"/>
                                <field name="invoice_edi_format"
                                       placeholder="XML format"
                                       groups="base.group_no_one"
                                       invisible="not display_invoice_edi_format"/>
                                <field name="invoice_template_pdf_report_id"
                                       invisible="not display_invoice_template_pdf_report_id"
                                       options="{'no_create': True, 'no_edit': True}"/>
                            </group>
                            <group string="Credit Limits"
                                   name="credit_limits"
                                   groups="account.group_account_invoice,account.group_account_readonly"
                                   invisible="not show_credit_limit">
                                <field name="credit"/>
                                <field name="days_sales_outstanding"/>
                                <label for="use_partner_credit_limit"/>
                                <div class="o_row">
                                    <field name="use_partner_credit_limit"/>
                                    <field name="credit_limit" class="oe_inline" widget="monetary" options="{'currency_field': 'currency_id'}" invisible="not use_partner_credit_limit"/>
                                </div>
                            </group>
                        </group>
                    </page>
                    <page string="Invoicing" name="accounting_disabled" invisible="is_company or not parent_id" groups="account.group_account_invoice,account.group_account_readonly">
                        <div>
                            <p>Accounting-related settings are managed on <button name="open_commercial_entity" type="object" string="the parent company" class="oe_link"/></p>
                        </div>
                    </page>
                </page>
                <xpath expr="//group[@name='misc']" position="before">
                    <group string="Fiscal Information" name="fiscal_information" priority="5" groups="account.group_account_invoice,account.group_account_readonly">
                        <field name="property_account_position_id" options="{'no_create': True, 'no_open': True}"/>
                    </group>
                </xpath>
                <group name="sale" position="inside">
                    <field string="Payment Terms" name="property_payment_term_id" options="{'no_open': True, 'no_create': True}" groups="account.group_account_invoice,account.group_account_readonly"/>
                    <field string="Payment Method"
                           name="property_inbound_payment_method_line_id"
                           options="{'no_open': True, 'no_create': True}"
                           groups="account.group_account_invoice,account.group_account_readonly"
                    />
                </group>
                <group name="purchase" position="inside">
                    <field string="Payment Terms" name="property_supplier_payment_term_id" options="{'no_open': True, 'no_create': True}" groups="account.group_account_invoice,account.group_account_readonly"/>
                    <field string="Payment Method"
                           name="property_outbound_payment_method_line_id"
                           options="{'no_open': True, 'no_create': True}"
                           groups="account.group_account_invoice,account.group_account_readonly"
                    />
                </group>
           </data>$view_arch$)
          FROM ir_model_data imd
         WHERE imd.module = 'account'
           AND imd.name = 'view_partner_property_form'
           AND imd.model = 'ir.ui.view'
           AND imd.res_id = view.id
           AND view.model = 'res.partner'
        """
    )
