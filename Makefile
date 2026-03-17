SHELL := /bin/sh

.DEFAULT_GOAL := help

include docker/casa/version.env
export CASA_VERSION

