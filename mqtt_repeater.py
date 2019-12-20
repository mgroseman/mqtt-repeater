#!/usr/bin/python
# Script to setup a MQTT repeater system.
# Copyright (c) 2016 - mgroseman - Mike Roseman
# MIT License
#
#  You can duplicate messages across both MQTT and Adafruit IO services.
#  You can write to a file and/or SQLite DB  (file is historical data.  DB stores just the last values.)

# Note:  Adafruit IO does speak MQTT, and their library mainly puts a wrapper around some functions for ease of use
# Use case:  
#    You have a local MQTT broker on your home network.  (to log or to integrate with OpenHAB or because of security encryption concerns.)
#    You wish to send some feeds/topics up to Adafruit IO servers for display on their dashboard.
#    You can also have it watch Adafruit IO servers for messages and repeat on your local MQTT server  (eg.  If you hit a button on a IO Dashboard)
#    You can either have your device (Arduino, etc) send to both services, or use this code to watch both services and repeat incoming messages
#    You can write to a file for historical or graphing purposes.  CSV format.
#    You can store values in SQLite DB, so you can query the last status for any topic.
#
# This has been tested with the 'mosquitto' open-source MQTT broker
#
#  Issues:
#   - For some reason Adafruit doesn't always connect for me, and doesn't generate an error or even complete the internal paho-MQTT function.
#      So, if you don't see:  "Connected to Adafruit IO!  Subscribing..."  
#      Just hit Ctrl-C and try again.  I even had to restart my computer once because it wouldn't connect.  Very odd.
#

# Import python modules.
import random
import sys
import time
import logging
import threading 
import socket
import datetime
import sqlite3

# Import Adafruit IO MQTT client.
from Adafruit_IO import MQTTClient

#Global variables
cfgfile='etc/mqtt_repeater.cfg'   # File that contains settings and rules on what to duplicate
LOGFILE='logs/mqtt_repeater.log'   # File to send standard output.  Look at logging.basicConfig line below if you don't want to output to a file.

settings_dict=dict()
#Basic structure of this nested dictionary looks like:
#settings_dict[INSTANCE_NAME] = dictionary of instance names
#settings_dict[INSTANCE_NAME]['SETTING_NAME'] = value 
#settings_dict[INSTANCE_NAME]['instance'] = MQTTClient object   # Send library methods to here, like .connect()
#settings_dict[INSTANCE_NAME]['instance']._service_host # Internal instance variable
#settings_dict[INSTANCE_NAME]['instance']._service_port # Internal instance variable
#settings_dict[INSTANCE_NAME]['instance']._instance_name # Internal instance variable - useful to see who is calling a callback function

#Default values if not set in cfgfile
settings_defaults_dict = { 
  'USERNAME': '', 'PASSWORD': '', 'SERVER': 'io.adafruit.com', 'PORT': 1883, 
  'KEEPALIVE': 3600, 'CLIENTID' : None, 'TOPIC_FMT': 'adafruit_fmt', 'QOS': 1, 
  'RETRY_COUNTER': 1, 'MAX_RETRIES' : 3, 'TLS_SET' : 0, 'CACERT': None }

logger = logging.getLogger('mqtt_repeater')  #label when logging

#logging level.  Use one of these:
#Maybe READ level from command line (with a default to WARNING)
#Not to a file:
#logging.basicConfig(format='%(asctime)s:%(name)s:%(process)s:%(levelname)s:%(message)s', level=logging.INFO)
#logging.basicConfig(format='%(asctime)s:%(name)s:%(process)s:%(levelname)s:%(message)s', level=logging.DEBUG)
#or to a file:
#logging.basicConfig(filename='myapp.log', format='%(asctime)s:%(name)s:%(process)s:%(levelname)s:%(message)s', level=logging.DEBUG)
#INFO Shows every received message and way it is handled:
#logging.basicConfig(filename=LOGFILE, format='%(asctime)s:%(name)s:%(process)s:%(levelname)s:%(message)s', level=logging.INFO)
#WARNING only shows warnings and above 
logging.basicConfig(filename=LOGFILE, format='%(asctime)s:%(name)s:%(process)s:%(levelname)s:%(message)s', level=logging.WARNING)

