
from nwos import models, api, tools
from nwos.tools.mimetypes import guess_mimetype
import base64


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    # NWOS 19's load_web_menus provides the menu tree (incl. web_icon_data_mimetype)
    # natively; the old NWOS override read menu['parent_id'] which no longer
    # exists in NWOS 19's load_menus payload -> removed.

    @api.model
    @tools.ormcache('self.env.uid', 'self.env.lang')
    def load_menus_root(self):
        res = super(IrUiMenu, self).load_menus_root()
        for menu in res.get('children'):
            if menu.get('web_icon_data'):
                menu['mimetype'] = guess_mimetype(base64.b64decode(menu['web_icon_data']))
        return res

    @api.model
    @tools.ormcache('self.env.uid', 'debug', 'self.env.lang')
    def load_menus(self, debug):
        res = super(IrUiMenu, self).load_menus(debug)
        for menu_key, menu_val in res.items():
            if menu_key != 'root':
                if menu_val.get('web_icon_data'):
                    menu_val['mimetype'] = guess_mimetype(
                        base64.b64decode(menu_val['web_icon_data']))
        return res