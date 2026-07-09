import nwos.tests
from nwos.tools import mute_logger


@nwos.tests.common.tagged('post_install', '-at_install')
class TestWebsiteError(nwos.tests.HttpCase):

    @mute_logger('nwos.addons.http_routing.models.ir_http', 'nwos.http')
    def test_01_run_test(self):
        self.start_tour("/test_error_view", 'test_error_website')