#Read configuration file and store values in nested dictionaries
def read_cfgfile(filename):
    logger.info("----")
    logger.info("Reading file: %s", filename)
    f = open(filename)
    for l in f:  # Read lines
      line=l.strip()
      if not line.startswith("#") and line != "":
        # Store settings
        if line.startswith("set"):
         if line.count(" ") == 2:  # If no last field (value)
           mset,name,setting = line.split()
           value = ""  # Will pull default value later on
         else:
           mset,name,setting,value = line.split()
         if setting == "PASSWORD":   # Don't print password to screen or log
          logger.info("Storing setting (%s): %s -> ********", name, setting)
         else:   # Print everything else read from file
          logger.info("Storing setting (%s): %s -> %s", name, setting, value)
         if name not in settings_dict:  #If first time hitting this name, initialize its nested dictionaries
           settings_dict[name] = dict()
           settings_dict[name]['topic_map_dict'] = dict()  # For mappings later in loop
         settings_dict[name][setting] = value  # Save value
        else:
         # Store input->output mappings
         # Test # of fields.
         if len(line.split()) == 4:  # Assume MQTT/ADA broker destination
           sname,source,dname,dest = line.split()
           logger.info("Storing map pair (%s): %s -> (%s): %s", sname, source, dname, dest)
         elif len(line.split()) == 3:  # Assume FILE destination
           sname,source,dname = line.split()
           dest = 'BLANK'  # Just a placeholder for files and db.  
           logger.info("Storing map pair (%s): %s -> (%s)", sname, source, dname)
         else:  # Syntax error
             logger.critical("Line length error in config file.  Line length: %s", len(line.split()))
             logger.critical("LINE: %s", line)
             sys.exit(11)
         # Actually Store mapping
         if sname not in settings_dict:   # All sources need 'set' lines in file to define source
          logger.critical("%s message source not defined in any 'set' lines.  Exiting.", sname)
          sys.exit(11)
         else:
          if source in settings_dict[sname]['topic_map_dict']:  # Adding additional output for mapping
           logger.info(" source existed, adding new pair")
           settings_dict[sname]['topic_map_dict'][source].append((dname,dest))
          else:  # New output mapping
           settings_dict[sname]['topic_map_dict'][source] = [(dname, dest)]
            
    # Fill in missing settings with defaults
    for name in settings_dict:
     if settings_dict[name]['TOPIC_FMT'] == 'file':   #If a file type.  This isn't a source.  Only takes FILENAME and TOPIC_FMT
      if 'FILENAME' not in settings_dict[name]:
          logger.critical("%s missing filename for file output.  Exiting.", name)
          sys.exit(13)
      #Files only need two settings TOPIC_SMT and FILENAME
      test_file(settings_dict[name]['FILENAME']) #test file for writability. If not, exit program
      continue
     elif settings_dict[name]['TOPIC_FMT'] == 'sqlite':   #If a sqlite type.  This isn't a source.  Only takes FILENAME and TOPIC_FMT
      if 'FILENAME' not in settings_dict[name]:
          logger.critical("%s missing filename for DB output.  Exiting.", name)
          sys.exit(13)
      #Files only need two settings TOPIC_SMT and FILENAME
      test_file(settings_dict[name]['FILENAME']) #test file for writability. If not, exit program
      continue
     else:  #Other types, lookup defaults
      for setting in settings_defaults_dict:
        if setting not in settings_dict[name]:   #Use default from above global variable settings_defaults_dict.
         logger.info("Setting not found (%s): %s -> Using default -> %s", name, setting, str(settings_defaults_dict[setting]))
         settings_dict[name][setting] = settings_defaults_dict[setting]
      if 'LABEL' not in settings_dict[name]:  # Autogenerate default LABEL from source name
        logger.info("Setting not found (%s): LABEL -> Using default -> %s",name, name)
        settings_dict[name]['LABEL'] = name
    logger.info("----")
    logger.info("")
    f.close()



