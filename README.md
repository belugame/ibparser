# ibparser: Ad-hoc portfolio reports for your InteractiveBroker CSVs

## TL;DR

![screenshot](https://user-images.githubusercontent.com/16137830/107149988-da47a180-695b-11eb-91fe-5e4c06260cc1.png)

ibparser lists transactions, dividends, deposits and withdrawals, shows realized gains/losses and also fetches
current prices. All information is extracted from CSV reports (that any IB account can be set up to send out daily by
email) combined with metadata gathered from Yahoo finance. Output format is easy to read and easy to process further
with e.g. `awk` (the `-m` arg will give you a semicolon-separated list).

ibparser can as an example give you:

- list of buy-transactions only for ticker XY1 and only in the past 90 days
- list of all dividends received with the amounts converted to €
- list of only USD movements in your account

The screenshot above shows all transactions of a paper account of the last week.


## Status

Still in early development and will not be able to identify all stocks and exchanges correctly due to lack of data. You
could help the project by trying it out with a CSV of your account to see if it recognizes your tickers and exchanges.
**Remove any sensitive account data from the CSV before you share it**. Alternatively set up a IB paper account and
repeat similar transactions.


## What can ibparser do?

- parses CSVs generated from you IB account to create fast ad-hoc reports in the terminal
- lists sell/buy transactions with buy-price, sell-price, amount, realized profit/loss etc.
- lists dividends received, withdrawals and deposits
- recognizes splits & merges and adjusts transactions accordingly
- filter by one or multiple tickers, a time frame or by currency
- converts prices to desired currency
- fetches ticker metadata and current price from yahoo and shows unrealized price change percentage
- stores ticker metadata into a sqlite db for quicker invocation


## Features in development:

- show portfolio as a whole
- create reports like sum of realized profits with a plotted graph

## Installation

```
git clone git@github.com:belugame/ibparser.git
cd ibparser
pip install --user --upgrade .
```

## Config
Copy [ibparser.cfg](https://github.com/belugame/ibparser/blob/master/ibp/ibparser.cfg) to `.ibparser.cfg` in your home
folder and adjust. Parameters are explained in the file.

## Usage

`ibp <mode> <arguments> <symbol1> <symbol2>...`

If no symbols are given, it will show all. You can specify one or multiple to limit output to those.

`ibp transactions` is equivalent to `ibp t`

All modes:

- `t` is short for transactions
- `d` for dividends
- `e` for deposits
- `p` for portfolio
- `rr` for report_realized

Show the help for a command like this `ibp t -h`

For the `transaction` command:

```
  -s                   Only show sell transactions
  -b                   Only show buy transactions
  -c DISPLAY_CURRENCY  Convert all amounts to given currency
  -f FILTER_CURRENCY   Limit output to items of given currency
  -m                   Make output CSV-like (no padding of data)
  -d DATE_DELTA        Limit output to given date range. E.g. 2w for past two weeks, or ytd for year-to-date
```

Add `DEBUG=1` before the command to see logging output. On the first run it will try to recognize all involved tickers
(IB speak "instruments"), so that may take a while.

## Sample invocations

### All transactions of the last 10 days:
```
DEBUG=1 ibp transactions -d 10d
2021-01-26  AUD  ASX LTD             ASX.AX       12   73.930 AUD    72.23 AUD     -887 AUD    -2.3%
2021-01-27  CHF  LANDIS+GYR GROUP A  LAND.SW      20   73.150 CHF    64.75 CHF   -1,463 CHF   -11.5%
2021-01-27  USD  GOPRO INC-CLASS A   GPRO        -62   10.484 USD    10.53 USD     +650 USD     0.4%       9.58 USD
2021-01-29  CHF  LANDIS+GYR GROUP A  LAND.SW      11   66.959 CHF    64.75 CHF     -737 CHF    -3.3%
Total: 9.58 USD
```

The columns are:

- date of transaction
- ticker currency
- company name
- yahoo ticker
- amount bought/sold
- transaction price (price you bought/sold for; fees are included)
- current price (fetched currently only one time per day)
- total amount received from respectively paid for transaction
- price percentage change since transaction
- realized profit/loss (for sell transactions only)

### Dividends of the last 90 days received in Canadian Dollars:
```
DEBUG=1 ibp dividends -d 90d -f cad

2020-10-13  CAD  HORIZONS MARIJUANA  HMMJ.TO     4.41 CAD
2020-11-25  CAD  WASTE CONNECTIONS   UI51.F      3.73 CAD
Total: 8.14 CAD
```

### Buy/Sell transactions year-to-date of the two ticker symbols IBM and MWA converted to EUR
```
DEBUG=1 ibp transactions -d ytd -c eur IBM MWA
```
### List of money movements (deposits, withdrawals, etc.) in the past week
```
DEBUG=1 ibp deposits -d 1w

2021-02-01  USD         27.20 USD  Adjustment: Cash Receipt/Disbursement/Transfer (Transfer to UXXXXXXX)
2021-02-04  EUR      1,000.00 EUR  Electronic Fund Transfer
Total: 1,231.13 USD
```

### Cumulative sum of realized gains (sell transactions + dividends)

Work in progress

Creates a panda data frame from realized gains for single tickers or the whole portfolio. Currently uses `plottext` to
show a graph with 3 lines. Gains from selling, dividends and the sum of both.

```
ibp rr XY1

                       realized   dividends
2018-09-21 00:00:00     0.00000   29.844837
2019-03-15 00:00:00     0.00000   46.989744
...
2020-06-17 20:04:20   294.28280    0.000000
2020-06-22 01:28:49   213.45409    0.000000
2020-09-16 00:00:00     0.00000   42.671768
2021-01-20 19:29:15   458.43575    0.000000
```

![graph](https://user-images.githubusercontent.com/16137830/107189915-66a0a580-69ea-11eb-9aac-8bdeaad2d0fd.png)

## How do I get a CSV from my account?

You can export as far as one full year in a single CSV. You can also setup IB to send you a CSV every day. I have a
helper script that automatically gets me the attachments from the daily emails into my CSV folder using `munpack` from
where `mbsync` stores my emails.

### Setting up and exporting a CSV report for ibparser

See here for screenshots: https://github.com/belugame/ibparser/issues/1

Login to your interactivebrokers account management:

1) Click on "Reports" on the top menu tab
2) Click on the plus icon next to "Custom Statements"
3) Enter Statement Name e.g. "daily-all" and select "All" in the Sections
4) Use Format CSV and Period Daily. It is important that the output language is English
5) Click Continue and Create
6) Click on the arrow pointing to the right next to "daily-all" in the "Custom Statements" menu to create a CSV for e.g.
  the entire last year. You need Format CSV and language English. Download the CSV to your computer, store it in a new
  folder and point ibparser to this folder.

### Setting up a daily csv sent to you via email

1) Click on the gear icon next to "Statements Delivery"
2) Click on the gear icon next to "Daily Custom Statements Delivery"
3) Select "Delivery Method" Email and check daily-all in "Reports" with Format CSV.
