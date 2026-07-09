# Part of NextOSP. See LICENSE file for full copyright and licensing details.
from nwos import models


class IrQWeb(models.AbstractModel):
    _inherit = "ir.qweb"

    def _get_bundles_to_pregenarate(self):
        js_assets, css_assets = super()._get_bundles_to_pregenarate()
        assets = {"im_livechat.assets_embed_external"}
        return (js_assets | assets, css_assets | assets)
