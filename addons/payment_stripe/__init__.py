# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from . import controllers
from . import models

import nwos.addons.payment as payment  # prevent circular import error with payment


def post_init_hook(env):
    payment.setup_provider(env, 'stripe')


def uninstall_hook(env):
    payment.reset_payment_provider(env, 'stripe')
