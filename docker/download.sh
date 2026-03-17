#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
CASA_DIR="${SCRIPT_DIR}/casa"
VERSION_FILE="${CASA_DIR}/version.env"

if [ ! -f "${VERSION_FILE}" ]; then
    echo "Could not find CASA version file at ${VERSION_FILE}" >&2
    exit 1
fi

. "${VERSION_FILE}"

CASA_TARBALL="casa-${CASA_VERSION}.tar.xz"
CASA_URL="https://casa.nrao.edu/download/distro/casa/releaseprep/casa-${CASA_VERSION}.tar.xz"

if [ -z "${CASA_VERSION}" ]; then
    echo "Could not determine CASA_VERSION from ${VERSION_FILE}" >&2
    exit 1
fi

usage() {
    echo "Usage: $0 [--casa] [--data] [--all] [--runtime docker|apptainer]"
    echo "  --casa              Download CASA tarball (~800MB, needed for the casa service)"
    echo "  --data              Download CASA measures data (~400MB, needed by both services)"
    echo "  --all               Download everything"
    echo "  --runtime RUNTIME   Force runtime: docker or apptainer (default: auto-detect)"
    exit 1
}

GET_CASA=false
GET_DATA=false
RUNTIME=""

[ $# -eq 0 ] && usage

while [[ $# -gt 0 ]]; do
    case $1 in
        --casa)    GET_CASA=true ;;
        --data)    GET_DATA=true ;;
        --all)     GET_CASA=true; GET_DATA=true ;;
        --runtime) shift; RUNTIME="$1" ;;
        *)         usage ;;
    esac
    shift
done

# --- runtime detection -------------------------------------------------------

if [ -z "${RUNTIME}" ]; then
    if command -v docker &>/dev/null && docker info &>/dev/null 2>&1; then
        RUNTIME=docker
    elif command -v apptainer &>/dev/null; then
        RUNTIME=apptainer
    else
        echo "Error: neither Docker nor Apptainer is available." >&2
        echo "       Install one or use --runtime to specify explicitly." >&2
        exit 1
    fi
    echo "Runtime: ${RUNTIME} (auto-detected)"
else
    echo "Runtime: ${RUNTIME} (forced)"
fi

# --- download CASA tarball ---------------------------------------------------

if $GET_CASA; then
    if [ ! -f "${CASA_DIR}/${CASA_TARBALL}" ]; then
        echo "Downloading CASA ${CASA_VERSION}..."
        wget -q --show-progress "${CASA_URL}" -P "${CASA_DIR}"
    else
        echo "CASA tarball already present, skipping."
    fi
fi

# --- download CASA measures data ---------------------------------------------

if $GET_DATA; then
    echo "Downloading CASA measures data to ${SCRIPT_DIR}/data/ ..."
    mkdir -p "${SCRIPT_DIR}/data"
    chmod a+w "${SCRIPT_DIR}/data"

    PULL_CMD="python -c \"import casaconfig; casaconfig.pull_data(path='/home/pipeline/.casa/data')\""

    case "${RUNTIME}" in
        docker)
            docker compose -f "${ROOT_DIR}/docker-compose.yml" run --rm dev \
                bash -c "${PULL_CMD}"
            ;;
        apptainer)
            DEV_SIF="${ROOT_DIR}/apptainer/pipeline-dev.sif"
            if [ ! -f "${DEV_SIF}" ]; then
                echo "Error: ${DEV_SIF} not found." >&2
                echo "       Build it first with: ./apptainer/build.sh --dev" >&2
                exit 1
            fi
            apptainer exec \
                --writable-tmpfs \
                --bind "${SCRIPT_DIR}/data:/home/pipeline/.casa/data" \
                "${DEV_SIF}" \
                bash -c "${PULL_CMD}"
            ;;
        *)
            echo "Error: unknown runtime '${RUNTIME}'. Use 'docker' or 'apptainer'." >&2
            exit 1
            ;;
    esac

    echo "Measures data downloaded."
fi

echo "Done."
