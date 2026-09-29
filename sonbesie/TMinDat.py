#!/usr/bin/python
import sys
import time
from pprint import pprint
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from settings_loader import load_settings

Config = load_settings()

stationName = "Sonbesie"
tableName = "SB_TMin"
dataFile = "/home/weather/importWeatherdata/sonbesie/29DEC14-5JAN15.txt"

log = open("/home/weather/importWeatherdata/sonbesie/TMin.log", 'a')
log.write( "Run start: "+time.strftime("%Y-%m-%d", time.localtime(time.time()))+" "+time.strftime("%H:%M:%S", time.localtime(time.time()))+"\n" )

try:
    import MySQLdb
except:
    print "ERROR !!!!\nMySQLdb not installed."
    sys.exit(1)

try:
    # Database connection
    conn = MySQLdb.connect (host = Config.get("database", "host"),
                        user = Config.get("database", "username"),
                        passwd = Config.get("database", "password"),
                        db = Config.get("database", "database"))
    cursor = conn.cursor ()
    
    # read in file
    f = open(dataFile)
#    f = urllib.urlopen(dataFile, proxies={})
    
    titles = []
    sqlBaseStatement = "INSERT INTO "+tableName+" (Date, Time, "

    countlines = 0
    while 1:
        line = f.readline()
        if not line: break
        
        line = line.rstrip('\n\r')
        countlines = countlines + 1
        
        if (countlines == 2):
            titles = line.split(',')
            for x in titles:
                x = x.strip('", ')
                
                if(x == "TIMESTAMP"):
                    x = "TimeStamp"
                if(x == "RECORD"):
                    x = "Record"
                sqlBaseStatement = sqlBaseStatement + x + ','
            sqlBaseStatement = sqlBaseStatement.rstrip(',')

        if (countlines > 4):
            if(line==""):
              continue
            values = line.split(',')
            timeDate = values[0].strip('", ').split(" ");
            date = timeDate[0]
            time = timeDate[1]
            sqlString = "SELECT * FROM `"+tableName+"` WHERE `Date` = '"+date+"' AND `Time` = '"+time+"'"
#            print sqlString
            cursor.execute(sqlString)
            
            if (cursor.rowcount==0):

                sqlStatement = sqlBaseStatement + ") VALUES ('"+date+"','"+time+"','"+values[0].strip('", ')+"'"

                tel = 1
                while tel < len(values):
                    if (values[tel].strip('", ') == "NAN"):
                        sqlStatement = sqlStatement + ",NULL"
                    else:
                        sqlStatement = sqlStatement + ",'"+values[tel].strip('", ')+"'"
                    tel = tel + 1

                sqlStatement = sqlStatement + ")"
#                print(sqlStatement)
                cursor.execute(sqlStatement)
                
                log.write("Added entry " + str(countlines) + " as record #"+values[1]+"\n")
                print "Added entry " + str(countlines) + " as record #"+values[1]
#                print ".",
                
            else: 
                print "Entry "+str(countlines)+" already there."
#                print "-",
    f.close()
    
    cursor.close ()
    conn.close ()
    log.close()

except MySQLdb.Error, e:
    print "Error %d: %s" % (e.args[0], e.args[1])
    sys.exit (1)
