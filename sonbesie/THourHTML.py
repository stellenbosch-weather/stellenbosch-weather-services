#!/usr/bin/env python
import sys
import time
import datetime
try:
    import urllib.request as urllib2
except ImportError:  # Python 2.7 on the production collector
    import urllib2
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from settings_loader import load_settings
from tmin_html import parse_tmin_html
from import_progress import progress, error, stage

lock_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "THour.lock")
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "THour.log")

Config = load_settings()


#This is to check if there is already a lock file existing#
if os.access(lock_file, os.F_OK):
  #if the lockfile is already there then check the PID number 
  #in the lock file
  pidfile = open(lock_file, "r")
  pidfile.seek(0)
  oldpid = pidfile.readline()
  # Now we check the PID from lock file matches to the current
  # process PID
  if oldpid.strip() != "" and os.path.exists("/proc/%s" % oldpid):
    progress("You already have an instance of the program running")
    progress("It is running as process %s," % oldpid)
    sys.exit(1)
  else:
    progress("File is there but the program is not running")
    progress("Removing lock file for the: %s as it can be there because of the program last time it was run" % oldpid)
    os.remove(lock_file)

#This is part of code where we put a PID file in the lock file
pidfile = open(lock_file, "w")
newpid = str(os.getpid())
progress("PID="+newpid)
pidfile.write(newpid)
pidfile.close()


stationName = "Sonbesie"
tableName = "SB_THour"
dataFile = "http://"+Config.get("sonbesie", "address")+"/?command=TableDisplay&table=THour&records="

log = open(log_file, 'a')

try:
    import MySQLdb
except ImportError:
    try:
        import pymysql as MySQLdb
    except ImportError:
        error("ERROR !!!!\nInstall MySQLdb or PyMySQL (pip install -r requirements.txt).")
        sys.exit(1)

try:
    # Database connection
    with stage("Connecting to database for " + tableName):
        conn = MySQLdb.connect (host = Config.get("database", "host"),
                            user = Config.get("database", "username"),
                            passwd = Config.get("database", "password"),
                            db = Config.get("database", "database"),
                            port = Config.getint("database", "port") if Config.has_option("database", "port") else 3306)
        conn.autocommit(True)
        cursor = conn.cursor ()
    
    # Get the last date and count the amount of days to get
    sqlStatement = "SELECT MAX(`TimeStamp`) FROM "+tableName
    with stage("Checking latest stored timestamp for " + tableName):
        cursor.execute(sqlStatement)
        lastDate = cursor.fetchone()[0]
    now = datetime.datetime.now()
    delta = now - lastDate
    
    # read in file
    dataFile = dataFile+str(int((delta.days*24) + (delta.seconds/60/60) + 1 ))
    with stage("Downloading " + dataFile):
        f = urllib2.urlopen(dataFile, timeout=3600)
    
        filecontents = f.read()
        f.close()
    
    progress("Downloaded %d bytes; parsing HTML" % len(filecontents))
    with stage("Parsing " + tableName):
        columns, rows = parse_tmin_html(filecontents)
    progress("Parsed %d records" % len(rows))
    sqlStatement = "INSERT INTO `" + tableName + "` (`Date`, `Time`, "
    sqlStatement += ", ".join("`" + column + "`" for column in columns)
    sqlStatement += ") VALUES (" + ", ".join(["%s"] * (len(columns) + 2)) + ")"

    inserted = 0
    with stage("Importing records into " + tableName):
        for countlines, values in enumerate(rows, 2):
            date, time_var = values[0].split()
            cursor.execute(
                "SELECT 1 FROM `" + tableName + "` WHERE `TimeStamp` = %s LIMIT 1",
                (values[0],))
            if cursor.fetchone() is None:
                cursor.execute(sqlStatement, [date, time_var] + values)
                inserted += 1
            processed = countlines - 1
            if processed == 1 or processed % 100 == 0 or processed == len(rows):
                progress("%s: processed %d/%d records; inserted %d, skipped %d" %
                         (tableName, processed, len(rows), inserted, processed - inserted))

        conn.commit()
    cursor.close ()
    conn.close ()
    summary = "%s: complete; processed %d, inserted %d, skipped %d" % (tableName, len(rows), inserted, len(rows) - inserted)
    progress(summary)
    log.write(time.strftime("%Y-%m-%d %H:%M:%S") + " " + summary + "\n")
    log.close()

except MySQLdb.Error as e:
    error("Error %d: %s" % (e.args[0], e.args[1]))
    sys.exit (1)
