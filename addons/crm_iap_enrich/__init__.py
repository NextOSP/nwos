# -*- coding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from . import models


def _synchronize_cron(env):
    cron = env.ref('crm_iap_enrich.ir_cron_lead_enrichment', raise_if_not_found=False)
    if cron:
        cron.active = False
