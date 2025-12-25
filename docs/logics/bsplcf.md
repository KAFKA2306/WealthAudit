# Balance Sheet and Cash Flow Logic

This document describes the logic for calculating the balance sheet and cash flow statements.

## Cash Flow Calculation (`cash_flow.py`)

The cash flow calculation is performed by the `CashFlowCalculator`.

1.  **Aggregation**: Incomes and expenses are aggregated by month.
2.  **Net Savings**: For each month, net savings are calculated as `total income - total expenses`.
3.  **Statement Generation**: A `CashFlowStatement` is created for each month, containing the total income, total expenses, and net savings.

## Balance Sheet Calculation (`balance_sheet.py`)

The balance sheet calculation is performed by the `BalanceSheetCalculator`.

1.  **Asset Grouping**: Assets are grouped by month.
2.  **Asset Classification**: For each month, the total balance of liquid assets, risk assets, and pension assets is calculated based on the account's risk classification and asset class.
3.  **Investment Gain/Loss**: The investment gain or loss for the month is calculated. This is the change in total assets minus the net savings from the cash flow statement.
4.  **Statement Generation**: A `BalanceSheet` is created for each month, containing the balances of liquid, risk, and pension assets, as well as the total financial assets and the investment gain/loss.