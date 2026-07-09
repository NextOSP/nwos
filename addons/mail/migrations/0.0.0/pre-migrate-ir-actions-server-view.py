# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    cr.execute(
        """
        UPDATE ir_ui_view view
           SET arch_db = jsonb_build_object('en_US', $view_arch$<data>
                <xpath expr="//form" position="inside">
                    <chatter/>
                </xpath>
                <xpath expr="//t[@name='action_content']//notebook" position="before">
                    <group invisible="state != 'next_activity'">
                        <group>
                            <field name="activity_type_id" options="{'no_create': True, 'no_open': True}" required="state == 'next_activity'"/>
                            <field name="activity_summary" placeholder="e.g. Discuss proposal"/>
                        </group>
                        <group>
                            <label for="activity_date_deadline_range"/>
                            <div class="o_row">
                                <field name="activity_date_deadline_range" class="oe_inline"/>
                                <field name="activity_date_deadline_range_type" class="oe_inline" required="state == 'next_activity' and activity_date_deadline_range &gt; 0"/>
                            </div>
                            <field name="activity_user_type" required="state == 'next_activity'"/>
                            <field name="activity_user_field_name" widget="field_selector" options="{'model': 'model_name'}" invisible="activity_user_type != 'generic'" required="state == 'next_activity' and activity_user_type == 'generic'"/>
                            <field name="activity_user_id" placeholder="Choose a user..." invisible="activity_user_type != 'specific'" required="state == 'next_activity' and activity_user_type == 'specific'"/>
                            <field name="activity_note" class="oe-bordered-editor" placeholder="Add a description to your activity..."/>
                        </group>
                    </group>
                    <group invisible="state not in ['followers', 'remove_followers']">
                        <group>
                            <field name="followers_type" required="state in ['followers', 'remove_followers']"/>
                            <field name="partner_ids" string="Followers to add" widget="many2many_tags" placeholder="Choose a contact..." invisible="state != 'followers' or followers_type != 'specific'" required="state == 'followers' and followers_type == 'specific'"/>
                            <field name="partner_ids" string="Followers to remove" widget="many2many_tags" placeholder="Choose a contact..." invisible="state != 'remove_followers' or followers_type != 'specific'" required="state == 'remove_followers' and followers_type == 'specific'"/>
                            <field name="followers_partner_field_name" widget="field_selector" options="{'model': 'model_name'}" invisible="followers_type != 'generic'" required="state in ['followers', 'remove_followers'] and followers_type == 'generic'"/>
                        </group>
                    </group>
                    <group invisible="state != 'mail_post'">
                        <group>
                            <field name="template_id" placeholder="Choose a template..." required="state == 'mail_post'" context="{'default_model': model_name, 'default_use_default_to': True}"/>
                            <label for="mail_post_method"/>
                            <div class="d-flex flex-column">
                                <field name="mail_post_method" required="state == 'mail_post'"/>
                                <div class="text-muted">
                                    <span invisible="mail_post_method != 'email'">The message will be sent as an email to the recipients of the template and will not appear in the messaging history.</span>
                                    <span invisible="mail_post_method != 'note'">The message will be posted as an internal note visible to internal users in the messaging history.</span>
                                    <span invisible="mail_post_method != 'comment'">The message will be posted as a message on the record, notifying all followers. It will appear in the messaging history.</span>
                                </div>
                            </div>
                            <field name="mail_post_autofollow" invisible="1"/>
                        </group>
                    </group>
                </xpath>
           </data>$view_arch$)
          FROM ir_model_data imd
         WHERE imd.module = 'mail'
           AND imd.name = 'view_server_action_form_template'
           AND imd.model = 'ir.ui.view'
           AND imd.res_id = view.id
           AND view.model = 'ir.actions.server'
        """
    )
