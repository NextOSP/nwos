# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from nwos import models
from nwos.addons.mail.tools.discuss import Store


class MailMessage(models.Model):
    _inherit = "mail.message"

    def _to_store(self, store: Store, fields, **kwargs):
        super()._to_store(store, fields, **kwargs)
        slides = self._records_by_model_name().get("slide.slide")
        if not slides:
            return
        store.add(slides, as_thread=True, fields=["comments_count"])
