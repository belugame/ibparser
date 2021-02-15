from datetime import timedelta
from itertools import chain

import matplotlib.pyplot as plt
import pandas as pd

from .config import config
from .dividends import DividendParser
from .helpers import get_latest_file
from .parser import CSVReader
from .portfolio import Portfolio
from .transactions import Transaction, TransactionParser


def main():
    csv_path = config.get("csv_path")
    reader = CSVReader(csv_path)
    transactions = TransactionParser(reader).get_csv_transactions()
    latest = get_latest_file(csv_path)
    reader = CSVReader(files=[latest], patterns=[CSVReader.position_pattern, CSVReader.portfolio_pattern])
    portfolio = Portfolio(reader)
    __import__("pudb").set_trace()
    for t in transactions:
        transaction_portfolio[t.instrument] += t.amount


if __name__ == "__main__":
    sys.exit(main())
