# Stellenbosch Weather services

This repository contains processing scripts that need to run periodically.
The most important part is importing weather data from the weather stations.
In the future this can be extended to aggregate data for graphing.

## Configuration

The scripts look for `settings.conf` in this order:

1. The current working directory (`./settings.conf`).
2. The services repository root.
3. The parent workspace directory.
4. The current user's home directory (`~/settings.conf`).

## Sonbesie rain columns

Before running the TMin HTML importer against the updated logger, apply
`migrations/20261009_sonbesie_rain.sql` once to the weather database. It adds
nullable `Rain_1_Tot` and `Rain_1_Accumulated` columns to `SB_TMin`, leaving
historical readings as NULL. The importer maps columns by the logger's headers.

Run the parser regression checks (including a captured live logger response) with:

```sh
python3 -m unittest discover -s sonbesie/tests -v
```

The hourly and daily tables require
`migrations/20261009_sonbesie_hourly_daily_rain.sql` as well. Apply each migration
only once; existing columns cause an error on repeat application.

## Running imports

The HTML collectors require Python 3 and PyMySQL:

```sh
python3 -m venv /tmp/sonbesie-venv
/tmp/sonbesie-venv/bin/pip install -r requirements.txt
export PATH=/tmp/sonbesie-venv/bin:$PATH
./import-minutely.sh
./import-hourly.sh
./import-daily.sh
```

For SSH forwards on local ports 8888 (logger) and 3306 (database), configure
`sonbesie.address = 127.0.0.1:8888`, `database.host = 127.0.0.1`, and
`database.port = 3306` in a local `settings.conf`, alongside the database
credentials. This file is excluded from Git. The scripts fetch the backlog since
the most recent stored timestamp, limited by the logger's retained records.

For a short live-data check, use `./import-minutely.sh --records 60`. To import the
logger's full retained minute history explicitly, use
`./import-minutely.sh --records 58440` (the retention reported on 2026-10-09).
A limited run advances the latest database timestamp; a later normal run will
not automatically fill the older gap, so use an explicit record count to backfill.
