# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from . import models
from nwos.exceptions import UserError


def uninstall_hook(env):
    if not env.ref('base.module_base').demo:
        raise UserError('The module "Account Audit Trail" (account_audit_trail) cannot be uninstalled.')
