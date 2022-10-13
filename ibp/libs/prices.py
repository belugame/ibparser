from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from yahoo_historical import Fetcher

from .config import config
from .logging import log
from .models import Price as DBPrice
from .money import Money


class PriceService(object):
    """Retrieves prices from local database or 3rd party online"""

    def __init__(self, instrument):
        # log.debug("{}.__init__".format(self.__class__.__name__))
        self.instrument = instrument

    def get(self, date_time=None, failed_tries=0):
        """Return price for given date or stored date"""
        assert self.instrument.currency, "Don't have currency for {}".format(self.instrument)
        date_time = date_time or datetime.now()
        if date_time.weekday() == 6:
            date_time -= timedelta(days=1)
        price = self._get_from_database(date_time) or self._get_from_yahoo(date_time, failed_tries)
        return Money(price, self.instrument.currency)

    def _get_from_database(self, date_time):
        """Return most recent price for given day from db"""
        start = date_time.replace(hour=0, minute=0, second=0, microsecond=0)
        end = date_time.replace(hour=23, minute=59, second=59, microsecond=999)
        prices = (
            DBPrice.select()
            .where(
                (DBPrice.instrument == self.instrument._db_instrument)
                & (DBPrice.datetime > start)
                & (DBPrice.datetime < end)
            )
            .order_by(DBPrice.datetime.desc())
            .limit(1)
        )
        if prices:
            return prices.first().price
        return None

    def _get_from_yahoo(self, date_time, failed_tries=0):
        """Fetch close price of instrument on given date from yahoo"""
        if failed_tries >= config.getint("price_fetch_max_allowed_tries"):
            log.warning(
                "Refusing to fetch {} {} because of {} previous failed attempt. Returning 0.001".format(
                    self.instrument.symbol_yahoo, date_time, failed_tries
                )
            )
            return 0.001
        log.debug("{}: Fetching {}".format(self.instrument.symbol_yahoo, date_time))
        start = round(date_time.timestamp())
        end = round((date_time + timedelta(days=1)).timestamp())
        try:
            data = Fetcher(self.instrument.symbol_yahoo, start, end)
        except UnboundLocalError:
            log.warning("Failed to fetch price: {} {}".format(self.instrument.symbol_yahoo, date_time))
            return self.get(date_time - timedelta(days=1), failed_tries=failed_tries + 1).as_float

        try:
            price_as_float = data.get_historical().values[0][1]
        except IndexError:
            log.warning("Failed to fetch price: {} {}".format(self.instrument.symbol_yahoo, date_time))
            price_as_float = self.get(date_time - timedelta(days=1), failed_tries=failed_tries + 1).as_float
        self._write_to_database(price_as_float, date_time)
        return price_as_float

    def _write_to_database(self, price_as_float, date_time):
        DBPrice.get_or_create(instrument=self.instrument._db_instrument, price=price_as_float, datetime=date_time)


class ThreadPriceService(object):
    pool = ThreadPoolExecutor(max_workers=10)
    queue = []

    def submit(self, instrument, my_date):
        key = "{}-{}".format(instrument.symbol_ib, my_date or "today")
        if key not in self.queue:
            self.queue.append(key)
            self.pool.submit(PriceService(instrument).get, my_date)


thread_price_service = ThreadPriceService()
