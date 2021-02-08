import os

from peewee import SqliteDatabase, CharField, Model, ForeignKeyField, DateField, DateTimeField, FloatField

from .config import config

db_file = os.path.expanduser(config.get("db_file"))
db = SqliteDatabase(db_file)


class BaseModel(Model):
    class Meta:
        database = db


class Instrument(BaseModel):
    name = CharField()
    symbol_ib = CharField()
    symbol_yahoo = CharField()
    symbols_ib_additional = CharField()
    con_id = CharField(unique=True)
    security_id = CharField()  # CA03765K1049 is the same for 10E und APHA
    currency = CharField()

    def __repr__(self):
        return "<Instrument: IB {} YA {} | {}>".format(self.symbol_ib, self.symbol_yahoo, self.symbols_ib_additional)


class Price(BaseModel):
    instrument = ForeignKeyField(Instrument, related_name="prices", null=False)
    price = FloatField()
    datetime = DateTimeField(null=False)


class CurrencyRate(BaseModel):
    currency_a = CharField(null=False)
    currency_b = CharField(null=False)
    rate = FloatField(null=False)
    date = DateField(null=False)


db.create_tables([Instrument, Price, CurrencyRate])
