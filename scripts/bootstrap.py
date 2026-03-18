from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT_DIR = Path(__file__).resolve().parent.parent
PIPELINE_DIR = ROOT_DIR / "pipeline"
TESTDATA_DIR = ROOT_DIR / "pipeline-testdata"
VERSION_FILE = ROOT_DIR / "docker" / "casa" / "version.env"
CASA_DIR = ROOT_DIR / "docker" / "casa"
DATA_DIR = ROOT_DIR / "docker" / "data"
APPTAINER_DIR = ROOT_DIR / "apptainer"
REQUIRED_DATA_DIRS = ("alma", "catalogs", "ephemerides", "geodetic")


def say(message: str = "") -> None:
    print(message)


def run_command(
    *args: str, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(
            args=args, returncode=127, stdout="", stderr=""
        )


def detect_runtime() -> str | None:
    """
    Return 'docker', 'apptainer', or None if neither is available.
    """
    docker = run_command("docker", "info")
    if docker.returncode == 0:
        return "docker"
    if run_command("apptainer", "--version").returncode == 0:
        return "apptainer"
    return None


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def main() -> int:
    required_failures = 0
    optional_warnings = 0
    pipeline_ready = False
    testdata_ready = False
    casa_tarball_ready = False
    measures_data_ready = False

    def ok(message: str) -> None:
        say(f"[ok] {message}")

    def warn(message: str) -> None:
        nonlocal optional_warnings
        optional_warnings += 1
        say(f"[warn] {message}")

    def fail(message: str) -> None:
        nonlocal required_failures
        required_failures += 1
        say(f"[fail] {message}")

    runtime = detect_runtime()
    say(f"Bootstrap check for {ROOT_DIR}")
    say()

    status_result = run_command(
        "git", "-C", str(ROOT_DIR), "submodule", "status", "pipeline"
    )
    if status_result.returncode == 127:
        fail("git is not installed or not on PATH.")
    elif status_result.returncode != 0:
        say("[...] git submodule status pipeline failed, cloning as submodule...")
        add_result = run_command(
            "git",
            "submodule",
            "add",
            "https://open-bitbucket.nrao.edu/scm/pipe/pipeline.git",
        )
        init_result = run_command(
            "git", "-C", str(ROOT_DIR), "submodule", "update", "--init", "pipeline"
        )
        if init_result.returncode == 0:
            pipeline_ready = True
            ok("pipeline/ submodule added and initialized")
    elif status_result.stdout.startswith("-"):
        say(
            "[..] pipeline/ submodule not initialised — running: git submodule update --init pipeline"
        )
        init_result = run_command(
            "git", "-C", str(ROOT_DIR), "submodule", "update", "--init", "pipeline"
        )
        if init_result.returncode == 0:
            pipeline_ready = True
            ok("pipeline/ submodule initialised successfully.")
        else:
            fail(
                f"git submodule update --init pipeline failed: {init_result.stderr.strip()}"
            )
    else:
        pipeline_ready = True
        ok("pipeline/ is present and usable as a Git checkout.")

    if TESTDATA_DIR.is_dir():
        result = run_command(
            "git", "-C", str(TESTDATA_DIR), "rev-parse", "--is-inside-work-tree"
        )
        if result.returncode == 0:
            ok("pipeline-testdata/ is present as a Git checkout.")
            lfs_version = run_command("git", "lfs", "version")
            if lfs_version.returncode == 0:
                lfs_files = run_command(
                    "git", "-C", str(TESTDATA_DIR), "lfs", "ls-files"
                )
                first_lfs_line = next(
                    (line for line in lfs_files.stdout.splitlines() if line.strip()), ""
                )
                if first_lfs_line:
                    testdata_ready = True
                    ok("pipeline-testdata/ declares Git LFS-tracked content.")
                else:
                    warn(
                        "pipeline-testdata/ has no visible Git LFS files. Check whether the checkout is complete."
                    )
            else:
                warn(
                    "git-lfs is not installed. Install it before using pipeline-testdata/."
                )
        else:
            warn("pipeline-testdata/ exists but is not a usable Git checkout.")
    else:
        warn(
            "pipeline-testdata/ is absent. Clone it if you need component or regression tests."
        )
        say(
            "      git clone https://open-bitbucket.nrao.edu/scm/pipe/pipeline-testdata.git pipeline-testdata"
        )

    if VERSION_FILE.is_file():
        ok("Found CASA version config at docker/casa/version.env.")
        casa_version = parse_env_file(VERSION_FILE).get("CASA_VERSION", "")
        if casa_version:
            casa_tarball = CASA_DIR / f"casa-{casa_version}.tar.xz"
            if casa_tarball.is_file():
                casa_tarball_ready = True
                ok(f"CASA tarball is present for CASA_VERSION={casa_version}.")
            else:
                warn(
                    f"Missing CASA tarball for CASA_VERSION={casa_version}. Run: ./docker/download.sh --casa"
                )
        else:
            fail("docker/casa/version.env does not define CASA_VERSION.")
    else:
        fail("Missing docker/casa/version.env.")

    if DATA_DIR.is_dir():
        missing_dirs = [
            name for name in REQUIRED_DATA_DIRS if not (DATA_DIR / name).is_dir()
        ]
        if not missing_dirs:
            measures_data_ready = True
            ok("CASA measures data looks present under docker/data/.")
        else:
            missing = " ".join(missing_dirs)
            warn(
                f"docker/data/ exists but looks incomplete (missing: {missing}). Run: ./docker/download.sh --data"
            )
    else:
        warn(
            "docker/data/ is missing. Run: ./docker/download.sh --data if you need CASA or data-heavy tests."
        )

    # --- runtime -----------------------------------------------------------------

    apptainer_dev_sif_ready = False
    apptainer_casa_sif_ready = False

    if runtime == "docker":
        ok("Docker is available.")
    elif runtime == "apptainer":
        ok("Apptainer is available (Docker not detected — HPC mode).")
        dev_sif = APPTAINER_DIR / "pipeline-dev.sif"
        casa_sif = APPTAINER_DIR / "pipeline-casa.sif"
        if dev_sif.is_file():
            apptainer_dev_sif_ready = True
            ok("apptainer/pipeline-dev.sif is present.")
        else:
            warn(
                "apptainer/pipeline-dev.sif is missing. Build it on a Docker machine with: ./apptainer/build.sh --dev"
            )
        if casa_sif.is_file():
            apptainer_casa_sif_ready = True
            ok("apptainer/pipeline-casa.sif is present.")
        else:
            warn(
                "apptainer/pipeline-casa.sif is missing. Build it on a Docker machine with: ./apptainer/build.sh --casa"
            )
    else:
        fail(
            "Neither Docker nor Apptainer was found. Install one to use the containerised workflow."
        )

    say()
    say("Summary")

    if required_failures == 0:
        ok("Core development prerequisites look ready.")
    else:
        say("[fail] Core development prerequisites are incomplete.")

    if optional_warnings == 0:
        ok("Optional CASA and regression-test assets are present.")
    else:
        say(
            f"[warn] {optional_warnings} optional prerequisite(s) need attention for CASA or heavier test workflows."
        )

    say()
    say("Suggested next steps")

    if not testdata_ready:
        say("  Clone pipeline-testdata/ before running component or regression tests:")
        say(
            "    git clone https://open-bitbucket.nrao.edu/scm/pipe/pipeline-testdata.git pipeline-testdata"
        )

    if runtime == "docker":
        if pipeline_ready:
            say("  make build-dev")
            say("  make shell-dev")
        if not measures_data_ready:
            say("  ./docker/download.sh --data")
        if not casa_tarball_ready:
            say("  ./docker/download.sh --casa")
        if casa_tarball_ready and measures_data_ready:
            say("  make build-casa")
    elif runtime == "apptainer":
        if not apptainer_dev_sif_ready:
            say("  Build the dev SIF on a Docker machine, then transfer it:")
            say("    ./apptainer/build.sh --dev")
        if pipeline_ready and apptainer_dev_sif_ready:
            say("  ./apptainer/run-dev.sh")
        if not measures_data_ready:
            say("  ./docker/download.sh --data   # auto-detects Apptainer")
        if not apptainer_casa_sif_ready:
            say("  Build the casa SIF on a Docker machine, then transfer it:")
            say("    ./apptainer/build.sh --casa")

    return 1 if required_failures else 0


if __name__ == "__main__":
    sys.exit(main())
