import csv
from collections import namedtuple
from datetime import datetime, timedelta

from .config import config
from .corporate_actions import CorporateActionParser
from .helpers import get_latest_file
from .money import Money
from .parser import CSVReader
from .transactions import TransactionParser

PositionTuple = namedtuple(
    "PositionTuple",
    [
        "currency",
        "symbol_ib",
        "amount",
        "price_average",
        "value_cost",  # How much money the entire position has cost
        "price_now",
        "value_now",
        "delta_absolute",
        "delta_percentage",
        "portfolio_weight",
    ],
)


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

    def get_positions(self):
        reader = csv.reader(self.position_lines, delimiter=",")
        positions = []
        for row in reader:
            row = row[4:]
            (
                currency,
                symbol_ib,
                _,
                amount,
                _,
                price_average,
                value_cost,
                price_now,
                value_now,
                delta_absolute,
                portfolio_weight,
                _,
            ) = row
            value_cost = Money(float(value_cost), currency)
            value_now = Money(float(value_now), currency)
            price_now = Money(float(price_now), currency)
            price_average = Money(float(price_average), currency)
            delta_absolute = Money(float(delta_absolute), currency)
            if delta_absolute.as_float < 0:
                delta_percentage = ((value_cost - value_now) / value_cost).as_float * -1
            else:
                delta_percentage = ((value_now - value_cost) / value_cost).as_float

            if self.filter_currency and self.filter_currency != currency:
                continue
            position = PositionTuple(
                currency,
                symbol_ib,
                int(amount),
                price_average,
                value_cost,
                price_now,
                value_now,
                delta_absolute,
                delta_percentage,
                portfolio_weight,
            )
            positions.append(position)
        return positions

    def print_positions(self):
        positions = self.get_positions()
        positions = sorted(positions, key=self._get_sort_lambda(self.sort_order))
        if self.sort_order.endswith("_r"):
            positions = positions[::-1]
        for p in positions:
            columns = [
                "{}".format(p.currency),
                "{:7.7}".format(p.symbol_ib),
                "{:6}".format(p.amount),
                "{:10.3f}".format(p.price_average),
                "{:10.3f}".format(p.price_now),
                "{:10,.0f}".format(p.value_cost),
                "{:10,.0f}".format(p.value_now),
                "{:+10,.0f}".format(p.delta_absolute),
                "{:+.2%}".format(p.delta_percentage),
            ]
            if self.machine_readable:
                print(";".join([c.strip() for c in columns]))
            else:
                print("  ".join(columns))

    def _get_sort_lambda(self, sort_order):
        if sort_order.endswith("_r"):
            sort_order = sort_order[:-2]
        methods = {
            "symbol": lambda x: x.symbol_ib,
            "amount": lambda x: x.amount,
            "value": lambda x: x.value_now,
            "percent": lambda x: x.delta_percentage,
            "absolut": lambda x: x.delta_absolute,
        }
        assert sort_order in methods
        return methods.get(sort_order)

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
    p = Portfolio(reader, instruments_filter, display_currency, filter_currency, machine_readable, sort_order)
    p.print_positions()
