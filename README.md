<div align="center">

# Golden Triangle Offline Installer

[![Platform](https://img.shields.io/badge/Platform-ARM64%20%2F%20aarch64-blue?style=flat-square)](.)
[![OS](https://img.shields.io/badge/OS-Ubuntu%2024.04-orange?style=flat-square)](.)
[![Encryption](https://img.shields.io/badge/Encryption-AES--256--GCM-red?style=flat-square)](.)
[![Compiled](https://img.shields.io/badge/Compiled-Nuitka%20%E2%80%94%20Native%20Binary-76b900?style=flat-square)](.)
[![Packaged](https://img.shields.io/badge/Packaged-makeself%20%E2%80%94%20Self--Extracting-555555?style=flat-square)](.)
[![License](https://img.shields.io/badge/License-MIT-lightgrey?style=flat-square)](./LICENSE)

**Single encrypted executable. Fully offline. No internet. One command.**

Bundles NVIDIA GPU Driver + CUDA Toolkit + DOCA networking stack  
into one self-contained binary for air-gapped ARM64 deployments.

> **PORTFOLIO PROJECT — Framework only.**  
> Required NVIDIA source files (`.run`, `.deb`) are proprietary, not included, and cannot be redistributed.  
> A working installer cannot be produced without a valid NVIDIA license.

</div>

---

## Demo

<div align="center">

![Demo](https://github.com/SmallNoraNeko/nvidia-golden-installer/releases/download/v1.0/demo.gif)

▶ *No internet. No browser extension. One command.*

</div>

---

## Why this is hard

Air-gapped ARM64 servers cannot reach the internet. Standard NVIDIA installers assume network access. This project solves:

| Problem | Solution |
|---------|----------|
| GPU driver is a 600 MB+ proprietary binary that cannot travel plaintext | AES-256-GCM encryption — key compiled into native binary, never on disk |
| Python scripts are readable and easily modified | Nuitka compiles to native aarch64 — no source extractable |
| Existing driver conflicts silently break new installs | **Dual-path uninstall**: auto-detects `.run` vs `apt/deb` install and takes the correct removal path — no manual intervention |
| CUDA reinstalls waste 20+ minutes and can fail midway | Version fingerprinting — auto-skip if identical version already present |
| Deployment artifacts left on target machine after install | Offline APT sources removed + installer self-deletes post-completion |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        makeself wrapper                         │
│  ┌────────────────────────────┐  ┌──────────────────────────┐  │
│  │     Nuitka native binary   │  │   CUDA Toolkit  (.run)   │  │
│  │  ┌──────────────────────┐  │  │   DOCA Network  (.deb)   │  │
│  │  │  GPU Driver payload  │  │  └──────────────────────────┘  │
│  │  │  AES-256-GCM enc.    │  │                                 │
│  │  │  Key: compiled-in    │  │  ┌──────────────────────────┐  │
│  │  └──────────────────────┘  │  │     install.sh           │  │
│  └────────────────────────────┘  │  (orchestrator)          │  │
│                                  └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

**Build pipeline:**

```
GPU .run ──▶ AES-256-GCM encrypt ──▶ Nuitka --onefile ──▶ native binary
                                                                  │
CUDA .run ─────────────────────────────────────────────▶ makeself pack ──▶ single executable
DOCA .deb ─────────────────────────────────────────────▶
install.sh ────────────────────────────────────────────▶
```

---

## Security layers

| Layer | Detail |
|-------|--------|
| GPU driver payload | AES-256-GCM encrypted at build time |
| Encryption key | Embedded via Nuitka — not stored as plaintext anywhere |
| Binary | Native aarch64 machine code — no Python source recoverable |
| CUDA / DOCA | Public packages — no encryption required |
| Post-install cleanup | Offline APT sources removed, installer self-deletes |

---

## What gets installed

```
Step 1/5  Detect & remove existing GPU driver   ← dual-path auto-detection
          │
          ├── Path A  (.run-based install detected)
          │     nvidia-uninstall --silent
          │     dkms remove all nvidia entries
          │     rm residuals: /var/lib/nvidia, libnvidia*.so
          │
          └── Path B  (apt/deb-based install detected)
                apt purge nvidia-* libnvidia-*
                dkms remove all nvidia entries
                rm residuals: /var/lib/nvidia, libnvidia*.so
          │
          └── (both paths) rmmod nvidia_drm nvidia_modeset nvidia_uvm nvidia

Step 2/5  Install GPU Driver
          └── Decrypt payload in memory → extract to tmpfs → run → wipe

Step 3/5  Install CUDA Toolkit
          └── Auto-skip if same version already present ✓

Step 4/5  Install DOCA networking stack

Step 5/5  Verify · cleanup · self-delete · reboot prompt
```

---

## Repository structure

```
.
├── build_golden.py       Build pipeline — encrypt, compile, package
├── Dockerfile.builder    Reproducible aarch64 build environment
├── USAGE.md              End-user installation guide (non-technical)
└── README.md
```

---

## Build

**Requirements (aarch64 machine):**

```bash
pip install cryptography nuitka --break-system-packages
sudo apt install -y makeself patchelf
```

**Source files (not included — obtain under valid NVIDIA license):**

```
NVIDIA-Linux-aarch64-<VERSION>.run
cuda_<VERSION>_linux_sbsa.run
doca-host_<VERSION>_arm64.deb
```

**Run:**

```bash
export GPU_RUN="NVIDIA-Linux-aarch64-<VERSION>.run"
export CUDA_RUN="cuda_<VERSION>_linux_sbsa.run"
export DOCA_DEB="doca-host_<VERSION>_arm64.deb"
export OUTPUT_NAME="nvidia-golden-aarch64"    # optional
export CUDA_SKIP_VERSION="13.0"               # optional

python3 build_golden.py
```

**Or with Docker (same aarch64 host required):**

```bash
docker build -f Dockerfile.builder -t golden-builder .

docker run --rm \
  -v $(pwd):/build \
  -e GPU_RUN="NVIDIA-Linux-aarch64-<VERSION>.run" \
  -e CUDA_RUN="cuda_<VERSION>_linux_sbsa.run" \
  -e DOCA_DEB="doca-host_<VERSION>_arm64.deb" \
  golden-builder
```

---

## Deploy (on target air-gapped machine)

```bash
chmod +x nvidia-golden-aarch64
sudo ./nvidia-golden-aarch64
```

See [USAGE.md](./USAGE.md) for the full end-user guide.

---

## License

MIT — framework only. NVIDIA software is subject to NVIDIA's own license terms.
