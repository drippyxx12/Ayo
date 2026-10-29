"""Exact original-currency minor units, with explicit ISO exponent handling."""
from decimal import Decimal, InvalidOperation

ZERO_DIGITS = {'BIF', 'CLP', 'DJF', 'GNF', 'ISK', 'JPY', 'KMF', 'KRW', 'PYG', 'RWF', 'UGX', 'UYI', 'VND', 'VUV', 'XAF', 'XOF', 'XPF'}
THREE_DIGITS = {'BHD', 'IQD', 'JOD', 'KWD', 'LYD', 'OMR', 'TND'}


def exponent(currency):
    if not isinstance(currency, str) or len(currency) != 3 or not currency.isascii() or not currency.isupper() or not currency.isalpha():
        raise ValueError('Invalid currency code')
    return 0 if currency in ZERO_DIGITS else 3 if currency in THREE_DIGITS else 4 if currency in {'CLF', 'UYW'} else 2


def minor_units(value, currency):
    digits = exponent(currency)
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0:
            raise ValueError('Invalid money')
        minor = amount * (10 ** digits)
        if minor != minor.to_integral_value() or minor > 9223372036854775807:
            raise ValueError('Money exceeds supported precision or range')
        return int(minor)
    except InvalidOperation as exc:
        raise ValueError('Invalid money') from exc


def display_minor(value, currency):
    digits = exponent(currency)
    return f'{Decimal(value) / (10 ** digits):,.{digits}f}'
