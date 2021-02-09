import csv
import re
from collections import namedtuple
from datetime import date, datetime

from .config import config
from .corporate_actions import CorporateActionParser
from .helpers import ignore_due_time_constraint, parse_date_delta
from .instruments import InstrumentCollection, ignore_instrument
from .logging import log
from .parser import CSVReader
from .prices import Money

TransactionRowFormat1 = namedtuple(
    "TransactionFormat1",
    [
        "currency",
        "symbol_ib",
        "timestamp",
        "amount",
        "transaction_price",
        "c_price",
        "transaction_total",
        "fee",
        "basis",
        "realized",
        "realized_percent",
        "mtm",
        "code",
    ],
)
TransactionRowFormat2 = namedtuple(
    "TransactionFormat2",
    [
        "currency",
        "symbol_ib",
        "timestamp",
        "blank",
        "amount",
        "transaction_price",
        "c_price",
        "transaction_total",
        "fee",
        "basis",
        "realized",
        "realized_percent",
        "mtm",
        "code",
    ],
)
TransactionRowFormat3 = namedtuple(
    "TransactionFormat3",
    [
        "currency",
        "symbol_ib",
        "timestamp",
        "amount",
        "transaction_price",
        "c_price",
        "transaction_total",
        "fee",
        "basis",
        "realized",
        "mtm",
        "code",
    ],
)
TransactionRowFormat4 = namedtuple(
    "TransactionFormat4",
    [
        "currency",
        "symbol_ib",
        "timestamp",
        "exchange",
        "amount",
        "transaction_price",
        "c_price",
        "transaction_total",
        "fee",
        "basis",
        "realized",
        "mtm",
        "code",
    ],
)


class Transaction(object):
    """
    Represents a buy or sell transaction based on a csv row. Adds information that we calculate or fetch from
    3rd party to the CSV data.
    """

    def __init__(
        self, timestamp, instrument, amount, transaction_price, fee, realized, transaction_total, realized_percent
    ):
        # log.debug("{}.__init__".format(self))
        self.timestamp = timestamp
        self.instrument = instrument
        self.amount = amount
        self.transaction_price = transaction_price
        self.fee = fee
        self.realized = realized
        self.transaction_total = transaction_total
        self.realized_percent = realized_percent

    def __repr__(self):
        return "<{}: {} {}>".format(self.timestamp, self.instrument.symbol_ib, self.amount)

    @property
    def price_today(self):
        return self.instrument.get_price()

    @property
    def price(self):
        """The per-stock price the stock was sold/bought for."""
        if self.transaction_price.as_float == 0.0:
            # Happens e.g. when a new stock emerges from a spin-off
            # We did not pay for these but we cannot calculate with zero
            return Money(0.01, self.instrument.currency)
        # Distributes fee over each share bought/sold
        return self.transaction_price - (self.fee / self.amount)

    @property
    def price_base(self):
        """For sell-transactions this returns the original buy-price"""
        return self.transaction_total / self.amount

    @property
    def days_held(self):
        if self.amount < 0:
            return 0
        return int((date.today() - self.timestamp.date()).days)

    @property
    def action(self):
        return "Bought" if self.amount > 0 else "Sold"

    @property
    def unrealized_percent(self):
        return (self.price_today / self.price).as_float - 1


