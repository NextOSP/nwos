# Part of NextOSP. See LICENSE file for full copyright and licensing details.
from nwos.tests.common import TransactionCase


class TestBodDashboardAi(TransactionCase):

    def test_revenue_trend_question_uses_dashboard_context(self):
        answer = self.env['bod.dashboard']._local_ai_answer(
            "How is revenue trending vs the previous period?",
            {
                'period': 'quarter',
                'sales': {
                    'revenue': {'formatted': '$ 1,200.00'},
                    'revenue_delta': 12.5,
                    'order_count': 3,
                    'trend': [
                        {'label': '2026-04', 'value': 400.0},
                        {'label': '2026-05', 'value': 800.0},
                    ],
                },
            },
        )

        self.assertIn('$ 1,200.00', answer)
        self.assertIn('12.5%', answer)
        self.assertIn('Confirmed orders: 3', answer)

    def test_top_customers_question_uses_dashboard_context(self):
        answer = self.env['bod.dashboard']._local_ai_answer(
            "Who are our top 5 customers this period?",
            {
                'sales': {
                    'top_customers': [
                        {'name': 'Emily', 'formatted': '$ 500.00'},
                        {'name': 'Azure Interior', 'formatted': '$ 300.00'},
                    ],
                },
            },
        )

        self.assertIn('Emily: $ 500.00', answer)
        self.assertIn('Azure Interior: $ 300.00', answer)

    def test_overdue_receivables_question_uses_dashboard_context(self):
        answer = self.env['bod.dashboard']._local_ai_answer(
            "How much is overdue in receivables?",
            {
                'invoicing': {
                    'overdue': {'formatted': '$ 700.00'},
                    'overdue_count': 2,
                    'unpaid': {'formatted': '$ 900.00'},
                },
            },
        )

        self.assertIn('Overdue receivables are $ 700.00', answer)
        self.assertIn('2 invoice', answer)
        self.assertIn('Total unpaid receivables are $ 900.00', answer)
