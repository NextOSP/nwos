from nwos.addons.point_of_sale.tests.test_generic_localization import TestGenericLocalization
from nwos.tests import tagged
from nwos.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install', 'post_install_l10n')
class TestGenericAR(TestGenericLocalization):

    @classmethod
    @AccountTestInvoicingCommon.setup_country('ar')
    def setUpClass(cls):
        super().setUpClass()
