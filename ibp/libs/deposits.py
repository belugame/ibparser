import csv
from datetime import datetime
from collections import namedtuple

from .config import config
from .helpers import parse_date_delta, ignore_due_time_constraint
from .parser import CSVReader
from .money import Money


MoneyMove = namedtuple("MoneyMove", ["date", "currency", "amount", "description"])


class MoneyMoveParser(object):
    """Creates a csv-like report for deposits and withdrawals received """

    def __init__(self, reader, display_currency=None, date_delta=None, machine_readable=False, filter_currency=None):
        self.reader = reader
        self.display_currency = display_currency
        self.filter_currency = filter_currency
        self.machine_readable = machine_readable
        self.date_delta = parse_date_delta(date_delta)
        super(MoneyMoveParser, self).__init__()

    def parse_money_lines(self):
        lines = self.reader.get_money_move_lines()
        reader = csv.reader(lines, delimiter=",")
        moves = {}
        for row in reader:
            row = row[2:6]
            currency, date_activity, description, amount = row
            date_activity = datetime.strptime(date_activity, "%Y-%m-%d")
            if self.filter_currency and self.filter_currency != currency:
                continue
            if ignore_due_time_constraint(self.date_delta, date_activity):
                continue
            amount = Money(float(amount), currency)
            key = "{}-{}-{}-{}".format(date_activity, amount, description, currency)
            if key not in moves:
                moves[key] = MoneyMove(date_activity, currency, amount, description)
        return moves

    def print_money_moves(self, dividends):
        total = 0.0
        for d in dividends:
            amount = d.amount.convert_to(self.display_currency) if self.display_currency else d.amount
            columns = [
                "{}".format(d.date.strftime("%Y-%m-%d")),
                "{}".format(d.currency),
                "{:12,.2f}".format(amount),
                "{}".format(d.description),
            ]
            total += amount
            if self.machine_readable:
                print(";".join([c.strip() for c in columns]))
            else:
                print("  ".join(columns))
        print("Total: {:,.2f}".format(total))


def main(display_currency=None, date_delta=None, machine_readable=False, filter_currency=None):
    reader = CSVReader(config.get("csv_path"))
    parser = MoneyMoveParser(reader, display_currency, date_delta, machine_readable, filter_currency)
    money_moves = sorted(parser.parse_money_lines().values(), key=lambda d: d.date)
    parser.print_money_moves(money_moves)
