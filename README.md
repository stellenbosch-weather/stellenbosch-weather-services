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

Before running the TMin importer against the updated logger, apply
`migrations/20261009_sonbesie_rain.sql` once to the weather database. It adds
nullable `Rain_1_Tot` and `Rain_1_Accumulated` columns to `SB_TMin`, leaving
historical readings as NULL. The importers map columns by the logger's field names.

Run the parser regression checks (including a captured live logger response) with:

```sh
python3 -m unittest discover -s sonbesie/tests -v
```

The hourly and daily tables require
`migrations/20261009_sonbesie_hourly_daily_rain.sql` as well. Apply each migration
only once; existing columns cause an error on repeat application.

## Running imports

The `import-*.sh` entry points use the HTML importers for TMin, THour,
TDaily, and Thermocouple. They work with the server's existing MySQLdb driver
without installing additional packages:

```sh
./import-minutely.sh
./import-minutely.sh --records 60
./import-hourly.sh
./import-daily.sh
```

When stdout is a terminal, the HTML importers display database, download,
parsing, and insertion progress, with elapsed-time updates every five seconds
while a stage is running. Insert progress includes processed, inserted, and
skipped counts. Cron and redirected runs suppress routine console output;
errors still go to stderr. The HTML importers append one completion summary
per run to their existing log files instead of logging each inserted record.
This uses only the standard library and requires no additional server packages.
Changes apply to new runs; an already-running process retains its old behavior.

## Optional PakBus imports

The `sonbesie/*PakBus.py` scripts remain available for environments where
additional packages can be installed. They run with `python` on PATH and
support Python 2.7 and Python 3. Install their dependencies before invoking
them directly:

```sh
python -m pip install -r requirements.txt
python sonbesie/TMinPakBus.py
python sonbesie/THourPakBus.py
python sonbesie/ThermocouplePakBus.py
python sonbesie/TDailyPakBus.py
```

The existing MySQLdb driver is preferred, with PyMySQL as a fallback.
For local Python 3 use:

```sh
python3 -m venv /tmp/sonbesie-venv
/tmp/sonbesie-venv/bin/pip install -r requirements.txt
export PATH=/tmp/sonbesie-venv/bin:$PATH
```

PakBus uses the hostname from `sonbesie.address`, discarding its HTTP port,
and connects to port **5001**. Set optional `sonbesie.pakbus_port` to override
that port. With SSH forwards on localhost ports 5001 (PakBus), 8888 (HTTP),
and 3306 (database), the existing `sonbesie.address = 127.0.0.1:8888` and
`database.host = 127.0.0.1`, `database.port = 3306` work unchanged in
`settings.conf`. Keep database credentials in that Git-ignored file.

Normal runs fetch records from the latest stored timestamp, or all retained
records for an empty database. Timestamps retain the logger's local time.
Imports skip timestamps already stored and commit each received batch, so an
interrupted catch-up resumes on the next run. A shared process lock serializes
PakBus access across the scheduled scripts and releases automatically on exit.
Logger NaN/infinite readings become SQL NULL; daily NSec peak timestamps are
converted to datetimes. The rain migrations above are still required.

All PakBus scripts accept `--records N` to import the latest N retained records
regardless of the database timestamp. A limited run advances the latest database
timestamp; use an explicit record count to backfill older gaps afterward.

```sh
python sonbesie/TMinPakBus.py --records 60
python sonbesie/TMinPakBus.py --records 58440  # Full minute retention on 2026-10-09
python sonbesie/THourPakBus.py --records 24
python sonbesie/TDailyPakBus.py --records 40
```

Use `--dry-run --records N` to read and validate live PakBus data without
connecting to the database:

```sh
python sonbesie/TMinPakBus.py --dry-run --records 60
python sonbesie/THourPakBus.py --dry-run --records 2
python sonbesie/TDailyPakBus.py --dry-run --records 2
python3 -m unittest discover -s sonbesie/tests -v
```

The regression suite requires Python 3 and the dependencies in `requirements.txt`.
