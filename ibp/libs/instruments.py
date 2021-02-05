import csv

from .constants import IB_EXCHANGE_TO_CURRENCY
from .config import config
from .logging import log
from .models import Instrument as DBInstrument
from .money import Money
from .prices import PriceService
from .prices import thread_price_service
from .yahoo_instrument_scraper import YahooSymbolPageScraper
from .yahoo_json_search_scraper import get_yahoo_json_search_result


class Instrument(object):
    """
    Holds all info we extract straight from a CSV file. Not all have a security id, e.g. AFK or ASX
    """
    currency = None
    _db_instrument = None

    def __init__(self, symbol_ib, name, con_id, security_id, currency=None, symbols_ib_additional=None):
        self.symbol_ib = symbol_ib
        self.name = name
        self.con_id = con_id
        self.security_id = security_id
        self.currency = currency
        self.symbols_ib_additional = symbols_ib_additional or []
        log.debug("{}.__init__ {}, {}, {}, {}".format(self.__class__.__name__, symbol_ib, name, con_id, security_id))
        if self.symbol_ib.endswith(".OLD"):
            log.warning("Ignoring {} as no longer valid name.".format(self.symbol_ib))
        else:
            self.symbol_yahoo, self.currency = self._get_yahoo_metadata()

    def __repr__(self):
        return "<{} {}>".format(self.symbol_ib, self.currency)

    def _get_yahoo_metadata(self):
        """
        Returns the symbol name yahoo uses for this instrument, something we can't get from the IB csvs.
        Tries to guess yahoo symbol name and confirms it by crawling yahoo. On success we save it in a simple csv.
        """
        db_instrument = db.get(self.con_id)

        if db_instrument:
            self.symbol_yahoo = db_instrument.symbol_yahoo
            self.currency = db_instrument.currency
        else:
            log.debug("{:12}: Start yahoo search, currency {}, name '{}', id {}".format(
                self.symbol_ib, self.currency, self.name, self.security_id or "-"))
            if self.security_id:
                self.symbol_yahoo, yahoo_name, yahoo_currency = get_yahoo_json_search_result(self.security_id)
            if not self.symbol_yahoo:
                self.symbol_yahoo, yahoo_name, yahoo_currency = get_yahoo_json_search_result(self.name)
                if not self.currency:
                    self.currency = yahoo_currency
            if not yahoo_currency or self.currency != yahoo_currency:
                log.warn("Could not confirm IB currency with yahoo result: {} != {} (yahoo)".format(
                    self.currency, yahoo_currency))
                self.symbol_yahoo, yahoo_name, yahoo_currency = YahooSymbolPageScraper(
                        self.symbol_ib, self.name, self.currency).fetch()
                if not self.currency:
                    self.currency = yahoo_currency
                else:
                    assert self.currency == yahoo_currency
            db.add(self)
            log.debug("-" * 5)
        return self.symbol_yahoo, self.currency

    def get_price(self, date_time=None):
        if not self.symbol_yahoo:
            log.warning("Can't get price for {}, as we don't have a yahoo symbol.".format(self))
            return Money(0.0, self.currency or config.get("default_currency"))
        return PriceService(self).get(date_time)

    def get_price_in_background(self, date=None):
        thread_price_service.submit(self, date)

    def get_all_known_symbols(self):
        db_instrument = db.get(con_id=self.con_id)
        symbols = [db_instrument.symbol_ib, db_instrument.symbol_yahoo]
        if db_instrument.symbols_ib_additional:
            symbols += db_instrument.symbols_ib_additional.split(",")
        return symbols


class InstrumentCollection(object):
    """Helps to lookup an instrument e.g. by it's symbol from information gathered from IB csv files."""

    def __init__(self, reader, instrument_filter=None):
        log.debug("{}.__init__".format(self.__class__.__name__))
        self.instrument_filter = instrument_filter
        InstrumentParser(reader, instrument_filter).get_csv_instruments()

    def get(self, symbol_ib, currency, con_id=None):
        db_instrument = None
        if con_id:
            db_instrument = db.get(con_id=con_id)
        if not db_instrument:
            db_instrument = db.get_by_symbol_ib(symbol_ib, currency)
        if db_instrument:
            assert db_instrument.currency == currency, "Currency mismatch: DB {} vs transaction {}".format(
                    db_instrument.currency, currency)
            return db_instrument_to_instrument(db_instrument)

        # This happens for newly bought stocks where we only have a daily_*.csv and no 'Financial Instrument' line:
        log.warning("{}: Missing currency metadata".format(symbol_ib))
        impromptu_instrument = Instrument(symbol_ib, "{} ?".format(symbol_ib), "?", "?")
        return impromptu_instrument


