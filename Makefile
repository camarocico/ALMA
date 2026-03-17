SHELL := /bin/sh

.DEFAULT_GOAL := help

include docker/casa/version.env
export CASA_VERSION

COMPOSE ?= docker compose
PYTHON ?= python3
DEV_SERVICE := dev
CASA_SERVICE := casa