#Function to search dictionaries for a matching output rules.  Returns list of destinations for topic
def search_map(name, incoming_topic):
    outgoing_topics = ""
    if incoming_topic in settings_dict[name]['topic_map_dict']:
       logger.debug("Found matching topic - %s - %s", name, incoming_topic)
       outgoing_topics = settings_dict[name]['topic_map_dict'][incoming_topic]
       logger.debug(" Outgoing topics - %s ", outgoing_topics)

    if outgoing_topics == "":
#TODO:  Add Regex searching to match # as a wildcard for FILE/DB saves.  (eg. \#)
       logger.info("No matching topic found.  Ignoring.  Topic: %s", incoming_topic)

    return(outgoing_topics)

#Test output file for writability
def test_file(filename):
  file = open(filename, 'a')  #Append-only
  file.close()


#Publish data to a file
# Called using these parameters: (client._instance_name, feed_id, dest, settings_dict[dest]['FILENAME'], payload)
#TODO: handle errors gracefully instead of exiting.
def publish_file(name, sourcefeed, dest, filename, payload):
  file = open(filename, 'a')  #Append-only
  timestring = datetime.datetime.now().isoformat()  # Current timestamp. This is evil in python and should be easier
  #  Human readable if desired
  #file.write("{0}\t{1}\t\t{2}\t\t{3}\n".format(timestring,name,sourcefeed,payload))
  #  CSV format
  file.write("{0},{1},{2},{3}\n".format(timestring,name,sourcefeed,payload))
  file.close()

def publish_sqldb(name, sourcefeed, dest, filename, payload):
  # Apparently you need to create SQL files within the same thread
  #  Therefore need to open DB file for each publish
  #Setup SQL DB
  dbconn = sqlite3.connect(settings_dict[dest]['FILENAME'])
  sqldb = dbconn.cursor()
  timestring = datetime.datetime.now().isoformat()  # Current timestamp. This is evil in python and should be easier
  # Check to see if this feed already exists
  sqldb.execute('SELECT * FROM states WHERE source_label=? and source_feed=?', (name, sourcefeed))
  if sqldb.fetchone() is None:  # Fetchone reads the previous .execute output
     # New entry
     sqldb.execute('INSERT INTO states VALUES (?,?,?,?)', (name, sourcefeed, payload, timestring))
  else:  
     # If this source/feed entry already exists, do an update
     sqldb.execute('UPDATE states SET value=?, last_timestamp=? WHERE source_feed=? and source_label=?', (payload, timestring, sourcefeed, name))
  #Save (commit) the changes
  dbconn.commit()
  dbconn.close()


