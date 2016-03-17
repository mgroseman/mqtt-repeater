#!/usr/bin/python
#This needs to be fully commented and have a Usage message
#Takes two args:   1) SOURCE label  2) topic
# eg.   mqtt_db_query.py MQTT_1 /home/sensor/temp
#
# Copyright (c) 2016 - mgroseman - Mike Roseman
# MIT License

import sqlite3
import sys
SQLDB='/var/tmp/mqtt_repeater.db'
conn = sqlite3.connect(SQLDB)

db = conn.cursor()

source=sys.argv[1]
topic=sys.argv[2]
db.execute('SELECT value FROM states WHERE source_label=? and source_feed=?', (source, topic))
print db.fetchall()[0][0]  # Needed to unpack tuple

conn.close()

