# ruff: noqa: E402, F401
# Part of NextOSP. See LICENSE file for full copyright and licensing details.

""" NWOS initialization. """

from . import init

# ----------------------------------------------------------
# Shortcuts
# Expose them at the `nwos` namespace level
# ----------------------------------------------------------
import nwos
from .orm.commands import Command
from .orm.utils import SUPERUSER_ID
from .tools.translate import _, _lt

nwos.SUPERUSER_ID = SUPERUSER_ID
nwos._ = _
nwos._lt = _lt
nwos.Command = Command
