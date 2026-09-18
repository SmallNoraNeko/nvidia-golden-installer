# Golden Triangle — Reproducible Build Environment
# Platform: aarch64 (must run on ARM64 machine)
# Usage: see README.md

FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    makeself \
    patchelf \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install cryptography nuitka --break-system-packages

WORKDIR /build

# Source files (GPU_RUN, CUDA_RUN, DOCA_DEB) must be mounted at /build
# via -v $(pwd):/build when running the container.
# They are NOT included in this image.

ENTRYPOINT ["python3", "build_golden.py"]
