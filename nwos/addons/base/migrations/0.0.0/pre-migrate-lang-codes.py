# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    cr.execute("UPDATE ir_ui_view SET type = 'list' WHERE type = 'tree'")
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
        UPDATE ir_model_data imd
           SET name = 'lang_sr@Cyrl'
         WHERE imd.module = 'base'
           AND imd.name = 'lang_sr_RS'
           AND imd.model = 'res.lang'
           AND NOT EXISTS (
                SELECT 1
                  FROM ir_model_data existing
                 WHERE existing.module = 'base'
                   AND existing.name = 'lang_sr@Cyrl'
           )
        """
    )
    cr.execute(
        """
        UPDATE ir_model_data imd
           SET name = 'state_id_pe'
         WHERE imd.module = 'base'
           AND imd.name = 'state_id_pp'
           AND imd.model = 'res.country.state'
           AND NOT EXISTS (
                SELECT 1
                  FROM ir_model_data existing
                 WHERE existing.module = 'base'
                   AND existing.name = 'state_id_pe'
           )
        """
    )
    cr.execute(
        """
        UPDATE res_lang
           SET code = 'sr@Cyrl',
               iso_code = 'sr@Cyrl',
               url_code = 'sr@Cyrl'
         WHERE code = 'sr_RS'
           AND NOT EXISTS (
                SELECT 1
                  FROM res_lang existing
                 WHERE existing.code = 'sr@Cyrl'
           )
        """
    )
    cr.execute(
        """
        UPDATE ir_ui_view view
           SET arch_db = jsonb_build_object('en_US', $view_arch$<data>
                <xpath expr="//button[@name='create_action']" position="replace">
                    <button name="method_direct_trigger" type="object" string="Run Manually" class="oe_highlight" invisible="state != 'code'"/>
                </xpath>
                <xpath expr="//button[@name='unlink_action']" position="replace">
                </xpath>
                <xpath expr="//button[@name='run']" position="replace">
                </xpath>
                <xpath expr="//button[@name='history_wizard_action']" position="replace"/>
                <xpath expr="//notebook" position="before">
                    <group>
                        <group>
                            <field name="user_id"/>
                            <label for="interval_number" string="Execute Every"/>
                            <div>
                                <field name="interval_number" class="oe_inline"/>
                                <field name="interval_type" class="oe_inline"/>
                            </div>
                            <field name="active" widget="boolean_toggle"/>
                            <field name="nextcall"/>
                            <field name="priority"/>
                        </group>
                    </group>
                </xpath>
                <field name="state" position="attributes">
                    <attribute name="invisible">1</attribute>
                </field>
           </data>$view_arch$)
          FROM ir_model_data imd
         WHERE imd.module = 'base'
           AND imd.name = 'ir_cron_view_form'
           AND imd.model = 'ir.ui.view'
           AND imd.res_id = view.id
           AND view.model = 'ir.cron'
        """
    )
    cr.execute(
        """
        DELETE FROM ir_ui_view view
              WHERE view.id IN (
                    SELECT imd.res_id
                      FROM ir_model_data imd
                     WHERE imd.module = 'base'
                       AND imd.name = 'user_groups_view'
                       AND imd.model = 'ir.ui.view'
              )
        """
    )
    cr.execute(
        """
        DELETE FROM ir_model_data imd
              WHERE imd.module = 'base'
                AND imd.name = 'user_groups_view'
                AND imd.model = 'ir.ui.view'
        """
    )
    cr.execute("UPDATE res_partner SET lang = 'sr@Cyrl' WHERE lang = 'sr_RS'")
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = 'res_users'
           AND column_name = 'lang'
        """
    )
    if cr.fetchone():
        cr.execute("UPDATE res_users SET lang = 'sr@Cyrl' WHERE lang = 'sr_RS'")
