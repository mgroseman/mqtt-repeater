#!/bin/sh

#source variables
. ./podman_env

#Stop existing container if running
podman stop ${INSTANCE_NAME}

#Delete existing container
podman rm ${INSTANCE_NAME}

#Run container.  Bind-mount local directories into the containers for configs, logs, db and to use host timezone
podman run -dit -v $INSTALL_PATH/etc:/app/mqtt-repeater/etc:z -v  $INSTALL_PATH/logs:/app/mqtt-repeater/logs:z -v $INSTALL_PATH/db:/app/mqtt-repeater/db:z -v /etc/localtime:/etc/localtime:z,ro $RUN_OPTIONS --name ${INSTANCE_NAME} mqtt-repeater-${VERSION}

