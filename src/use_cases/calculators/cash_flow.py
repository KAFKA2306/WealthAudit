from typing import List, Dict, Optional
from collections import defaultdict
from src.constants import AccountType
from src.domain.entities.models import Account, Income, Expense
from src.use_cases.dtos.output import CashFlowStatement


class CashFlowCalculator:
    def calculate(
        self,
        incomes: List[Income],
        expenses: List[Expense],
        accounts: Optional[List[Account]] = None,
    ) -> List[CashFlowStatement]:
        account_map: Dict[str, Account] = {acc.id: acc for acc in accounts or []}
        monthly_income: Dict[str, int] = defaultdict(int)
        monthly_asset_contribution: Dict[str, int] = defaultdict(int)
        monthly_expense: Dict[str, int] = defaultdict(int)
        all_months = set()

        for inc in incomes:
            account = account_map.get(inc.account_id)
            if account and account.type == AccountType.PENSION:
                monthly_asset_contribution[inc.month] += inc.amount
            else:
                monthly_income[inc.month] += inc.amount
            all_months.add(inc.month)

        for exp in expenses:
            monthly_expense[exp.month] += exp.amount
            all_months.add(exp.month)

        # Create statements
        statements = []
        for month in sorted(all_months):
            inc_val = monthly_income[month]
            asset_contribution = monthly_asset_contribution[month]
            exp_val = monthly_expense[month]
            net_savings = inc_val - exp_val
            statement = CashFlowStatement(
                month=month,
                after_tax_income=inc_val,
                expenditure=exp_val,
                net_savings=net_savings,
                asset_contribution=asset_contribution,
                net_worth_contribution=net_savings + asset_contribution,
            )
            statements.append(statement)

        return statements
