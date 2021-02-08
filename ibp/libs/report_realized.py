from itertools import chain

import matplotlib.pyplot as plt
import pandas as pd

from .config import config
from .dividends import DividendParser
from .parser import CSVReader
from .transactions import Transaction, TransactionParser


class ReportRealized(object):
    """Create date-value series of accumulated realized profits"""

    def __init__(self, transactions, dividends, display_currency):
        super(ReportRealized, self).__init__()
        self.display_currency = display_currency or config.get("default_currency")
        self.transactions = transactions
        self.dividends = dividends

    def print_report(self):
        items = sorted(chain(self.transactions, self.dividends), key=lambda x: x.timestamp)
        if not items:
            print("Nothing to show")
            return
        dates = []
        realized = []
        dividends = []
        for item in items:
            dates.append(pd.Timestamp(item.timestamp))
            if isinstance(item, Transaction):
                realized.append(item.realized.convert_to(self.display_currency).as_float)
                dividends.append(0.0)
            else:
                dividends.append(item.amount.convert_to(self.display_currency).as_float)
                realized.append(0.0)

        data = {"realized": realized, "dividends": dividends}
        df = pd.DataFrame(data=data, index=dates)
        df = df.groupby(level=0).sum()  # Sum up 2 dividends on same day into one entry
        print(df)
        df = df.cumsum()
        df = df.resample("M").pad()
        df["total return"] = df[["realized", "dividends"]].sum(1)
        df.plot(drawstyle="steps-post")
        plt.savefig("saved_figure.png")


def main(instruments_filter, date_delta, display_currency):
    reader = CSVReader(config.get("csv_path"))
    transactions = TransactionParser(
        reader,
        instruments_filter,
        only_sell=True,
        display_currency=display_currency,
        date_delta=date_delta,
        machine_readable=True,
    ).get_csv_transactions()
    dividends = DividendParser(
        reader, instruments_filter, display_currency=display_currency, date_delta=date_delta, machine_readable=True
    ).parse_dividend_lines()
    ReportRealized(transactions, dividends, display_currency=display_currency).print_report()
