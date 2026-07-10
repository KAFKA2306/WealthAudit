# Market Data Logic

This document describes how market data is used in the calculations.

## Currency Conversion

The market data, which includes USD/JPY and EUR/JPY exchange rates, is used to convert USD and EUR asset balances to JPY. JPY and `multi` balances are already JPY-valued and use no FX conversion. This is primarily done in the `BalanceSheetCalculator` when calculating the total value of assets.