# Start instance of MQTT input client
def instance_start(c, name):
 # Using 'c' instead of 'client' for easier reading/writing
 #Last field 'name' of client will be used to set '_instance_name' so we can read a unique name inside callback functions
 logger.info('Setting up instance and connecting: %s', name)
 c['instance'] = MQTTClient(c['USERNAME'], c['PASSWORD'], c['SERVER'], int(c['PORT']), c['CLIENTID'], c['TOPIC_FMT'], name)  # Create MQTTClient instance
 logger.debug("New instance: %s *PASSWORD* %s %s %s %s %s ",c['USERNAME'], c['SERVER'], int(c['PORT']), c['CLIENTID'], c['TOPIC_FMT'], name)
 # Setup the callback functions defined below.
 c['instance'].on_connect    = connected
 c['instance'].on_disconnect = disconnected
 c['instance'].on_message    = message
 #Setup TLS for basic connection encryption (like a web browser using HTTPS)
 # - You can probably do other TLS connection types like pre-shared key authentication if you modify this code and add setting variables
 # For Adafruit, just use normal OS CA lookup bundle file in /etc/ssl/certs/:  (Probably OS-dependent location)
 if c['TLS_SET'] == "1":
   logger.debug("Set TLS: %s", c['CACERT'])
   c['instance'].tls_set(c['CACERT'])  # If you need more of the TLS settings, feel free to add to config file and here.
 # Connect to servers
 # Need to convert these from strings to integers to use for counting
 c['RETRY_COUNTER'] = int(c['RETRY_COUNTER'])
 c['MAX_RETRIES'] = int(c['MAX_RETRIES'])
 while True:   #Loop until complete or retry limit hit
   try:
     c['instance'].connect()  # Try to connect.  Some errors might be fatal.
   except:  # Have only seen 'socket.errors', but could be other kinds
     if c['RETRY_COUNTER'] > c['MAX_RETRIES']:
       logger.critical('Giving up retries to %s (%s).  Terminating process.', c['instance']._service_host, c['instance']._instance_name)
       for name in settings_dict:
        if 'instance' in settings_dict[name]:  #For each existing instance besides this one
         settings_dict[name]['instance'].disconnect()  # Terminate instance
       sys.exit(1)
     logger.error('%s connect error for %s. Retry # %s', str(sys.exc_info()[0]), c['instance']._instance_name, str(c['RETRY_COUNTER']))
     c['RETRY_COUNTER'] += 1;  # Iterate try
     time.sleep(5)  # Delay before retry
   else:
     # Connection Worked.  Reset counter and break loop
     c['RETRY_COUNTER'] = 1;
     break


# Define callback handler functions.  Called when events happen.
def connected(client):
    # Connected function will be called when the client is connected to MQTT source
    logger.info('Connected to %s (%s) - Subscribing...', client._service_host, client._instance_name)
    settings_dict[client._instance_name]['RETRY_COUNTER'] = 0;
    # Subscribe to changes on feeds defined in config file
    if settings_dict[client._instance_name]['topic_map_dict'] == {}:
      logger.info(" No Subscriptions on this server.")
    for feed in settings_dict[client._instance_name]['topic_map_dict']:  # Loop through output feeds for this topic
      logger.info(' Subscribe to: %s - QOS: %s', feed, settings_dict[client._instance_name]['QOS'])
      client.subscribe(feed, int(settings_dict[client._instance_name]['QOS']))
    logger.info('')

def disconnected(client):
    # Disconnected function will be called when the client disconnects.
    time.sleep(1)  # In case disconnect is on purpose during exit, wait a second before retry
    logger.error('Disconnected from %s (%s)! Retrying...', client._service_host, client._instance_name)
    logger.error('')
    if settings_dict[client._instance_name]['RETRY_COUNTER'] == settings_dict[client._instance_name]['MAX_RETRIES']:
       logger.critical('Giving up retries to %s (%s).  Terminating process.', client._service_host, client._instance_name)
       for name in settings_dict: 
        if 'instance' in settings_dict[name]:  #For each exiting instance besides this one
         settings_dict[name]['instance'].disconnect()  # Terminate instance
       sys.exit(1)
    settings_dict[client._instance_name]['RETRY_COUNTER'] += 1;
    time.sleep(5)
    client.connect()  # Try to reconnect.  Some things are always fatal

def message(client, feed_id, payload):
    # Message function will be called when a subscribed feed has a new value.
    # The feed_id parameter identifies the feed, and the payload parameter has the value
    logger.info('%-12s <- Receive: (%s) - %s', client._instance_name, feed_id, payload)
    # Search for output mapping rules:
    outgoing_topics = search_map(client._instance_name, feed_id)
    if outgoing_topics != "":
      for dest,dtopic in outgoing_topics:  # For each destination defined.  Can have multiple
       if settings_dict[dest]['TOPIC_FMT'] == 'file':   # If FILE output
         logger.info('%-12s -> Publish: (%s) - %s', dest, settings_dict[dest]['FILENAME'], payload)
         publish_file(client._instance_name, feed_id, dest, settings_dict[dest]['FILENAME'], payload)
       elif settings_dict[dest]['TOPIC_FMT'] == 'sqlite':   # If SQL DB output
         logger.info('%-12s -> Publish: (%s) - %s', dest, settings_dict[dest]['FILENAME'], payload)
         publish_sqldb(client._instance_name, feed_id, dest, settings_dict[dest]['FILENAME'], payload)
       else:  #If MQTT/Adafruit output
         logger.info('%-12s -> Publish: (%s) - %s', dest, dtopic, payload)
         settings_dict[dest]['instance'].publish(dtopic, payload, int(settings_dict[dest]['QOS']))
    logger.info('')
    logger.info('')


