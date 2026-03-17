#!/bin/sh
# Wrap every command in a virtual framebuffer so that CASA tools that require
# a display (e.g. plotms) work inside a headless container.
exec xvfb-run --auto-servernum "$@"
