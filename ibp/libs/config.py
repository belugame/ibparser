import configparser
from os import path
from pathlib import Path

home = str(Path.home())
config_file = path.join(home, ".ibparser.cfg")
if not path.exists(config_file):
    config_file = path.join(path.dirname(path.abspath(__file__)), "../ibparser.cfg")

parser = configparser.RawConfigParser()
parser.read(config_file)
config = parser["ibparser"]
