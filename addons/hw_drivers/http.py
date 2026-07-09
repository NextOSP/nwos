# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.

import nwos


def db_list(force=False, host=None):
    return []

nwos.http.db_list = db_list
