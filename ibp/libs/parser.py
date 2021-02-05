import glob
import re
from os import path

from .logging import log


class CSVReader(object):
    """Base class to get relevant parts from IB csv files"""

    money_move_pattern = r"^Deposits & Withdrawals,Data,[A-Z]{3}"
    dividend_pattern = r"^Dividends,Data,[A-Z]{3}"
    instrument_pattern = r"^Financial Instrument Information,Data,Stocks"
    transaction_pattern = r"^Trades,Data,Order,Stocks"
    transaction_pattern = r"^Trades,Data,Order,Stocks"
    corporate_action_pattern = r"^Corporate Actions,Data,Stocks"
    patterns = [dividend_pattern, instrument_pattern, transaction_pattern, money_move_pattern, corporate_action_pattern]
    relevant_lines = {}

    def __init__(self, csv_folder):
        log.debug("{}.__init__".format(self.__class__.__name__))
        csv_folder_glob = glob.glob(path.join(path.expanduser(csv_folder), "*.csv"))
        assert csv_folder_glob, "Not any matching files found: {}".format(csv_folder)
        self.files = sorted(csv_folder_glob)
        for p in self.patterns:
            self.relevant_lines[p] = []
        self.get_relevant_lines()

    def get_relevant_lines(self):
        lines = []
        log.debug("Search lines {}".format(", ".join(self.patterns)))
        for csv_filename in self.files:
            log.debug("In file {}".format(csv_filename))
            with open(csv_filename, "r") as csv_file:
                for line in csv_file.readlines():
                    for pattern in self.patterns:
                        if re.match(pattern, line):
                            self.relevant_lines[pattern].append(line)
        return lines

    def get_instrument_lines(self):
        return self.relevant_lines[self.instrument_pattern]

    def get_dividend_lines(self):
        return self.relevant_lines[self.dividend_pattern]

    def get_transaction_lines(self):
        return self.relevant_lines[self.transaction_pattern]

    def get_money_move_lines(self):
        return self.relevant_lines[self.money_move_pattern]

    def get_corporate_action_lines(self):
        """Splits and merges"""
        return self.relevant_lines[self.corporate_action_pattern]
