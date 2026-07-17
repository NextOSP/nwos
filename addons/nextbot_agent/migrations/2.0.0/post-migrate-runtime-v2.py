# Part of NextOSP. See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    """Preserve v1 history while closing state that cannot be resumed safely."""
    cr.execute("UPDATE nextbot_run SET runtime_version = 1")
    cr.execute(
        """
        UPDATE nextbot_run
           SET status = 'interrupted',
               completed_at = COALESCE(completed_at, NOW() AT TIME ZONE 'UTC'),
               error_message = COALESCE(
                   error_message,
                   'Interrupted by the NextBot v2 runtime upgrade. Regenerate this request to continue.'
               )
         WHERE status IN ('queued', 'running', 'waiting_approval')
        """
    )
    cr.execute(
        """
        UPDATE nextbot_approval
           SET state = 'superseded',
               resolved_at = COALESCE(resolved_at, NOW() AT TIME ZONE 'UTC')
         WHERE state IN ('pending', 'executing')
        """
    )
    cr.execute(
        """
        UPDATE ir_config_parameter
           SET value = '1440'
         WHERE key = 'nextbot_agent.approval_ttl_minutes' AND value = '15'
        """
    )
    cr.execute(
        """
        UPDATE ir_config_parameter
           SET value = '100'
         WHERE key = 'nextbot_agent.max_tool_calls' AND value = '4'
        """
    )
