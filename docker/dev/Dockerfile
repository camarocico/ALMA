FROM ubuntu:24.04

# Install micromamba
RUN apt-get update \
    && apt-get install -y --no-install-recommends bzip2 curl ca-certificates git less \
    && curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xvj -C /usr/local bin/micromamba \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV MAMBA_ROOT_PREFIX=/opt/conda

RUN useradd -m -s /bin/bash pipeline

# Copy only the environment specs: pipeline source is bind-mounted at runtime
# requirements.txt must be alongside environment.yml since it's referenced via -r requirements.txt
COPY pipeline/environment.yml /tmp/environment.yml
COPY pipeline/requirements.txt /tmp/requirements.txt
COPY pipeline/requirements_dev.txt /tmp/requirements_dev.txt

# Create the conda environment and install dev tools
RUN micromamba create -f /tmp/environment.yml -n pipeline --yes \
    && micromamba run -n pipeline pip install --disable-pip-version-check -r /tmp/requirements_dev.txt \
    && micromamba clean --all --yes

# Add .pth file so the bind-mounted source (/home/pipeline/pipeline) is importable
# without needing pip install -e (which fails on read-only mounts)
RUN echo '/home/pipeline/pipeline' \
    > /opt/conda/envs/pipeline/lib/python3.12/site-packages/pipeline-src.pth

USER pipeline
WORKDIR /home/pipeline

# Create CASA data directory as a mount point for the measures data volume.
RUN mkdir -p /home/pipeline/.casa/data

# Allow git to operate on the bind-mounted source (owned by host user, not container user).
RUN git config --global --add safe.directory /home/pipeline/pipeline

ENV PATH=/opt/conda/envs/pipeline/bin:$PATH \
    CONDA_PREFIX=/opt/conda/envs/pipeline \
    CONDA_DEFAULT_ENV=pipeline
