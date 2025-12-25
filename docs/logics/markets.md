# Market Data Logic

This document describes how market data is used in the calculations.

## Currency Conversion

The market data, which includes USD/JPY and EUR/JPY exchange rates, is used to convert asset balances from their original currency (USD or EUR) to JPY. This is primarily done in the `BalanceSheetCalculator` when calculating the total value of assets.