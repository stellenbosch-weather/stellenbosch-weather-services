#!/usr/bin/python
import sys
import time
from pprint import pprint
import re
import time
import datetime
import urllib2
import math
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from settings_loader import load_settings

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
    print "You already have an instance of the program running"
    print "It is running as process %s," % oldpid
    sys.exit(1)
  else:
    print "File is there but the program is not running"
    print "Removing lock file for the: %s as it can be there because of the program last time it was run" % oldpid
    os.remove(lock_file)

#This is part of code where we put a PID file in the lock file
pidfile = open(lock_file, "w")
newpid = str(os.getpid())
print "PID="+newpid
pidfile.write(newpid)
pidfile.close()


stationName = "Sonbesie"
tableName = "SB_THour"
dataFile = "http://"+Config.get("sonbesie", "address")+"/?command=TableDisplay&table=THour&records="

log = open(log_file, 'a')
log.write( "Run start: "+time.strftime("%Y-%m-%d", time.localtime(time.time()))+" "+time.strftime("%H:%M:%S", time.localtime(time.time()))+"\n" )

try:
    import MySQLdb
except:
    print "ERROR !!!!\nMySQLdb not installed."
    sys.exit(1)

try:
    # Statics
    titles = []
    sqlBaseStatement = "INSERT INTO "+tableName+" (Date, Time, "
    
    # Database connection
    conn = MySQLdb.connect (host = Config.get("database", "host"),
                        user = Config.get("database", "username"),
                        passwd = Config.get("database", "password"),
                        db = Config.get("database", "database"))
    cursor = conn.cursor ()
    
    # Get the last date and count the amount of days to get
    sqlStatement = "SELECT MAX(`TimeStamp`) FROM "+tableName
    cursor.execute(sqlStatement)
    lastDate = cursor.fetchone()[0]
    now = datetime.datetime.now()
    delta = now - lastDate
    
    # read in file
#    f = open(dataFile)
    dataFile = dataFile+str(int((delta.days*24) + (delta.seconds/60/60) + 1 ))
    pprint(dataFile)
    f = urllib2.urlopen(dataFile)
    
    filecontents = f.read()
#    pprint( filecontents)
    f.close()
    
    rows = re.findall(r'<tr.*?>(.*?)</tr>', filecontents, re.S|re.I)
#    pprint( rows)

    countlines = 0
    for row in rows:
#    if 0:
        countlines = countlines + 1
        
        if (countlines == 1):
            values = re.findall(r'<th.*?>(.*?)</th>', row, re.S|re.I)
            #pprint (values)
            for x in values:
                x = x.strip('", ')
                #print x
                if(x == "TIMESTAMP"):
                    x = "TimeStamp"
                if(x == "RECORD"):
                    x = "Record"
                sqlBaseStatement = sqlBaseStatement + x + ', '
            sqlBaseStatement = sqlBaseStatement.rstrip(', ')
            #print sqlBaseStatement

        if (countlines >= 2):
            values = re.findall(r'<td.*?>(.*?)</td>', row, re.S|re.I)
            timeDate = values[0].strip('", ').split(" ");
            date = timeDate[0]
            time = timeDate[1]
            sqlString = "SELECT * FROM `"+tableName+"` WHERE `Date` = '"+date+"' AND `Time` = '"+time+"'"
            cursor.execute(sqlString)
            
            if (cursor.rowcount==0):
                sqlStatement = sqlBaseStatement + ") VALUES ('"+date+"', '"+time+"'"

                for value in values:
                    if (value.strip('", ') == "NAN"):
                        sqlStatement = sqlStatement + ",NULL"
                    else:
                        sqlStatement = sqlStatement + ",'"+value.strip('", ')+"'"

                sqlStatement = sqlStatement + ")"
                cursor.execute(sqlStatement)
                
                log.write("Added entry " + str(countlines) + " as record #"+values[1]+"\n")
                print "Added entry " + str(countlines) + " as record #"+values[1]
                
            else: 
                print "Entry "+str(countlines)+" already there."
    
    cursor.close ()
    conn.close ()
    log.close()

except MySQLdb.Error, e:
    print "Error %d: %s" % (e.args[0], e.args[1])
    sys.exit (1)
