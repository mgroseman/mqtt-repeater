# mqtt-repeater
MQTT message repeater.   It can replicate messages between multiple MQTT or Adafruit IO servers.<br>
It can also write a file for historical record of messages, or save the last value in a SQLite DB for retrieval by external scripts.

Features:<br>
  You can duplicate messages across both MQTT and Adafruit IO services.<br>
  You can write to a file and/or SQLite DB  (file is historical data.  DB stores just the last values.)<br>

 Note:  Adafruit IO does speak MQTT, and their library mainly puts a wrapper around some functions for ease of use
 

 Use cases:  <br>
    You have a local MQTT broker on your home network.  (to log or to integrate with OpenHAB or because of security enc
ryption concerns.)<br>
    You wish to send some feeds/topics up to Adafruit IO servers for display on their dashboard.<br>
    You can also have it watch Adafruit IO servers for messages and repeat on your local MQTT server  (eg.  If you hit 
a button on a IO Dashboard)<br>
    You can either have your device (Arduino, etc) send to both services, or use this code to watch both services and r
epeat incoming messages<br>
    You can write to a file for historical or graphing purposes.  CSV format.<br>
    You can store values in SQLite DB, so you can query the last status for any topic.<br>

This has been tested with the 'mosquitto' open-source MQTT broker.

Installation:
NOTE:  This uses a branch of Adafruit IO's MQTT library, which has not been pushed upstream yet.  I'm waiting for another commit to be accepted by another contributor first.
You can use my tree here:
 https://github.com/mgroseman/io-client-python/tree/repeater
 Branch: repeater

Known Issues:<br>
   - For some reason Adafruit doesn't always connect for me, and doesn't generate an error or even complete the interna
l paho-MQTT function.<br>
      So, if you don't see:  "Connected to Adafruit IO!  Subscribing..."  <br>
      Just hit Ctrl-C and try again.  I even had to restart my computer once because it wouldn't connect.  Very odd.

