"""Explicit Nigeria/Ghana capabilities; methods are options, never connections."""
from decimal import Decimal, InvalidOperation

MARKETS = {
    'NG': {'name': 'Nigeria', 'currency': 'NGN', 'timezone': 'Africa/Lagos',
           'payment_methods': ('card', 'bank_transfer', 'ussd'),
           'providers': ('Paystack', 'Flutterwave')},
    'GH': {'name': 'Ghana', 'currency': 'GHS', 'timezone': 'Africa/Accra',
           'payment_methods': ('card', 'mobile_money', 'bank_transfer'),
           'providers': ('Paystack', 'Flutterwave')},
}


def verified_payment_amount(event):
    """Never count pending MoMo/transfers, unsigned events or mixed money as cash.

    This adapter contract consumes a *server-verified* normalized provider event,
    not browser input. Real payment integrations are not yet configured.
    """
    if event.get('verified') is not True or event.get('state') != 'settled':
        return None
    market = MARKETS.get(event.get('country'))
    if not market or event.get('currency') != market['currency'] or not event.get('receipt_id'):
        raise ValueError('A settled payment needs a supported market, original currency and receipt.')
    try:
        value = Decimal(str(event['amount']))
    except (KeyError, InvalidOperation):
        raise ValueError('Invalid payment amount.')
    if not value.is_finite() or value < 0 or value.quantize(Decimal('.01')) != value:
        raise ValueError('Invalid payment amount.')
    return value
