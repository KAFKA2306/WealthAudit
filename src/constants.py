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
    SMBC_1 = "smbc_1"
    SMBC_2 = "smbc_2"
    RAKUTEN_1 = "rakuten_1"
    RAKUTEN_2 = "rakuten_2"
    EPOS = "epos"
    MONEX_CARD = "monex_card"
    SONY_CARD = "sony_card"
    WISE = "wise"
    CASH = "cash"
    ADJUSTMENT = "adjustment"
    RAKUTEN_JCB = "rakuten_jcb"
    SMBC_NUMBERLESS = "smbc_numberless"


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