#Begin Main Code
print("Started.  Logging to: " + LOGFILE)
#Print something so we know log is working
logger.error('MQTT Repeater Service Started')

# Read the configuration file
read_cfgfile(cfgfile)

#Setup SQL DBs
for name in settings_dict:
 if settings_dict[name]['TOPIC_FMT'] == 'sqlite':  
   dbconn = sqlite3.connect(settings_dict[name]['FILENAME']) 
   sqldb = dbconn.cursor()
   # Create 'states' table if it doesn't exist
   sqldb.execute('''CREATE TABLE IF NOT EXISTS states
             (source_label text, source_feed text, value text, last_timestamp text)'''
   )
   # Should we create another table to log all data historically?
   # Since writes occur in different threads, might as well close this here.
   # Each thread needs it's own connection setup apparently.
   dbconn.close()
 else:
  continue  #Skip non-DB


#Do some threading magic to watch for clients dying.  Keep a dictionary of running thread descriptors
thread_dict = {}
#Store the 'main' thread
thread_dict['main'] = threading.currentThread()

# Create client instances
for name in settings_dict:
 if settings_dict[name]['TOPIC_FMT'] == 'file' or settings_dict[name]['TOPIC_FMT'] == 'sqlite':  #Don't run instance_start() if rule is output-only file or db
  continue  #Skip files
 instance_start(settings_dict[name],name)  #Create instance definition and start in background

logger.info('----')
# Start background threads for clients
for name in settings_dict:
 if settings_dict[name]['TOPIC_FMT'] == 'file' or settings_dict[name]['TOPIC_FMT'] == 'sqlite':  # Skip file and db definitions
  continue  #Skip output files
 settings_dict[name]['instance'].loop_background() # Start thread in background
 time.sleep(0.1)  #slight delay
  # Store thread associations in dictionary for monitoring
 for thread in threading.enumerate():  # Get all current threads
  if thread in thread_dict:
   continue   # If found already, skip.  Anything left is new thread
  thread_dict[name] = thread  #Store thread association


time.sleep(0.5)  #slight delay
logger.info('----')
logger.info('')
logger.info('...(Ctrl-C a few times will quit)...')
logger.info('')
logger.info('')

#Run until someone kills me
while True:
  
  #Monitor for dead instances/threads.  
  for name in thread_dict:  # Get threads from dictionary
   if not thread_dict[name].is_alive():  # If thread died
      logger.info('----')
      logger.debug(threading.enumerate())  #Print remaining threads for debugging purposes
      logger.error("Thread dead: %s  Restarting...", name)
      #Try to restart dead thread 
      settings_dict[name]['instance'].disconnect()   # Disconnect dead thread (might not be necessary)
      thread_dict[name] = None  #remove dead association from dictionary
      instance_start(settings_dict[name],name)  #Create new instance definition and connect (will retry # of times inside this function)
      settings_dict[name]['instance'].loop_background() # Start thread in background
      time.sleep(0.5)  #slight delay
      for thread in threading.enumerate():  # Get all current threads
       if thread in thread_dict:
        continue   # If found already, skip.  Anything left is new thread
       thread_dict[name] = thread  #Store new thread identifier
      logger.info('----')

  time.sleep(10)  # Sleep between monitor probes

#End
