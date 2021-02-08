import json
from urllib import request
from urllib.parse import quote

from .constants import YAHOO_EXCHANGE_TO_CURRENCY
from .logging import log


def get_yahoo_json_search_result(query):
    """
    Parses json search result retrieved from the same url yahoo uses when one enters a query in the search field on
    finance.yahoo.com.
    """
    log.debug("Query yahoo: {}".format(query))
    url = "https://query1.finance.yahoo.com/v1/finance/search?q={}".format(quote(query))
    my_request = request.urlopen(url)
    response = my_request.read().decode("utf-8")
    response = json.loads(response)
    if len(response["quotes"]) == 0:
        log.debug("{:12}: No quotes found.".format(query))
        return None, None, None
    symbol = response["quotes"][0]["symbol"]
    try:
        name = response["quotes"][0]["longname"]
    except KeyError:
        name = symbol
    exchange = response["quotes"][0]["exchange"]
    currency = YAHOO_EXCHANGE_TO_CURRENCY.get(exchange)
    if not currency:
        # can mean that this exchange's currency is not any of our base currencies used for transactions
        log.warning("Unknown currency for yahoo exchange: {} ({}, {})".format(exchange, symbol, name))

    log.debug("{:12}: Found {} | {}".format(symbol, name, currency))
    return symbol, name, currency
