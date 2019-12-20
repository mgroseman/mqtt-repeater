#!/usr/bin/env python
#This needs to be fully commented and have a Usage message
# Copyright (c) 2016 - mgroseman - Mike Roseman
# MIT License


import sqlite3
SQLDB='db/mqtt_repeater.db'
conn = sqlite3.connect(SQLDB)

db = conn.cursor()

for row in db.execute('SELECT * FROM states ORDER BY last_timestamp'):
        print('%s\t%s\t%s\t%s' % row)

conn.close()

