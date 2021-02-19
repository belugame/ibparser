from collections import defaultdict
from datetime import timedelta
from itertools import chain

import matplotlib.pyplot as plt
import pandas as pd

from .config import config
from .corporate_actions import CorporateActionParser
from .dividends import DividendParser
from .helpers import get_latest_file
from .parser import CSVReader
from .portfolio import Portfolio
from .transactions import Transaction, TransactionParser


def main():
    csv_path = config.get("csv_path")
    reader = CSVReader(csv_path)
    transactions = TransactionParser(reader).get_csv_transactions()
    CorporateActionParser(reader).apply_actions(transactions)
    latest = get_latest_file(csv_path)
    reader = CSVReader(files=[latest], patterns=[CSVReader.position_pattern, CSVReader.portfolio_pattern])
    portfolio = Portfolio(reader)
    transaction_portfolio = defaultdict(int)
    for t in transactions:
        transaction_portfolio[t.instrument.symbol_ib] += t.amount
    for p in portfolio.get_positions():
        if not p.amount == transaction_portfolio[p.symbol_ib]:
            print(
                "Amount mismatch for {:7}: Portfolio {:8}  Transactions {:8}".format(
                    p.symbol_ib, p.amount, transaction_portfolio[p.symbol_ib]
                )
            )


if __name__ == "__main__":
    sys.exit(main())
