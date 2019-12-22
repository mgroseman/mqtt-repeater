#!/bin/sh

#source variables
. ./podman_env

#Stop existing container if running
podman stop ${INSTANCE_NAME}

#Delete existing if an image has the same name
podman rmi mqtt-repeater-${VERSION}

#Build image
podman build --tag mqtt-repeater-${VERSION} .

