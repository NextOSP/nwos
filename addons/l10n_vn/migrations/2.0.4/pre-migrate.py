# Part of NextOSP. See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    """Keep existing references when correcting Ba Chẽ's administrative code."""
    cr.execute("""
        UPDATE ir_model_data AS data
           SET name = 'city_vn_06970'
         WHERE data.module = 'l10n_vn'
           AND data.name = 'city_vn_06978'
           AND NOT EXISTS (
               SELECT 1
                 FROM ir_model_data AS existing
                WHERE existing.module = 'l10n_vn'
                  AND existing.name = 'city_vn_06970'
           )
    """)
