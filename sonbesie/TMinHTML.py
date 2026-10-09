#!/usr/bin/env python3
import sys
import argparse
import time
from pprint import pprint
import datetime
import urllib.request as urllib2
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from settings_loader import load_settings
from tmin_html import parse_tmin_html

lock_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "TMin.lock")
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "TMin.log")

argument_parser = argparse.ArgumentParser(description="Import Sonbesie minute readings")
argument_parser.add_argument('--records', type=int, help='Request this many recent records instead of automatic catch-up')
args = argument_parser.parse_args()
if args.records is not None and args.records <= 0:
    argument_parser.error('--records must be positive')

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
    print("You already have an instance of the program running")
    print("It is running as process %s," % oldpid)
    sys.exit(1)
  else:
    print("File is there but the program is not running")
    print("Removing lock file for the: %s as it can be there because of the program last time it was run" % oldpid)
    os.remove(lock_file)

#This is part of code where we put a PID file in the lock file
pidfile = open(lock_file, "w")
newpid = str(os.getpid())
print("PID="+newpid)
pidfile.write(newpid)
pidfile.close()


stationName = "Sonbesie"
tableName = "SB_TMin"
dataFile = "http://"+Config.get("sonbesie", "address")+"/?command=TableDisplay&table=TMin&records="

log = open(log_file, 'a')
log.write( "Run start: "+time.strftime("%Y-%m-%d", time.localtime(time.time()))+" "+time.strftime("%H:%M:%S", time.localtime(time.time()))+"\n" )

try:
    import pymysql as MySQLdb
except ImportError:
    print("ERROR !!!!\nPyMySQL not installed (pip install -r requirements.txt).")
    sys.exit(1)

try:
    # Database connection
    conn = MySQLdb.connect (host = Config.get("database", "host"),
                        user = Config.get("database", "username"),
                        passwd = Config.get("database", "password"),
                        db = Config.get("database", "database"),
                        port = Config.getint("database", "port") if Config.has_option("database", "port") else 3306,
                        autocommit = True)
    cursor = conn.cursor ()
    
    # Get the last date and count the amount of days to get
    sqlStatement = "SELECT MAX(TimeStamp) AS TimeStamp FROM "+tableName
    cursor.execute(sqlStatement)
    lastDate = cursor.fetchone()[0]
    now = datetime.datetime.now()
    delta = now - lastDate
    
    # read in file
#    f = open(dataFile)
    records = args.records if args.records is not None else int(delta.total_seconds() / 60) + 1
    dataFile = dataFile + str(records)
    pprint(dataFile)

    # f = urllib2.urlopen(dataFile)
    request = urllib2.Request(dataFile)
    f = urllib2.urlopen(request, timeout=3600)
    filecontents = f.read()
    f.close()
    
    columns, rows = parse_tmin_html(filecontents)
    sqlStatement = "INSERT INTO `" + tableName + "` (`Date`, `Time`, "
    sqlStatement += ", ".join("`" + column + "`" for column in columns)
    sqlStatement += ") VALUES (" + ", ".join(["%s"] * (len(columns) + 2)) + ")"

    for countlines, values in enumerate(rows, 2):
        date, time_var = values[0].split()
        cursor.execute(
            "SELECT 1 FROM `" + tableName + "` WHERE `TimeStamp` = %s LIMIT 1",
            (values[0],))
        if cursor.fetchone() is None:
            cursor.execute(sqlStatement, [date, time_var] + values)
            log.write("Added entry " + str(countlines) + " as record #" + values[1] + "\n")
            print("Added entry " + str(countlines) + " as record #" + values[1])
        else:
            print("Entry " + str(countlines) + " already there.")

    conn.commit()
    cursor.close ()
    conn.close ()
    log.close()

except MySQLdb.Error as e:
    print("Error %d: %s" % (e.args[0], e.args[1]))
    sys.exit (1)
