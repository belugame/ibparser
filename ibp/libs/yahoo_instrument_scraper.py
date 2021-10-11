import re
from difflib import SequenceMatcher
from time import sleep
from urllib import request
from urllib.error import HTTPError

from .config import config
from .exceptions import BadYahooSymbolError
from .logging import log


class YahooSymbolPageScraper(object):
    """
    Parses info from the yahoo finance page of a stock. E.g. https://finance.yahoo.com/quote/AEF.AX
    """

    # History of what has already been tried, but failed
    tried_symbols = []

    def __init__(self, symbol_ib, name=None, currency=None):
        # log.debug("{}.__init__".format(self.__class__.__name__))
        self.symbol_ib = symbol_ib.rstrip("d")  # in case of 'MXHNd' IB has a 'd' at the end which is of no use
        self.name = name
        self.currency = currency

    def fetch(self):
        """Returns yahoo's name of given stock symbol (makes guesses to find it)."""
        if not self.currency or self.currency == "USD":
            result = self.fetch_for_unknown_currency()
        elif self.currency == "EUR":
            result = self.fetch_for_eur(self.symbol_ib)
        elif self.currency == "AUD":
            result = self.fetch_for_aud(self.symbol_ib)
        elif self.currency == "CAD":
            result = self.fetch_for_cad(self.symbol_ib)
        else:
            result = (None, None, None)
        log.debug("{:12}: End: {}".format(self.symbol_ib, str(bool(result[0]))))
        return result

    def fetch_for_eur(self, symbol):
        suffixes = [".DE", ".F", ".MI", ".AS", ".PA", ".BR", ".LS", ".BE"]
        for s in suffixes:
            symbol = self.symbol_ib + s
            try:
                my_request = self.get_yahoo_response(symbol)
                response = self.parse_yahoo_response(my_request)
            except BadYahooSymbolError:
                self.tried_symbols.append(symbol)
            else:
                if response[0]:
                    return response
        return None, None, None

    def fetch_for_aud(self, symbol):
        symbol = self.symbol_ib + ".AX"
        try:
            my_request = self.get_yahoo_response(symbol)
            return self.parse_yahoo_response(my_request)
        except BadYahooSymbolError:
            self.tried_symbols.append(symbol)
        return None, None, None

    def fetch_for_cad(self, symbol):
        suffixes = [".T", ".TO", ".V"]
        for s in suffixes:
            symbol = self.symbol_ib + s
            try:
                my_request = self.get_yahoo_response(symbol)
                return self.parse_yahoo_response(my_request)
            except BadYahooSymbolError:
                self.tried_symbols.append(symbol)
                continue
        return None, None, None

    def fetch_for_unknown_currency(self):
        try:
            my_request = self.get_yahoo_response(self.symbol_ib)
            symbol, name, currency = self.parse_yahoo_response(my_request)
        except BadYahooSymbolError:
            symbol, name = None, ""

        if symbol:
            return symbol, name, currency

        eur_symbol = self.fetch_for_eur(self.symbol_ib)
        if eur_symbol[0]:
            return eur_symbol
        aud_symbol = self.fetch_for_aud(self.symbol_ib)
        if aud_symbol[0]:
            return aud_symbol
        cad_symbol = self.fetch_for_cad(self.symbol_ib)
        if cad_symbol[0]:
            return cad_symbol
        return None, None, None

    def get_yahoo_response(self, symbol, failed_attemps=0):
        if failed_attemps >= config.getint("instrument_fetch_max_allowed_tries"):
            raise BadYahooSymbolError()
        url = "https://finance.yahoo.com/quote/{}".format(symbol)
        try:
            my_request = request.urlopen(url)
        except HTTPError as e:
            if e.code == 503:
                log.warning("{:12}: Received 503 request, trying again in few seconds...".format(symbol))
                sleep(4)
                return self.get_yahoo_response(symbol, failed_attemps + 1)
            if e.code == 404:
                print(url)
                raise BadYahooSymbolError()
            else:
                raise

        if my_request.url != url:
            log.debug("{:12}: Not found".format(symbol))
            raise BadYahooSymbolError()
        else:
            log.debug("{:12}: Found".format(symbol))

        return my_request

    def parse_yahoo_response(self, my_request):
        """Retrieve symbol ticker, full name and currency from the response from finance.yahoo.com"""
        try:
            response = my_request.read().decode("utf-8")
        except UnicodeDecodeError:
            return None, "", ""
        log.error(response)
        name, symbol = self._get_name_and_symbol_from_response(response)
        if not name:
            return None, "", ""
        symbol_base = symbol
        if "." in symbol:
            symbol_base = symbol.split(".")[0]
        if not symbol_base == self.symbol_ib:
            assert_string_similarity(symbol, self.name, name)
        if not self.currency:
            self.currency = self._get_currency_from_response(response)
            log.debug("{:12}: Currency on yahoo: {}".format(self.symbol_ib, self.currency))
        return symbol, name, self.currency

    def _get_name_and_symbol_from_response(self, response):
        title_start = response.find("<title>") + len("<title>")
        title_end = response.find("</title>")
        title = response[title_start:title_end]  # BIO ON (ON.MI) Stock Price, Quote, History &amp; News
        title = title.replace("(The)", "")  # Walt Disney Company (The) (DIS) Stock Price, Quote, History &amp; News
        if title == "Requested symbol wasn&#x27;t found":
            return None, ""
        symbol = re.search(r"\(([A-Z\d\.]+)\) Stock Price", title).groups()[0]

        needle = '<h1 class="D(ib) Fz(16px) Lh(18px)" data-reactid="7">'  # After this the name comes
        needle = response.find(needle)
        if needle == -1:
            needle = response.find('<h1 class="D(ib) Fz(18px)" data-reactid="7">')
        assert needle != -1, "Need to check this response as it seems an exception of the rule."
        name = response[needle : needle + 200]
        name = name[name.find(">") + 1 : name.find("</h1>")]

        return name, symbol

    def _get_currency_from_response(self, response):
        needle = "Currency in "
        start = response.find(needle) + len(needle)
        currency = response[start : start + 3]
        return currency


def assert_string_similarity(symbol, name1, name2):
    name_similarity = SequenceMatcher(None, name1.upper(), name2.upper()).ratio()
    if name_similarity < config.getfloat("min_name_similarity"):  # Compare name from yahoo page to name from csv
        log.debug(
            "{:12}: Name disregarded, similarity of {:.3f}: {} vs {}".format(symbol, name_similarity, name1, name2)
        )
        raise BadYahooSymbolError()
    log.debug("{:12}: Found {}".format(symbol, name2))
