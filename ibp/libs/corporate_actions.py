import csv
import re
from collections import defaultdict, namedtuple
from datetime import datetime

from .logging import log

CorporateAction = namedtuple(
    "CorporateAction", ["date", "symbol_ib", "ratio", "currency", "security_id_old", "security_id_new"]
)


class CorporateActionParser(object):
    """Handles stock splits and merges to correct previous transaction prices accordingly."""

    actions = defaultdict(list)

    def __init__(self, reader):
        super(CorporateActionParser, self).__init__()
        self.reader = reader
        lines = self.reader.get_corporate_action_lines()
        reader = csv.reader(lines, delimiter=",")
        for row in reader:
            if not any(["Merged" in row[6], "Split" in row[6]]):
                continue
            currency = row[3]
            date_action = datetime.strptime(row[4], "%Y-%m-%d")
            old_symbol_ib = row[6].split("(")[0]
            security_id_old = row[6].split("(")[1].split(")")[0]
            security_id_new = row[6].split(",").pop().strip(" )")
            ratio = re.search(r"(\d+) for (\d+)", row[6], re.IGNORECASE).group()  # e.g 100 FOR 1
            num_old, _, num_new = ratio.split()
            ratio = float(num_old) / float(num_new)
            action = CorporateAction(date_action, old_symbol_ib, ratio, currency, security_id_old, security_id_new)
            symbol = action.symbol_ib
            if symbol.endswith(".OLD"):
                symbol = symbol[:-4]
            self.actions[symbol].append(action)

    def apply_actions(self, transactions):
        applied_actions = []
        for t in transactions:
            if not any([s in self.actions for s in t.instrument.get_all_known_symbols()]):
                continue
            for a in self.actions[t.instrument.symbol_ib]:
                key = "{}-{}-{}".format(a.date, a.symbol_ib, t.timestamp)
                if a.date < t.timestamp or a.currency != t.instrument.currency or key in applied_actions:
                    continue
                t.amount = t.amount * a.ratio
                t.transaction_price = t.transaction_price / a.ratio
                applied_actions.append(key)
                log.info(
                    "Applying {}: {} {}".format("split" if a.ratio < 1 else "merge", a.ratio, t.instrument.symbol_ib)
                )
