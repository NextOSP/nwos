# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from datetime import timezone

from nwos import fields


def iso_utc(value):
    """Serialize an ORM datetime as an unambiguous ISO-8601 UTC value."""
    if not value:
        return False
    value = fields.Datetime.to_datetime(value)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace('+00:00', 'Z')
