import os
from datetime import date

from forex_python.converter import CurrencyRates

from .constants import KNOWN_CURRENCIES
from .config import config
from .logging import log
from .models import CurrencyRate as DBCurrencyRate


class Money(object):

    def __init__(self, amount, currency):
        assert isinstance(amount, float)
        assert currency, "No currency provided."
        self.as_float = amount
        self.currency = currency

    def __repr__(self):
        return "<{} {}>".format(self.as_float, self.currency)

    def __radd__(self, b):
        assert type(b) in (int, float)
        assert b == 0
        return Money(self.as_float, self.currency) + Money(float(b), self.currency)

    def __add__(self, b):
        if not self.currency == b.currency:
            b = Money(convert_currency(b.currency, self.currency, b.as_float), self.currency)
        return Money(self.as_float + b.as_float, self.currency)

    def __truediv__(self, b):
        if isinstance(b, Money):
            if not self.currency == b.currency:
                b = Money(convert_currency(b.currency, self.currency, b.as_float), self.currency)
            return Money(self.as_float / b.as_float, self.currency)
        elif isinstance(b, int) or isinstance(b, float):
            return Money(self.as_float / b, self.currency)
        else:
            raise NotImplementedError("Money and {}".format(type(b)))

    def __rmul__(self, b):
        return Money(self.as_float * b, self.currency)

    def __mul__(self, b):
        return Money(self.as_float * b, self.currency)

    def __sub__(self, b):
        if isinstance(b, Money):
            return Money(self.as_float - b.as_float, self.currency)
        elif isinstance(b, float):
            return Money(self.as_float - b, self.currency)

    def __format__(self, format_spec):
        return "{} {}".format(self.as_float.__format__(format_spec), self.currency)

    def __abs__(self):
        return Money(abs(self.as_float), self.currency)

    def __eq__(self, b):
        return all([self.currency == b.currency, self.as_float == b.as_float])

    def __bool__(self):
        return self.as_float != 0.0

    def convert_to(self, currency):
        if self.currency == currency:
            return self
        return Money(convert_currency(self.currency, currency, self.as_float), currency)


def convert_currency(base_currency, destination_currency, amount):
    assert base_currency in KNOWN_CURRENCIES, base_currency
    assert destination_currency in KNOWN_CURRENCIES, destination_currency
    currency_converter = config.get("currency_converter")
    if currency_converter == "gnu-units":
        output = os.popen('units --terse -- {}{} {}'.format(amount, base_currency, destination_currency)).read()
        return float(output.strip())
    elif currency_converter == "forex-python":
        return currency_converter.convert(base_currency, destination_currency, amount)
    raise RuntimeException("Unknown currency_converter. Should be either forex-python or gnu-units.")


class CachedCurrencyRates(CurrencyRates):
    """Caches currency rates that have already been fetched for great speed up."""
    cache = {}

    def convert(self, base_cur, dest_cur, amount, given_date=date.today()):
        assert base_cur, "We can't proceed w/o knowing the base currency."
        assert dest_cur, "We can't proceed w/o knowing the destination currency."
        # Look in db:
        db_rate = DBCurrencyRate.get_or_none(currency_a=base_cur, currency_b=dest_cur, date=given_date)
        if db_rate:
            return db_rate.rate * amount
        db_rate = DBCurrencyRate.get_or_none(currency_a=dest_cur, currency_b=base_cur, date=given_date)
        if db_rate:
            return 1 / db_rate.rate

        # Look it up online:
        log.debug("Fetching rate: {}-{}".format(base_cur, dest_cur))
        rate = super(CachedCurrencyRates, self).convert(base_cur, dest_cur, 1, given_date)
        DBCurrencyRate(currency_a=base_cur, currency_b=dest_cur, rate=rate, date=given_date).save()
        return rate * amount


currency_converter = CachedCurrencyRates()