class TransactionParser(object):
    """Creates a csv-like report with stock orders (buy/sell actions)"""

    def __init__(
        self,
        reader,
        instruments_filter=None,
        only_sell=False,
        only_buy=False,
        display_currency=None,
        filter_currency=None,
        date_delta=None,
        machine_readable=False,
    ):
        self.reader = reader
        self.instruments = InstrumentCollection(reader, instruments_filter)
        self.only_sell = only_sell
        self.only_buy = only_buy
        self.display_currency = display_currency
        self.filter_currency = filter_currency
        self.machine_readable = machine_readable
        self.date_delta = parse_date_delta(date_delta)
        super(TransactionParser, self).__init__()

    def get_csv_transactions(self):
        """
        Reads share sell/buy items from IB csv statements into a list of namedtuples
        Sample line:
        Trades,Data,Order,Stocks - Held (...) LLC,AUD,AEF,"2019-06-16, 20:09:34",500,1.85,1.775,-925,-6,931,0,0,-37.5,O
        """
        lines = self.reader.get_transaction_lines()
        reader = csv.reader(lines, delimiter=",")
        self.transactions = []
        for row in reader:
            transaction = self._parse_row_to_namedtuple(row)
            transaction = self._namedtuple_to_instance(transaction)
            if transaction:  # not-True here means this transaction should be ignored (duplicate, filtered out, etc)
                self.transactions.append(transaction)
        self.transactions = sorted(self.transactions, key=lambda t: t.timestamp)
        return self.transactions

    def _parse_row_to_namedtuple(self, row):
        """Single line in csv file to python namedtuple w/o adding or calculating additional data"""
        row_starts = (
            [
                "Trades",
                "Data",
                "Order",
                "Stocks - Held with Interactive Brokers (U.K.) Limited carried by Interactive Brokers LLC",
            ],
            ["Trades", "Data", "Order", "Stocks"],
        )
        assert row[:4] in row_starts, row
        row = row[4:]
        if len(row) == 13:
            if re.match(r"^-?[\d,]+$", row[3]):
                transaction = TransactionRowFormat1(*row)
            else:
                transaction = TransactionRowFormat4(*row)
        elif len(row) == 14:
            transaction = TransactionRowFormat2(*row)
        elif len(row) == 12:
            transaction = TransactionRowFormat3(*row)
        else:
            raise Exception("Unknown transaction row format. Length {}. {}".format(len(row), row))
        return transaction

    def _namedtuple_to_instance(self, transaction_tuple):
        if ignore_instrument(
            None, [transaction_tuple.symbol_ib], self.instruments.instrument_filter, transaction_tuple.currency
        ):
            return None
        if self.filter_currency and self.filter_currency != transaction_tuple.currency:
            return None
        timestamp = datetime.strptime(transaction_tuple.timestamp, "%Y-%m-%d, %H:%M:%S")
        if ignore_due_time_constraint(self.date_delta, timestamp):
            return None
        amount = float(transaction_tuple.amount.replace(",", ""))
        amount = int(amount) if amount.is_integer() else amount  # removes ".0" if even amount
        if amount == 0:
            log.debug("{} {}: Ignore 0 amount transaction".format(timestamp, transaction_tuple.symbol_ib))
            return None
        if self.only_sell and amount > 0:
            return None
        if self.only_buy and amount < 0:
            return None
        fee = Money(float(transaction_tuple.fee), transaction_tuple.currency)
        realized = Money(float(transaction_tuple.realized), transaction_tuple.currency)
        transaction_price = Money(float(transaction_tuple.transaction_price), transaction_tuple.currency)
        transaction_total = Money(float(transaction_tuple.transaction_total), transaction_tuple.currency)
        instrument = self.instruments.get(transaction_tuple.symbol_ib, transaction_tuple.currency)
        instrument.get_price_in_background()
        try:
            realized_percent = float(transaction_tuple.realized_percent) / 100
        except AttributeError:
            realized_percent = None

        transaction = Transaction(
            timestamp, instrument, amount, transaction_price, fee, realized, transaction_total, realized_percent
        )
        if [
            t
            for t in self.transactions
            if t.timestamp == transaction.timestamp and t.instrument == transaction.instrument
        ]:
            return None  # Avoids trades that are in more than one csv to be added more than once
        return transaction

    def print_transactions(self):
        transactions = self.get_csv_transactions()
        CorporateActionParser(self.reader).apply_actions(transactions)
        total_realized = 0
        for t in [t for t in transactions]:
            columns = [
                "{}".format(t.timestamp.strftime("%Y-%m-%d")),
                "{}".format(t.instrument.currency),
                "{:18.18}".format(t.instrument.name),
                "{:7.7}".format(t.instrument.symbol_yahoo),
                "{:6.0f}".format(t.amount),
            ]
            assert t.price_today.as_float != 0.0, "{}: {}".format(t, t.price_today)
            assert t.price.as_float != 0.0, "{}: {}".format(t, t.price)
            if self.display_currency:
                price = t.price.convert_to(self.display_currency)
                price_today = t.price_today.convert_to(self.display_currency)
            else:
                price = t.price
                price_today = t.price_today
            columns += [
                "{:7.3f}".format(price),
                "{:7.2f}".format(price_today),
                "{:+7,.0f}".format(-1 * t.amount * price),
            ]

            columns.append("{:7.1%}".format(t.unrealized_percent))

            if t.amount < 0:
                if self.display_currency:
                    amount_realized = t.realized.convert_to(self.display_currency)
                    total_realized += amount_realized
                else:
                    amount_realized = t.realized
                    total_realized += t.realized
                columns.append("{:9.2f}".format(amount_realized))
                if t.realized_percent:
                    columns.append("{:.2%}".format(t.realized_percent))
            if self.machine_readable:
                print(";".join([c.strip() for c in columns]))
            else:
                print("  ".join(columns))
        print("Total: {:,.2f}".format(total_realized))


def main(instruments_filter, only_sell, only_buy, display_currency, filter_currency, date_delta, machine_readable):
    reader = CSVReader(config.get("csv_path"))
    p = TransactionParser(
        reader, instruments_filter, only_sell, only_buy, display_currency, filter_currency, date_delta, machine_readable
    )
    p.print_transactions()
