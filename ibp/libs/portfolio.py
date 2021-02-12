import csv
from datetime import datetime, timedelta

from .config import config
from .corporate_actions import CorporateActionParser
from .helpers import get_latest_file
from .money import Money
from .parser import CSVReader
from .transactions import TransactionParser


class Position:
    def __init__(self, instrument, amount, price):
        self.instrument = instrument
        self.amount = round(amount)
        self.price_average = price
        self.price_now = self.instrument.get_price()
        self.value = self.price_now * self.amount

    def __repr__(self):
        return "<{} {} @ {}>".format(self.amount, self.instrument.ib, self.price_average)

    def update(self, transaction):
        """Updates the position of a instrument with the content of another transaction."""
        self.amount = round(self.amount + transaction.amount)
        if self.amount == 0:  # position was sold
            return None
        self.price_average = self._calculate_average_price(transaction.amount, transaction.transaction_price)
        return self

    def _calculate_average_price(self, amount_new, price_new):
        if self.amount + amount_new == 0:
            return self.price_average
        old = self.amount * self.price_average
        new = amount_new * price_new
        total_value = old + new
        total_amount = self.amount + amount_new
        return total_value / total_amount

    def get_delta_price(self, delta_in_days_from_today):
        """Get prices in the past: -1d, -7d etc. """
        day = datetime.now() + timedelta(days=delta_in_days_from_today)
        return self.instrument.get_price(day)

    def get_delta_price_percentage(self, delta_in_days_from_today):
        """Get prices in the past in percentage as delta to price today: -1d, -7d etc. """
        day = datetime.now() + timedelta(days=delta_in_days_from_today)
        return self.price_now / self.instrument.get_price(day)


class Portfolio(object):

    portfolio = {}

    def __init__(
        self,
        reader,
        instruments_filter=None,
        display_currency=None,
        filter_currency=None,
        machine_readable=False,
        sort_order=None,
    ):
        self.instruments_filter = instruments_filter
        self.display_currency = display_currency
        self.filter_currency = filter_currency
        self.machine_readable = machine_readable
        self.sort_order = sort_order or "name"
        transactions = TransactionParser(reader, instruments_filter, display_currency).get_csv_transactions()
        CorporateActionParser(reader).apply_actions(transactions)
        self._get_open_postions(transactions)
        self._set_portfolio_weight()

    def _get_open_postions(self, transactions):
        """Answer to what positions the transactions sum up to."""
        for t in transactions:
            position = self.portfolio.get(t.instrument.con_id)
            if position:
                position = position.update(t)
                if not position:  # position was sold
                    del self.portfolio[t.instrument.con_id]
                    continue
            else:
                position = Position(t.instrument, round(t.amount), t.transaction_price)

            self.portfolio[t.instrument.con_id] = position

    def _set_portfolio_weight(self):
        """
        Set for each position how much % of the total value it presents. Only makes sense once all transactions are
        parsed,
        """
        portfolio_value = sum((p.value for p in self.portfolio.values()))
        for p in self.portfolio.values():
            p.weight = (p.price_now * p.amount / portfolio_value).as_float

    def _get_sort_lambda(self, sort_order):
        if sort_order.endswith("_r"):
            sort_order = sort_order[:-2]
        methods = {
            "name": lambda x: x.instrument.name,
            "amount": lambda x: x.amount,
            "symbol": lambda x: x.instrument.symbol_yahoo,
        }
        return methods.get(sort_order)

    def print(self):
        positions = sorted(self.portfolio.values(), key=self._get_sort_lambda(self.sort_order))
        if self.sort_order.endswith("_r"):
            positions = positions[::-1]
        for p in positions:
            columns = [
                "{}".format(p.instrument.currency),
                "{:18.18}".format(p.instrument.name),
                "{:7.7}".format(p.instrument.symbol_yahoo),
                "{:7,}".format(p.amount),
                "{:7.3f}".format(p.price_average),
                "{:7.3f}".format(p.price_now),
                # "{:n}".format(p.get_delta_price(-7)),
                # "{:n}".format(p.get_delta_price(-14)),
                # "{:n}".format(p.get_delta_price(-30)),
                # "{:n}".format(p.get_delta_price(-60)),
                # "{:n}".format(p.get_delta_price(-90)),
                # "{:7.1%}".format(p.price_change_percentage),
                "{:5.1%}".format(p.weight),
            ]
            # here we need to wait for all promises to have reached
            if self.machine_readable:
                print(";".join([c.strip() for c in columns]))
            else:
                print("  ".join(columns))


class Portfolio2(object):
    portfolio = {}

    def __init__(
        self,
        reader,
        instruments_filter=None,
        display_currency=None,
        filter_currency=None,
        machine_readable=False,
        sort_order=None,
    ):
        self.reader = reader
        self.instruments_filter = instruments_filter
        self.display_currency = display_currency
        self.filter_currency = filter_currency
        self.machine_readable = machine_readable
        self.sort_order = sort_order or "name"
        self.position_lines = reader.get_position_lines()
        self.get_portfolio_metadata()
        self.total_stock_value, self.base_currency = self.get_portfolio_metadata()

    def print_positions(self):
        reader = csv.reader(self.position_lines, delimiter=",")
        positions = []
        for row in reader:
            row = row[4:]
            currency, symbol_ib, _, amount, _, price_average, value_cost, price_now, value_now, value_delta, \
                portfolio_weigth, _ = row
            if self.filter_currency and self.filter_currency != currency:
                continue
            columns = [
                "{}".format(currency),
                "{:7.7}".format(symbol_ib),
                "{:6}".format(int(amount)),
            ]
            print("  ".join(columns))

    def get_portfolio_metadata(self):
        """
        Determine total stock value (needed for calculating weight of each position) and base currency (currency IB
        uses for unrealized profits, fees etc.)
        """
        metadata = self.reader.get_portfolio_lines()
        base_currency = metadata[0].split(",").pop().strip()
        nav_total = Money(float(metadata[1].split(",")[6]), base_currency)
        return nav_total, base_currency


def main(instruments_filter, display_currency, filter_currency, machine_readable, sort_order):
    csv_path = config.get("csv_path")
    latest = get_latest_file(csv_path)
    reader = CSVReader(files=[latest], patterns=[CSVReader.position_pattern, CSVReader.portfolio_pattern])
    p = Portfolio2(reader, instruments_filter, display_currency, machine_readable, sort_order)
    p.print_positions()
