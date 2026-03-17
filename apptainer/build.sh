#!/bin/bash
# Build Apptainer SIF images from the existing Docker images.
#
# Prerequisites:
#   - Docker with the images already built (make build-dev and/or make build-casa)
#   - Apptainer installed and on PATH
#
# Output:
#   apptainer/pipeline-dev.sif   — development environment (Ubuntu + micromamba)
#   apptainer/runtime.sif        — CASA runtime environment (AlmaLinux + CASA)
#
# Typical usage (build both, then rsync to HPC):
#   ./apptainer/build.sh --all
#   rsync -av apptainer/*.sif hpc-host:~/alma/apptainer/

