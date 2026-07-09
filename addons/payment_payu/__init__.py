# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from . import controllers, models
from nwos.addons.payment import reset_payment_provider, setup_provider


def post_init_hook(env):
    setup_provider(env, "payu")


def uninstall_hook(env):
    reset_payment_provider(env, "payu")
