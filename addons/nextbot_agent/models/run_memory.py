# Part of NextOSP. See LICENSE file for full copyright and licensing details.

import logging
from datetime import timedelta

from nwos import api, fields, models
from nwos.modules import module as module_tools

_logger = logging.getLogger(__name__)


class NextBotRun(models.Model):
    """Auto-learning bookkeeping on runs.

    Memory extraction happens asynchronously in its own cron, never in the
    user-facing runtime, and its failures can never change a run's status.
    """

    _inherit = 'nextbot.run'

    memory_status = fields.Selection([
        ('pending', 'Pending'),
        ('done', 'Done'),
        ('skipped', 'Skipped'),
        ('failed', 'Failed'),
    ], default='pending', index=True, copy=False)
    remember_call_count = fields.Integer(default=0, copy=False)

    @api.model
    def _cron_extract_memories(self, batch_size=20):
        parameters = self.env['ir.config_parameter'].sudo()
        auto_learn = (parameters.get_param('nextbot_agent.auto_learn_enabled', 'True') or '').lower()
        if auto_learn in ('false', '0'):
            return
        cutoff = fields.Datetime.now() - timedelta(days=7)
        runs = self.sudo().search([
            ('status', '=', 'completed'),
            ('memory_status', '=', 'pending'),
            ('completed_at', '>=', cutoff),
        ], order='id', limit=batch_size)
        # Anything older than the window will never be processed; close it out.
        stale = self.sudo().search([
            ('status', 'in', ('completed', 'failed', 'cancelled')),
            ('memory_status', '=', 'pending'),
            ('completed_at', '<', cutoff),
        ], limit=500)
        if stale:
            stale.write({'memory_status': 'skipped'})
        committable = not module_tools.current_test
        for run in runs:
            try:
                # The savepoint isolates a failing run's partial work without
                # touching the outer transaction (works on test cursors too).
                with self.env.cr.savepoint():
                    if not run.user_id.active:
                        run.write({'memory_status': 'skipped'})
                    else:
                        status = self.env['nextbot.memory']._extract_from_run(run)
                        run.write({'memory_status': status})
            except Exception:  # noqa: BLE001 - one run must not block the batch
                _logger.warning('NextBot memory extraction failed for run %s', run.id, exc_info=True)
                run.write({'memory_status': 'failed'})
            if committable:
                self.env.cr.commit()
