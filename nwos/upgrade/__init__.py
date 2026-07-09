# Part of NextOSP. See LICENSE file for full copyright and licensing details.

import os.path
import pkgutil

class _UpgradePath(list):
    pass

__path__ = _UpgradePath(pkgutil.extend_path(__path__, __name__))
for path in __path__:
    os.path.abspath(path)
