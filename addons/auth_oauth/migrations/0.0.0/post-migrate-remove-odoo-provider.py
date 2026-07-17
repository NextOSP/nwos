# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    cr.execute(
        """
        WITH odoo_provider AS (
            SELECT res_id AS id
              FROM ir_model_data
             WHERE module = 'auth_oauth'
               AND name = 'provider_openerp'
               AND model = 'auth.oauth.provider'
        )
        UPDATE res_users users
           SET oauth_provider_id = NULL,
               oauth_uid = NULL,
               oauth_access_token = NULL
          FROM odoo_provider
         WHERE users.oauth_provider_id = odoo_provider.id
        """
    )
    cr.execute(
        """
        DELETE FROM auth_oauth_provider provider
              USING ir_model_data data
              WHERE data.module = 'auth_oauth'
                AND data.name = 'provider_openerp'
                AND data.model = 'auth.oauth.provider'
                AND provider.id = data.res_id
        """
    )
    cr.execute(
        """
        DELETE FROM ir_model_data
              WHERE module = 'auth_oauth'
                AND name = 'provider_openerp'
                AND model = 'auth.oauth.provider'
        """
    )
