# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from nwos import models
from nwos.addons.base.models.ir_module import assert_log_admin_access


class IrDemo(models.TransientModel):
    _name = 'ir.demo'
    _description = 'Demo'

    @assert_log_admin_access
    def install_demo(self):
        import nwos.modules.loading  # noqa: PLC0415
        nwos.modules.loading.force_demo(self.env)
        return {
            'type': 'ir.actions.act_url',
            'target': 'self',
            'url': '/nwos',
        }
