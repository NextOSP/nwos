# -*- coding: utf-8 -*-

import logging

import nwos.release
import nwos.tools
from nwos.exceptions import AccessDenied
from nwos.modules.registry import Registry
from nwos.tools.translate import _

_logger = logging.getLogger(__name__)

RPC_VERSION_1 = {
        'server_version': nwos.release.version,
        'server_version_info': nwos.release.version_info,
        'server_serie': nwos.release.serie,
        'protocol_version': 1,
}

def exp_login(db, login, password):
    return exp_authenticate(db, login, password, None)

def exp_authenticate(db, login, password, user_agent_env):
    if not user_agent_env:
        user_agent_env = {}
    with Registry(db).cursor() as cr:
        env = nwos.api.Environment(cr, None, {})
        env.transaction.default_env = env  # force default_env
        try:
            credential = {'login': login, 'password': password, 'type': 'password'}
            return env['res.users'].authenticate(credential, {**user_agent_env, 'interactive': False})['uid']
        except AccessDenied:
            return False

def exp_version():
    return RPC_VERSION_1

def exp_about(extended=False):
    """Return information about the NWOS Server.

    @param extended: if True then return version info
    @return string if extended is False else tuple
    """

    info = _('See http://nwos.com')

    if extended:
        return info, nwos.release.version
    return info

def exp_set_loglevel(loglevel, logger=None):
    # TODO Previously, the level was set on the now deprecated
    # `nwos.netsvc.Logger` class.
    return True

def dispatch(method, params):
    g = globals()
    exp_method_name = 'exp_' + method
    if exp_method_name in g:
        return g[exp_method_name](*params)
    else:
        raise Exception("Method not found: %s" % method)
