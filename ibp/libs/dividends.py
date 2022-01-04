import csv
import re
from collections import namedtuple
from datetime import datetime

from .config import config
from .helpers import ignore_due_time_constraint, parse_date_delta
from .instruments import db, ignore_instrument
from .logging import log
from .money import Money
from .parser import CSVReader

Dividend = namedtuple("Dividend", ["timestamp", "currency", "instrument", "amount_total"])


class Dividend(object):
    def __init__(self, timestamp, currency, instrument, amount, description):
        self.timestamp = timestamp
        self.currency = currency
        self.instrument = instrument
        self.amount = amount
        self.description = description

    def __repr__(self):
        return "<{}: {} {:.2f}>".format(self.timestamp, self.instrument, self.amount)


class DividendParser(object):
    """Creates a csv-like report for dividends received """

    def __init__(
        self,
        reader,
        instruments_filter=None,
        display_currency=None,
        filter_currency=None,
        date_delta=None,
        machine_readable=False,
    ):
        self.reader = reader
        self.instruments_filter = instruments_filter
        self.display_currency = display_currency
        self.filter_currency = filter_currency
        self.machine_readable = machine_readable
        self.date_delta = parse_date_delta(date_delta)
        super(DividendParser, self).__init__()

    def parse_dividend_lines(self):
        """Reads dividends received lines (=not accruals) from IB monthly statements into a list of namedtuples"""
        lines = self.reader.get_dividend_lines()
        reader = csv.reader(lines, delimiter=",")
        dividends = {}
        for row in reader:
            if re.match(r"^U\d+$", row[3]):
                _, _, currency, _, date_activity, description, amount = row
            else:
                _, _, currency, date_activity, description, amount = row

            date_activity = datetime.strptime(date_activity, "%Y-%m-%d")
            if self.filter_currency and self.filter_currency != currency:
                continue
            if ignore_due_time_constraint(self.date_delta, date_activity):
                continue
            symbol_ib = description.split("(")[0].strip()
            if ignore_instrument(None, [symbol_ib], self.instruments_filter):
                continue
            security_id = description.split("(")[1].split(")")[0]
            if len(currency.split()[0]) == 3:
                currency = currency.split()[0]
            else:
                currency = currency.split()[1]
            db_instrument = db.get_by_symbol_ib(symbol_ib)
            if not db_instrument:
                db_instrument = db.get_by_security_id(security_id)

            amount = Money(float(amount), currency)
            key = "{}-{}-{}-{}".format(date_activity, symbol_ib, security_id, amount.as_float)
            if key in dividends:
                d = dividends[key]
                if d.description == description and "LU0378438732" not in description:
                    log.debug("Skipping duplicate dividend: {}".format(key))
                    continue
                dividends[key + "-2"] = Dividend(date_activity, currency, db_instrument, amount, description)
            else:
                dividends[key] = Dividend(date_activity, currency, db_instrument, amount, description)
        return sorted(dividends.values(), key=lambda d: d.timestamp)

    def print_dividends(self, dividends):
        total = 0.0
        for d in dividends:
            amount = d.amount.convert_to(self.display_currency) if self.display_currency else d.amount
            columns = [
                "{}".format(d.timestamp.strftime("%Y-%m-%d")),
                "{}".format(d.currency),
                "{:18.18}".format(d.instrument.name),
                "{:7.7}".format(d.instrument.symbol_yahoo),
                "{:7.2f}".format(amount),
            ]
            total += amount
            if self.machine_readable:
                print(";".join([c.strip() for c in columns]))
            else:
                print("  ".join(columns))
        print("Total: {:,.2f}".format(total))


def main(instruments_filter=None, display_currency=None, filter_currency=None, date_delta=None, machine_readable=False):
    reader = CSVReader(config.get("csv_path"))
    parser = DividendParser(reader, instruments_filter, display_currency, filter_currency, date_delta, machine_readable)
    dividends = parser.parse_dividend_lines()
    parser.print_dividends(dividends)
