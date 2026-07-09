# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from nwos.tools.rendering_tools import template_env_globals
from nwos.http import request

template_env_globals.update({
    'slug': lambda value: request.env['ir.http']._slug(value)  # noqa: PLW0108
})

from . import controllers
from . import models
from . import utils
from . import wizard
