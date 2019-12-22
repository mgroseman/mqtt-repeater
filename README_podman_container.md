This has been tested in CentOS8 using Podman. Docker would be similar syntax, but hasn't been tested.<br>
Running as root containers using sudo.   

1)  Edit podman_env for variables about your instance
2)  sudo ./podman_build.sh
3)  Create etc/mqtt_repeater.cfg from etc/mqtt_repeater.cfg.example 
4)  sudo ./podman_run.sh

5)  debugging commands if necessary:

    tail logs/mqtt_repeater.log
    sudo podman ps 
    sudo podman ps --all
    sudo podman logs <instancename>
    sudo podman exec -it <instancename> sh

6) Autostart:  See instructions in systemd-script/mqtt-repeater-container.service 

Query Command examples to read from database: <br>
    sudo podman exec -it <instancename> util/mqtt_db_dump.py
    sudo podman exec -it <instancename> util/mqtt_db_query.py MQTT_1 /farm/sensors/garage/temp

