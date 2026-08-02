from enum import Enum


class AccountId(str, Enum):
    YUCHO = "yucho"
    SONY = "sony"
    DEUTSCHE = "deutsche"
    MINNA = "minna"
    JONAN = "jonan"
    WISE = "wise"
    SBI_SEC = "sbi_sec"
    RAKUTEN_SEC = "rakuten_sec"
    MONEX_SEC = "monex_sec"
    BINANCE = "binance"
    KOSEI_NENKIN = "kosei_nenkin"
    DC = "dc"
    RAKUTEN = "rakuten"


class AssetClassId(str, Enum):
    CASH = "cash"
    STOCK_JP = "stock_jp"
    STOCK_US = "stock_us"
    FUND = "fund"
    FX = "fx"
    CRYPTO = "crypto"
    PENSION = "pension"
    VC = "vc"


class PaymentMethodId(str, Enum):
    SMBC_NUMBERLESS = "smbc_numberless"
    SMBC_AMAZON = "smbc_amazon"
    RAKUTEN_JCB = "rakuten_jcb"
    RAKUTEN_MASTERCARD = "rakuten_mastercard"
    EPOS = "epos"
    MONEX_CARD = "monex_card"
    SONY_CARD = "sony_card"
    MERCARI = "mercari"
    WISE = "wise"
    CASH = "cash"
    ADJUSTMENT = "adjustment"


class AccountType(str, Enum):
    BANK = "bank"
    SECURITIES = "securities"
    CRYPTO = "crypto"
    PENSION = "pension"
    FINTECH = "fintech"


class Currency(str, Enum):
    JPY = "JPY"
    USD = "USD"
    EUR = "EUR"
    MULTI = "multi"


PORTFOLIO_EXPECTED_ANNUAL_RETURN = 0.05
# No benchmark forecast is assumed without an explicit policy. Forecast alpha is
# therefore undefined instead of being the difference of the same assumption.
BENCHMARK_EXPECTED_ANNUAL_RETURN: float | None = None
EXPECTED_ANNUAL_RETURN = PORTFOLIO_EXPECTED_ANNUAL_RETURN
FIXED_EXPENSE_CV_THRESHOLD = 0.3
