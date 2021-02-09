import sys

from .libs.deposits import main as deposits_main
from .libs.dividends import main as dividends_main
from .libs.helpers import get_common_argument_parser
from .libs.portfolio import main as portfolio_main
from .libs.report_realized import main as report_realized_main
from .libs.transactions import main as transactions_main


def main():
    parser = get_common_argument_parser("ibparser")
    sysargs = sys.argv[1:]
    modes = {"t": "transactions", "d": "dividends", "e": "deposits", "p": "portfolio", "rr": "report_realized"}
    modes_msg = "Possible values: {}".format(", ".join(modes.values()))
    if len(sysargs) > 0:
        if sysargs[0] in modes.keys():
            sysargs[0] = modes[sysargs[0]]
        elif sysargs[0] not in modes.values():
            raise RuntimeError("Unexpected mode '{}'. {}".format(sysargs[0], modes_msg))

    args = parser.parse_args(sysargs)
    if sysargs[0] == "transactions":
        transactions_main(
            args.instruments_filter,
            args.only_sell,
            args.only_buy,
            args.display_currency,
            args.filter_currency,
            args.date_delta,
            args.machine_readable,
        )
    elif sysargs[0] == "dividends":
        dividends_main(
            args.instruments_filter, args.display_currency, args.filter_currency, args.date_delta, args.machine_readable
        )
    elif sysargs[0] == "deposits":
        deposits_main(args.display_currency, args.filter_currency, args.date_delta, args.machine_readable)
    elif sysargs[0] == "portfolio":
        portfolio_main(
            args.instruments_filter, args.display_currency, args.filter_currency, args.machine_readable, args.sort_order
        )
    elif sysargs[0] == "report_realized":
        report_realized_main(
            instruments_filter=args.instruments_filter,
            date_delta=args.date_delta,
            display_currency=args.display_currency,
        )
    elif not sysargs[0]:
        raise RuntimeError("Missing mode. {}.".format(modes_msg))


if __name__ == "__main__":
    sys.exit(main())
