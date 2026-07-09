# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    cr.execute(
        """
        WITH parameter_map(old_name, new_name, key) AS (
            VALUES
                ('web_flectra_onesignal_app_id_key_data',
                 'web_nwos_onesignal_app_id_key_data',
                 'onesignal_app_id'),
                ('web_flectra_onesignal_rest_api_key_data',
                 'web_nwos_onesignal_rest_api_key_data',
                 'onesignal_rest_api_key'),
                ('web_flectra_website_api_endpoint_key_data',
                 'web_nwos_website_api_endpoint_key_data',
                 'website.website_api_endpoint')
        ),
        parameters AS (
            SELECT parameter_map.new_name,
                   parameter.id AS parameter_id
              FROM parameter_map
              JOIN ir_config_parameter parameter
                ON parameter.key = parameter_map.key
        )
        DELETE FROM ir_model_data imd
         USING parameters
         WHERE imd.module = 'web_nwos'
           AND imd.name = parameters.new_name
           AND imd.model = 'ir.config_parameter'
           AND imd.res_id != parameters.parameter_id
        """
    )
    cr.execute(
        """
        WITH parameter_map(old_name, new_name, key) AS (
            VALUES
                ('web_flectra_onesignal_app_id_key_data',
                 'web_nwos_onesignal_app_id_key_data',
                 'onesignal_app_id'),
                ('web_flectra_onesignal_rest_api_key_data',
                 'web_nwos_onesignal_rest_api_key_data',
                 'onesignal_rest_api_key'),
                ('web_flectra_website_api_endpoint_key_data',
                 'web_nwos_website_api_endpoint_key_data',
                 'website.website_api_endpoint')
        )
        UPDATE ir_model_data imd
           SET name = parameter_map.new_name
          FROM parameter_map, ir_config_parameter parameter
         WHERE imd.module = 'web_nwos'
           AND imd.name = parameter_map.old_name
           AND imd.model = 'ir.config_parameter'
           AND imd.res_id = parameter.id
           AND parameter.key = parameter_map.key
        """
    )
    cr.execute(
        """
        WITH parameter_map(new_name, key) AS (
            VALUES
                ('web_nwos_onesignal_app_id_key_data', 'onesignal_app_id'),
                ('web_nwos_onesignal_rest_api_key_data', 'onesignal_rest_api_key'),
                ('web_nwos_website_api_endpoint_key_data', 'website.website_api_endpoint')
        )
        INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
        SELECT 'web_nwos',
               parameter_map.new_name,
               'ir.config_parameter',
               parameter.id,
               TRUE
          FROM parameter_map
          JOIN ir_config_parameter parameter
            ON parameter.key = parameter_map.key
         WHERE NOT EXISTS (
               SELECT 1
                 FROM ir_model_data imd
                WHERE imd.module = 'web_nwos'
                  AND imd.name = parameter_map.new_name
                  AND imd.model = 'ir.config_parameter'
         )
        """
    )
