from typing import List, Dict
from collections import defaultdict
from src.domain.entities.models import Income, Expense
from src.use_cases.dtos.output import CashFlowStatement


class CashFlowCalculator:
    def calculate(
        self, incomes: List[Income], expenses: List[Expense]
    ) -> List[CashFlowStatement]:
        # Aggregate by month
        monthly_income: Dict[str, int] = defaultdict(int)
        monthly_expense: Dict[str, int] = defaultdict(int)
        all_months = set()

        for inc in incomes:
            monthly_income[inc.month] += inc.amount
            all_months.add(inc.month)

        for exp in expenses:
            monthly_expense[exp.month] += exp.amount
            all_months.add(exp.month)

        # Create statements
        statements = []
        for month in sorted(all_months):
            inc_val = monthly_income[month]
            exp_val = monthly_expense[month]
            net_savings = inc_val - exp_val
            statement = CashFlowStatement(
                month=month,
                after_tax_income=inc_val,
                expenditure=exp_val,
                net_savings=net_savings,
            )
            statements.append(statement)

        return statements
