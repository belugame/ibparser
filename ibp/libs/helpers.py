import argparse
from datetime import date, datetime, timedelta


def parse_date_delta(date_delta):
    """Parse a string given from command line like '10d' to a negative timedelta reaching back 10 days from now"""
    if not date_delta:
        return None

    if date_delta == "ytd":
        return datetime(date.today().year, 1, 1)
    elif "--" in date_delta:
        first, second = date_delta.split("--")
        first = datetime.strptime(first, "%Y-%m-%d")
        if second:
            second = datetime.strptime(second, "%Y-%m-%d")
            second = second.replace(hour=23, minute=59, second=59, microsecond=999)
        else:
            second = datetime(year=9999, month=1, day=1)
        return first, second
        return second, first
    else:
        quantifier = {"d": "days", "w": "weeks"}[date_delta[-1]]
        kwargs = {quantifier: int(date_delta[:-1])}
        return datetime.today() - timedelta(**kwargs)


def get_common_argument_parser(description):
    """Provides argument definitions valid for more than one use case."""
    parser = argparse.ArgumentParser(description=description)
    subparsers = parser.add_subparsers(title='mode')

    transactions = subparsers.add_parser("transactions")
    group = transactions.add_mutually_exclusive_group()
    group.add_argument('-s', dest="only_sell", help='Only show sell transactions', action='store_true')
    group.add_argument('-b', dest="only_buy", help='Only show buy transactions', action='store_true')
    add_common_arguments(transactions)

    dividends = subparsers.add_parser('dividends')
    add_common_arguments(dividends)

    portfolio = subparsers.add_parser('portfolio')
    portfolio.add_argument('-o', dest="sort_order", type=str.lower, help='Column name for sorting')
    add_common_arguments(portfolio)

    deposits = subparsers.add_parser('deposits')
    add_common_arguments(deposits, instruments_filter=False)

    report_realized = subparsers.add_parser('report_realized')
    add_common_arguments(report_realized, machine_readable=False)

    return parser


def add_common_arguments(parser, instruments_filter=True, machine_readable=True):
    if instruments_filter:
        parser.add_argument('instruments_filter', nargs=argparse.REMAINDER, type=str.upper,
                            help='One or more instruments to filter for')
    parser.add_argument('-c', dest="display_currency", type=str.upper, help='Convert all amounts to given currency')
    parser.add_argument('-f', dest="filter_currency", type=str.upper, help='Limit output to items of given currency')
    parser.add_argument('-m', dest="machine_readable", help='Make output CSV-like (no padding of data)',
                        action='store_true')
    parser.add_argument('-d', dest="date_delta", type=str.lower,
                        help='Limit output to given date range. E.g. 2w for past two weeks, or ytd for year-to-date')


def ignore_due_time_constraint(date_delta, timestamp):
    """Checks if an item should be excluded because it is outside of a given time period."""
    if not date_delta:
        return False
    if isinstance(date_delta, datetime):
        return timestamp < date_delta
    start, end = date_delta
    return not start <= timestamp <= end