class InstrumentParser(object):
    """
    Reads IB-metadata about the instruments (stocks, etfs etc.) from csv. As the trade-lines do not hold this
    information we need them to know the full name of the companies. Also we need it to identify company name changes as
    here we get an unique id.
    """
    instruments = {}

    def __init__(self, reader, instrument_filter=None):
        self.reader = reader
        self.instrument_filter = instrument_filter or []

    def get_csv_instruments(self):
        """
        Reads definitions of instruments from CSV files. Gives us symbol name and unique ids but not the currency.
        Sample line:
        Financial Instrument Information,Data,Stocks,ROP,ROPER TECHNOLOGIES INC,81025075,US7766961061,1,COMMON,
        """
        lines = set(self.reader.get_instrument_lines())
        reader = csv.reader(lines, delimiter=",")
        for row in reader:
            log.debug("Parsing instrument... {}".format(row[4]))
            i = self._parse_row_to_instrument(row)
            if i:
                self.instruments[i.con_id] = i
        return self.instruments

    def _parse_row_to_instrument(self, row):
        """Single line in csv file to python namedtuple Instrument w/o adding or calculating additional data"""
        # IB columns definition:
        # Financial Instrument Information,Header,Asset Category,Symbol,Description,Conid,Security ID,Multiplier,Type,Code
        _, _, _, symbol_ib, name, con_id, security_id, exchange = row[:8]
        currency = None
        if exchange:
            if exchange in ("CORPACT", "RIGHT"):
                return None
            assert exchange in IB_EXCHANGE_TO_CURRENCY, "Missing exchange: '{}'  Row: {}".format(exchange, row)
            currency = IB_EXCHANGE_TO_CURRENCY.get(exchange)
        if "," in symbol_ib:
            symbols = [extract_symbol(x.strip()) for x in symbol_ib.split(",")]
        else:
            symbols = [symbol_ib]

        if ignore_instrument(con_id, symbols, self.instrument_filter):
            return None

        db_instrument = DBInstrument.get_or_none(con_id=con_id)
        if db_instrument:
            db.update_symbols(db_instrument, symbols)
            return None  # Don't create new instrument

        return Instrument(symbols[0], name, con_id, security_id, currency, symbols[1:])

    def print_instruments(self):
        for i in self.instruments.values():
            columns = [
                "{:10}".format(i.symbol_ib),
                "{:40}".format(i.name),
                "{:20}".format(i.con_id),
                "{:20}".format(i.security_id),
                "{:5}".format(i.currency or "?"),
            ]
            print(";".join(columns))


class InstrumentDatabase(object):
    """
    Handles saving+loading information that should be stored permanently to avoid loading it again from Yahoo.
    The IB csvs do not give us the yahoo ticker name which we need for fetching prices. YahooSymbolScraper can fetch
    that information but it's slow.
    """

    def get(self, con_id):
        return DBInstrument.get_or_none(con_id=con_id)

    def get_by_security_id(self, security_id):
        return DBInstrument.get_or_none(security_id=security_id)

    def get_by_symbol_ib(self, symbol_ib, currency=None):
        if currency:
            db_instrument = DBInstrument.get_or_none(symbol_ib=symbol_ib, currency=currency)
        else:
            db_instrument = DBInstrument.get_or_none(symbol_ib=symbol_ib)
        if not db_instrument:
            db_instrument = DBInstrument.get_or_none(DBInstrument.symbols_ib_additional.contains(symbol_ib))
        return db_instrument

    def add(self, instrument):
        """
        Add to database if not in it yet.
        """
        db_instrument = DBInstrument.get_or_none(con_id=instrument.con_id)
        if not db_instrument:
            log.debug("Add instrument to database: {}".format(instrument.symbol_ib))
            DBInstrument(
                name=instrument.name,
                symbol_yahoo=instrument.symbol_yahoo,
                symbol_ib=instrument.symbol_ib,
                symbols_ib_additional=",".join(instrument.symbols_ib_additional),
                security_id=instrument.security_id,
                con_id=instrument.con_id,
                currency=instrument.currency).save()

    def update_symbols(self, db_instrument, symbols):
        if db_instrument.symbol_ib not in symbols:
            symbols.append(db_instrument.symbol_ib)
            if not symbols[0].endswith(".OLD"):
                db_instrument.symbol_ib = symbols[0]
        if db_instrument.symbols_ib_additional:
            symbols = db_instrument.symbols_ib_additional.split(",") + symbols
        symbols = set([s for s in symbols if not s == db_instrument.symbol_ib])
        db_instrument.symbols_ib_additional = ",".join(symbols)
        db_instrument.save()


def ignore_instrument(con_id, symbols, instrument_filter, currency=None):
    assert con_id or symbols, "One of either must be given for db lookup"
    ignored_symbols = config.get("ignored_symbols").split(",")
    if any([extract_symbol(s) in ignored_symbols for s in symbols]):
        return True
    if not instrument_filter:
        return False
    if any([extract_symbol(s) in instrument_filter for s in symbols]):
        return False
    if con_id:
        db_instrument = db.get(con_id)
    else:
        for s in symbols:
            db_instrument = db.get_by_symbol_ib(s, currency=currency)
            if db_instrument:
                break

    if db_instrument:
        symbols = [db_instrument.symbol_yahoo]
        if db_instrument.symbols_ib_additional:
            symbols += db_instrument.symbols_ib_additional.split(",")
        symbols += [extract_symbol(s) for s in symbols]
        return not any([s in instrument_filter for s in set(symbols)])

    return True


def extract_symbol(symbol):
    """Remove suffixes like the exchange name, or .OLD"""
    if "." in symbol:
        return symbol.split(".")[0]
    return symbol


def db_instrument_to_instrument(db_instrument):
    """From db object to class instance"""
    instrument = Instrument(db_instrument.symbol_ib, db_instrument.name, db_instrument.con_id,
                            db_instrument.security_id, db_instrument.currency)
    instrument._db_instrument = db_instrument
    return instrument


db = InstrumentDatabase()
