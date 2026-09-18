#!/usr/bin/env python3
"""
Golden Triangle Offline Installer Builder v5.0
================================================================
AES-256-GCM encrypted, Nuitka-compiled, makeself-packaged
offline deployer for NVIDIA GPU Driver + CUDA + DOCA on ARM64.

Designed for air-gapped environments with no internet access.
Tested on NVIDIA GB-series platforms (aarch64 / Ubuntu 24.04).

Build machine requirements:
  - aarch64 (same platform as target)
  - Python 3.10+
  - pip install cryptography nuitka --break-system-packages
  - sudo apt install -y makeself patchelf

Usage:
  # Option A — environment variables (recommended for CI/CD)
  export GPU_RUN="NVIDIA-Linux-aarch64-<VERSION>.run"
  export CUDA_RUN="cuda_<VERSION>_linux_sbsa.run"
  export DOCA_DEB="doca-host_<VERSION>_arm64.deb"
  export OUTPUT_NAME="nvidia-golden-aarch64"   # optional
  export CUDA_SKIP_VERSION="13.0"              # optional
  python3 build_golden.py

  # Option B — edit the FALLBACK defaults below, then run
  python3 build_golden.py

Output:
  <OUTPUT_NAME>   (no file extension, single self-executing file)

On target machine:
  sudo ./<OUTPUT_NAME>
================================================================
"""

import os
import sys
import shutil
import secrets
import subprocess
import textwrap

# ── Config (env vars override fallback defaults) ──────────────
#
# Set these via environment variables so no version-specific
# information is hard-coded in this file.
#
GPU_RUN  = os.environ.get("GPU_RUN",  "NVIDIA-Linux-aarch64-<VERSION>.run")
CUDA_RUN = os.environ.get("CUDA_RUN", "cuda_<VERSION>_linux_sbsa.run")
DOCA_DEB = os.environ.get("DOCA_DEB", "doca-host_<VERSION>_arm64.deb")

# Output binary name (no extension)
OUTPUT_NAME = os.environ.get("OUTPUT_NAME", "nvidia-golden-aarch64")

# CUDA major.minor version string used to detect existing install
# e.g. "13.0"  →  skips CUDA if nvcc reports "release 13.0"
CUDA_SKIP_VERSION = os.environ.get("CUDA_SKIP_VERSION", "13.0")

GPU_INSTALL_FLAGS = [
    "--silent",
    "--accept-license",
    "--no-questions",
    "--dkms",
    "--kernel-module-type=open",
    "--no-install-libglvnd",
    "--no-opengl-files",
]

# Internal temp names
_GPU_PAYLOAD    = "_gpu_payload.enc"
_GPU_SRC        = "_gpu_installer_src.py"
_GPU_BIN        = "gpu_installer"
_PAYLOAD_DIR    = "_payload"
# ─────────────────────────────────────────────────────────────


def _banner(msg: str):
    print(f"\n{'═'*56}")
    print(f"  {msg}")
    print(f"{'═'*56}")


def check_build_env():
    _banner("Step 0/6  Checking build environment")
    ok = True

    py = sys.version_info
    if py >= (3, 10):
        print(f"  [✓] Python {py.major}.{py.minor}.{py.micro}")
    else:
        print(f"  [✗] Python {py.major}.{py.minor} — need 3.10+")
        ok = False

    arch = subprocess.check_output(["uname", "-m"], text=True).strip()
    if arch == "aarch64":
        print(f"  [✓] Architecture: {arch}")
    else:
        print(f"  [✗] Architecture: {arch} — must build on aarch64")
        ok = False

    try:
        import cryptography
        print(f"  [✓] cryptography {cryptography.__version__}")
    except Exception:
        print("  [✗] cryptography  →  pip install cryptography --break-system-packages")
        ok = False

    r = subprocess.run([sys.executable, "-m", "nuitka", "--version"],
                       capture_output=True, text=True)
    if r.returncode == 0:
        print(f"  [✓] nuitka {r.stdout.strip().splitlines()[0]}")
    else:
        print("  [✗] nuitka  →  pip install nuitka --break-system-packages")
        ok = False

    for tool in ["makeself", "patchelf"]:
        if shutil.which(tool):
            print(f"  [✓] {tool}")
        else:
            print(f"  [✗] {tool}  →  sudo apt install -y {tool}")
            ok = False

    for fname in [GPU_RUN, CUDA_RUN, DOCA_DEB]:
        if os.path.exists(fname):
            mb = os.path.getsize(fname) // 1024 // 1024
            print(f"  [✓] {fname}  ({mb} MB)")
        else:
            print(f"  [✗] {fname}  — not found")
            ok = False

    stat = shutil.disk_usage(".")
    free_gb = stat.free / 1024 ** 3
    sym = "✓" if free_gb >= 15 else "!"
    print(f"  [{sym}] Disk free: {free_gb:.1f} GB  (recommend ≥ 15 GB)")

    if not ok:
        print("\n  Fix the [✗] items above and re-run.\n")
        sys.exit(1)


def encrypt_gpu_payload() -> tuple[str, str]:
    """AES-256-GCM encrypt the GPU .run file. Returns (key_hex, nonce_hex)."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    _banner("Step 1/6  Encrypting GPU driver payload")

    print(f"  Reading  : {GPU_RUN}")
    with open(GPU_RUN, "rb") as f:
        raw = f.read()
    print(f"  Size     : {len(raw):,} bytes ({len(raw)//1024//1024} MB)")

    key   = secrets.token_bytes(32)
    nonce = secrets.token_bytes(12)
    enc   = AESGCM(key).encrypt(nonce, raw, None)
    del raw

    with open(_GPU_PAYLOAD, "wb") as f:
        f.write(enc)
    print(f"  Encrypted: {_GPU_PAYLOAD}  ({len(enc)//1024//1024} MB)")

    return key.hex(), nonce.hex()


def generate_gpu_installer_src(key_hex: str, nonce_hex: str):
    """Generate the gpu_installer Python source with AES key embedded."""
    _banner("Step 2/6  Generating gpu_installer source")

    flags_repr = repr(GPU_INSTALL_FLAGS)

    src = textwrap.dedent(f'''\
        #!/usr/bin/env python3
        # -*- coding: utf-8 -*-
        """
        GPU Driver Decryptor + Installer
        AES-256-GCM key is compiled into this binary via Nuitka.
        """
        import os, sys, stat, secrets, tempfile, subprocess
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        _K = bytes.fromhex("{key_hex}")
        _N = bytes.fromhex("{nonce_hex}")
        _F = {flags_repr}
        _P = "{_GPU_PAYLOAD}"

        def _find_payload():
            for base in [
                os.path.dirname(os.path.abspath(sys.argv[0])),
                os.path.dirname(os.path.abspath(__file__)),
                os.getcwd(),
            ]:
                p = os.path.join(base, _P)
                if os.path.isfile(p):
                    return p
            return None

        def main():
            if os.geteuid() != 0:
                sys.exit("[!] gpu_installer must be run as root")

            path = _find_payload()
            if not path:
                sys.exit(f"[!] Encrypted payload not found: {{_P}}")

            print("[*] Decrypting GPU driver payload ...")
            with open(path, "rb") as f:
                enc = f.read()

            try:
                raw = AESGCM(_K).decrypt(_N, enc, None)
            except Exception:
                sys.exit("[!] Decryption failed — file may be tampered")
            del enc

            tmp_dir  = tempfile.mkdtemp(prefix=".gpu_")
            tmp_exec = os.path.join(tmp_dir, secrets.token_hex(10))
            try:
                with open(tmp_exec, "wb") as f:
                    f.write(raw)
                del raw
                os.chmod(tmp_exec, stat.S_IRWXU)

                print("[*] Running NVIDIA GPU driver installer ...")
                print("    (This may take 3-10 minutes for kernel module compilation)")
                ret = subprocess.run([tmp_exec] + _F).returncode
            finally:
                try: os.unlink(tmp_exec)
                except Exception: pass
                try: os.rmdir(tmp_dir)
                except Exception: pass

            if ret != 0:
                sys.exit(
                    f"[!] GPU driver installation failed (exit {{ret}})\\n"
                    f"    Log: /var/log/nvidia-installer.log"
                )
            print("[+] GPU driver installed successfully.")
            sys.exit(0)

        if __name__ == "__main__":
            main()
    ''')

    with open(_GPU_SRC, "w", encoding="utf-8") as f:
        f.write(src)
    print(f"  Generated: {_GPU_SRC}")


def compile_gpu_installer():
    """Compile gpu_installer with Nuitka (onefile, encrypted payload embedded)."""
    _banner("Step 3/6  Compiling gpu_installer with Nuitka")

    cmd = [
        sys.executable, "-m", "nuitka",
        "--onefile",
        f"--output-filename={_GPU_BIN}",
        f"--include-data-files={_GPU_PAYLOAD}={_GPU_PAYLOAD}",
        "--include-module=_cffi_backend",
        "--remove-output",
        "--assume-yes-for-downloads",
        _GPU_SRC,
    ]

    print(f"  Command: {' '.join(cmd)}\n")
    result = subprocess.run(cmd)

    for f in [_GPU_SRC]:
        try: os.unlink(f)
        except Exception: pass

    if result.returncode != 0:
        sys.exit("[!] Nuitka compilation failed.")

    size = os.path.getsize(_GPU_BIN)
    print(f"  Output : {_GPU_BIN}  ({size//1024//1024} MB)")


def prepare_payload_dir():
    """Assemble payload directory with all components."""
    _banner("Step 4/6  Assembling payload directory")

    if os.path.exists(_PAYLOAD_DIR):
        shutil.rmtree(_PAYLOAD_DIR)
    os.makedirs(_PAYLOAD_DIR)

    # gpu_installer binary (contains encrypted GPU .run)
    shutil.copy2(_GPU_BIN, os.path.join(_PAYLOAD_DIR, _GPU_BIN))
    os.chmod(os.path.join(_PAYLOAD_DIR, _GPU_BIN), 0o755)
    print(f"  [✓] {_GPU_BIN}  (encrypted GPU driver)")

    # _gpu_payload.enc — needed by gpu_installer at runtime
    # Note: Nuitka onefile embeds it, so we also keep it beside binary for redundancy
    shutil.copy2(_GPU_PAYLOAD, os.path.join(_PAYLOAD_DIR, _GPU_PAYLOAD))
    print(f"  [✓] {_GPU_PAYLOAD}  (AES-256-GCM encrypted payload)")

    # CUDA installer (plain — publicly available download)
    shutil.copy2(CUDA_RUN, os.path.join(_PAYLOAD_DIR, CUDA_RUN))
    mb = os.path.getsize(CUDA_RUN) // 1024 // 1024
    print(f"  [✓] {CUDA_RUN}  ({mb} MB)")

    # DOCA local-repo deb (plain — publicly available)
    shutil.copy2(DOCA_DEB, os.path.join(_PAYLOAD_DIR, DOCA_DEB))
    mb = os.path.getsize(DOCA_DEB) // 1024 // 1024
    print(f"  [✓] {DOCA_DEB}  ({mb} MB)")


def generate_install_sh():
    """Generate the main install.sh inside the payload directory."""
    _banner("Step 5/6  Generating install.sh")

    # Use raw string to avoid Python f-string collision with bash ${...}
    script = r"""#!/bin/bash
# =============================================================
# Golden Triangle Auto-Installer v5.0
# GPU Driver 580.167.08 + CUDA 13.0.2 + DOCA 3.2.1
# Platform: GB300 / aarch64 / Ubuntu 24.04
# Auto-generated — do not edit manually
# =============================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

log_info()  { echo -e "${CYAN}[INFO]${RESET}  $*"; }
log_ok()    { echo -e "${GREEN}[ OK ]${RESET}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
log_error() { echo -e "${RED}[ERR ]${RESET}  $*" >&2; }
log_step()  { echo -e "\n${BOLD}${CYAN}══  $*  ══${RESET}"; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="/var/log/golden-install-$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1

trap_error() {
    local code=$? line=${BASH_LINENO[0]}
    log_error "Failed at line ${line} (exit ${code})"
    log_error "Full log: ${LOG_FILE}"
    exit "$code"
}
trap trap_error ERR

# ── Banner ────────────────────────────────────────────────────
echo -e "${BOLD}"
echo "  ╔══════════════════════════════════════════════════════╗"
echo "  ║    Golden Triangle Installer v5.0  (aarch64)        ║"
echo "  ║    GPU Driver + CUDA + DOCA  — Offline Installer    ║"
echo "  ╚══════════════════════════════════════════════════════╝"
echo -e "${RESET}"

# ── Root check ────────────────────────────────────────────────
if [ "$(id -u)" -ne 0 ]; then
    log_error "Must be run as root:  sudo ./nvidia-golden-gb300-sbsa"  # replaced at build time
    exit 1
fi

# =============================================================
log_step "Step 1/5  Detect & remove existing NVIDIA driver"
# =============================================================

REMOVED_SOMETHING=false

# ── Path A: previous .run installation ───────────────────────
if command -v nvidia-uninstall &>/dev/null; then
    log_info "Detected .run-based installation → running nvidia-uninstall ..."
    nvidia-uninstall --silent 2>/dev/null || true
    REMOVED_SOMETHING=true
    log_ok ".run driver uninstalled"
fi

# ── Path B: previous apt/deb installation ────────────────────
NVIDIA_APT_PKGS=$(dpkg -l 2>/dev/null | grep -E "^ii.*nvidia" | awk '{print $2}' || true)
if [ -n "$NVIDIA_APT_PKGS" ]; then
    log_info "Detected deb-based installation → running apt purge ..."

    # Detect old major version number (e.g. 580, 535)
    OLD_VER=$(echo "$NVIDIA_APT_PKGS" | grep -oP 'nvidia[^0-9]*\K[0-9]{3,}' \
              | sort -rn | head -n1 || echo "")

    if [ -n "$OLD_VER" ]; then
        log_info "Old major version: ${OLD_VER}"
        DEBIAN_FRONTEND=noninteractive apt-get purge -y \
            "nvidia-driver-${OLD_VER}-open" \
            "nvidia-driver-${OLD_VER}" \
            "nvidia-dkms-${OLD_VER}-open" \
            "nvidia-kernel-source-${OLD_VER}-open" \
            "nvidia-kernel-common-${OLD_VER}" \
            "libnvidia-compute-${OLD_VER}" \
            "libnvidia-encode-${OLD_VER}" \
            "libnvidia-decode-${OLD_VER}" \
            "libnvidia-extra-${OLD_VER}" \
            "libnvidia-gl-${OLD_VER}" \
            "libnvidia-cfg1-${OLD_VER}" \
            "nvidia-utils-${OLD_VER}" \
            "xserver-xorg-video-nvidia-${OLD_VER}" \
            "nvidia-settings" \
            2>/dev/null || true
    fi

    # Remove local repo packages
    OLD_REPO=$(dpkg -l 2>/dev/null | grep "nvidia-driver-local-repo" | awk '{print $2}' || true)
    if [ -n "$OLD_REPO" ]; then
        DEBIAN_FRONTEND=noninteractive apt-get purge -y $OLD_REPO 2>/dev/null || true
        rm -f /etc/apt/sources.list.d/nvidia-driver-local*.list 2>/dev/null || true
        rm -f /usr/share/keyrings/nvidia-driver-local-*.gpg 2>/dev/null || true
    fi

    DEBIAN_FRONTEND=noninteractive apt-get autoremove --purge -y 2>/dev/null || true

    # Clear rc-state residuals
    RC_PKGS=$(dpkg -l 2>/dev/null | grep '^rc' | grep -i nvidia | awk '{print $2}' || true)
    [ -n "$RC_PKGS" ] && echo "$RC_PKGS" | xargs dpkg --purge 2>/dev/null || true

    REMOVED_SOMETHING=true
    log_ok "deb driver packages removed"
fi

# ── DKMS cleanup ─────────────────────────────────────────────
if command -v dkms &>/dev/null; then
    DKMS_NVIDIA=$(dkms status 2>/dev/null | grep -i "^nvidia" || true)
    if [ -n "$DKMS_NVIDIA" ]; then
        log_info "Removing DKMS NVIDIA entries ..."
        echo "$DKMS_NVIDIA" | while IFS=',' read -r modver _rest; do
            MODULE=$(echo "$modver" | awk -F'/' '{print $1}' | xargs)
            VERSION=$(echo "$modver" | awk -F'/' '{print $2}' | xargs)
            dkms remove -m "$MODULE" -v "$VERSION" --all 2>/dev/null \
                && log_ok "DKMS removed: ${MODULE}/${VERSION}" \
                || log_warn "DKMS remove skipped: ${MODULE}/${VERSION}"
        done
    fi
fi

# ── Residual cleanup (common to both paths) ───────────────────
rm -f /etc/modprobe.d/blacklist-nouveau.conf 2>/dev/null || true
rm -rf /var/lib/nvidia/ 2>/dev/null || true
rm -f /usr/lib/aarch64-linux-gnu/libnvidia* 2>/dev/null || true
rm -f /usr/lib/aarch64-linux-gnu/libGL*nvidia* 2>/dev/null || true

# Unload nvidia kernel module if loaded
rmmod nvidia_drm  2>/dev/null || true
rmmod nvidia_modeset 2>/dev/null || true
rmmod nvidia_uvm  2>/dev/null || true
rmmod nvidia      2>/dev/null || true

if [ "$REMOVED_SOMETHING" = true ]; then
    log_info "Updating initramfs after driver removal ..."
    update-initramfs -u 2>/dev/null || log_warn "update-initramfs had warnings (non-blocking)"
    log_ok "Old driver fully removed"
else
    log_ok "No existing NVIDIA driver found — clean system"
fi

# =============================================================
log_step "Step 2/5  Install GPU Driver 580.167.08"
# =============================================================

GPU_INSTALLER="${SCRIPT_DIR}/gpu_installer"
if [ ! -x "$GPU_INSTALLER" ]; then
    log_error "gpu_installer binary not found in: ${SCRIPT_DIR}"
    exit 1
fi

log_info "Launching encrypted GPU driver installer ..."
"$GPU_INSTALLER"
log_ok "GPU Driver 580.167.08 installed"

# =============================================================
log_step "Step 3/5  CUDA 13.0.2 (auto-skip if already installed)"
# =============================================================

CUDA_SKIP=false

# Check 1: nvcc version
if command -v nvcc &>/dev/null; then
    NVCC_VER=$(nvcc --version 2>/dev/null | grep -oP "release \K[0-9]+\.[0-9]+" || echo "")
    if [ "$NVCC_VER" = "CUDA_SKIP_VERSION_PLACEHOLDER" ]; then
        CUDA_SKIP=true
        log_ok "CUDA 13.0 already installed (nvcc confirms) — skipping ✓"
    fi
fi

# Check 2: directory exists
if [ "$CUDA_SKIP" = false ] && [ -d "/usr/local/cuda-13.0" ]; then
    CUDA_SKIP=true
    log_ok "CUDA 13.0 already installed (/usr/local/cuda-13.0 exists) — skipping ✓"
fi

if [ "$CUDA_SKIP" = false ]; then
    CUDA_INSTALLER=$(ls "${SCRIPT_DIR}"/cuda_*.run 2>/dev/null | head -n1 || true)
    if [ -z "$CUDA_INSTALLER" ]; then
        log_error "CUDA .run installer not found in payload."
        exit 1
    fi

    chmod +x "$CUDA_INSTALLER"
    log_info "Installing CUDA Toolkit (this takes 3-5 minutes) ..."
    "$CUDA_INSTALLER" --silent --toolkit 2>&1 | tee -a "$LOG_FILE"

    if command -v nvcc &>/dev/null || [ -d "/usr/local/cuda-${_CUDA_VER}" ]; then
        log_ok "CUDA ${_CUDA_VER} installed"
    else
        log_error "nvcc not found after CUDA install — check ${LOG_FILE}"
        exit 1
    fi

    # Write global env vars
    CUDA_DIR=$(ls -d /usr/local/cuda-${_CUDA_VER%.*}* 2>/dev/null | head -n1 || echo "/usr/local/cuda")
    cat > /etc/profile.d/cuda_env.sh << ENV_EOF
# CUDA Environment — auto-generated by Golden Triangle Installer v5.0
export PATH=\$PATH:${CUDA_DIR}/bin
export LD_LIBRARY_PATH=\$LD_LIBRARY_PATH:${CUDA_DIR}/lib64
ENV_EOF
    chmod 644 /etc/profile.d/cuda_env.sh
    log_ok "CUDA environment variables written to /etc/profile.d/cuda_env.sh"
fi

# =============================================================
log_step "Step 4/5  DOCA 3.2.1"
# =============================================================

DOCA_DEB_FILE=$(ls "${SCRIPT_DIR}"/doca-host_*.deb 2>/dev/null | head -n1 || true)
if [ -z "$DOCA_DEB_FILE" ]; then
    log_error "DOCA .deb not found in payload."
    exit 1
fi

log_info "Installing DOCA local repo package ..."
dpkg -i "$DOCA_DEB_FILE"

# Copy GPG key
DOCA_KEY=$(find /var/doca-host-repo-* /var/doca-repo-* -name "*.gpg" 2>/dev/null | head -n1 || true)
if [ -n "$DOCA_KEY" ]; then
    cp "$DOCA_KEY" /usr/share/keyrings/
    log_ok "DOCA GPG key installed"
fi

# Set up sources.list for local repo
DOCA_REPO_DIR=$(ls -d /var/doca-host-repo-* /var/doca-repo-* 2>/dev/null | head -n1 || true)
if [ -n "$DOCA_REPO_DIR" ]; then
    echo "deb [trusted=yes] file:${DOCA_REPO_DIR} ./" \
        > /etc/apt/sources.list.d/doca-offline.list
fi

log_info "Updating package index (offline — Ign messages are normal) ..."
apt-get update \
    -o Dir::Etc::sourcelist="sources.list.d/doca-offline.list" \
    -o Dir::Etc::sourceparts="-" \
    -o APT::Get::List-Cleanup="0" 2>&1 \
    | grep -v "^Ign:" | grep -v "^W:.*Failed" | grep -v "^W:.*Some" \
    | tee -a "$LOG_FILE" || true

log_info "Installing DOCA packages ..."
DEBIAN_FRONTEND=noninteractive apt-get install -y \
    --allow-unauthenticated \
    --allow-downgrades \
    --no-install-recommends \
    doca-host doca-all 2>&1 | tee -a "$LOG_FILE"

if dpkg -l doca-host 2>/dev/null | grep -q "^ii"; then
    DOCA_VER=$(dpkg -l doca-host | grep "^ii" | awk '{print $3}')
    log_ok "DOCA installed: ${DOCA_VER}"
else
    log_error "DOCA install failed — check ${LOG_FILE}"
    exit 1
fi

# =============================================================
log_step "Step 5/5  Verification & Finalization"
# =============================================================

PASS=true

echo ""
echo -e "▶ [1/4] GPU Driver package"
if dpkg -l 2>/dev/null | grep -qE "^ii.*nvidia.*(open|driver|dkms)"; then
    GPU_PKG=$(dpkg -l 2>/dev/null | grep -E "^ii.*nvidia.*(open|dkms)" | awk '{print $2" "$3}' | head -n1)
    log_ok "GPU packages installed: ${GPU_PKG}"
else
    log_warn "GPU packages not visible via dpkg (installed via .run — expected)"
    # Still check if nvidia-smi binary exists
    if [ -f "/usr/bin/nvidia-smi" ]; then
        log_ok "/usr/bin/nvidia-smi present ✓"
    else
        log_warn "nvidia-smi not found — will be available after reboot"
    fi
fi

echo ""
echo -e "▶ [2/4] DKMS NVIDIA module"
if command -v dkms &>/dev/null; then
    DKMS_NVIDIA=$(dkms status 2>/dev/null | grep -i "^nvidia" || true)
    if [ -n "$DKMS_NVIDIA" ]; then
        echo "$DKMS_NVIDIA"
        if echo "$DKMS_NVIDIA" | grep -q "installed"; then
            log_ok "DKMS module compiled and installed ✓"
        else
            log_warn "DKMS module registered (will compile on reboot)"
        fi
    else
        log_warn "NVIDIA not in DKMS — module will load on reboot"
    fi
fi

echo ""
echo -e "▶ [3/4] CUDA"
export PATH=$PATH:/usr/local/cuda-${_CUDA_VER}/bin:/usr/local/cuda/bin
if command -v nvcc &>/dev/null; then
    NVCC_V=$(nvcc --version 2>/dev/null | grep "release" | head -n1)
    log_ok "${NVCC_V}"
else
    log_warn "nvcc not in PATH yet (will be after reboot + source /etc/profile.d/cuda_env.sh)"
fi

echo ""
echo -e "▶ [4/4] DOCA"
if dpkg -l doca-host 2>/dev/null | grep -q "^ii"; then
    log_ok "doca-host $(dpkg -l doca-host | grep '^ii' | awk '{print $3}')"
else
    log_error "doca-host not installed"; PASS=false
fi

echo ""
log_info "Updating initramfs for new driver modules ..."
update-initramfs -u 2>/dev/null || log_warn "update-initramfs had warnings"

# ── 清除離線 APT source（防止之後 apt update 跳錯）──────────────
rm -f /etc/apt/sources.list.d/doca-offline.list 2>/dev/null || true
rm -f /etc/apt/sources.list.d/nvidia-unified-offline.list 2>/dev/null || true
rm -f /etc/apt/sources.list.d/nvidia-driver-local*.list 2>/dev/null || true
log_ok "Offline APT sources removed"

# ── Self-delete ───────────────────────────────────────────────
log_info "Removing installer files ..."
# Try to delete the original makeself archive
for _candidate in "${MAKESELF_ARCHIVE:-}" "${ARCHIVE:-}" "${MAKESELF_SELF:-}"; do
    if [ -n "$_candidate" ] && [ -f "$_candidate" ]; then
        rm -f "$_candidate" && log_ok "Installer deleted: ${_candidate}" && break
    fi
done

# ── Final result ─────────────────────────────────────────────
echo ""
if [ "$PASS" = true ]; then
    echo -e "${GREEN}${BOLD}"
    echo "  ╔══════════════════════════════════════════════════════╗"
    echo "  ║   Installation complete!  All checks passed. ✓      ║"
    echo "  ║                                                      ║"
    echo "  ║   Full log: ${LOG_FILE}"
    echo "  ║                                                      ║"
    echo "  ║   ⚠  Reboot required to load the GPU driver.        ║"
    echo "  ║   After reboot verify with:  nvidia-smi             ║"
    echo "  ╚══════════════════════════════════════════════════════╝"
    echo -e "${RESET}"

    echo -e "${YELLOW}${BOLD}"
    echo "  ┌──────────────────────────────────────────────────┐"
    echo "  │  Reboot now?  (yes = reboot in 5s / no = later) │"
    echo "  └──────────────────────────────────────────────────┘"
    echo -e "${RESET}"
    read -r -p "  Your choice [yes/no]: " _CHOICE
    if [[ "${_CHOICE,,}" == "yes" ]]; then
        log_info "Rebooting in 5 seconds ... (Ctrl+C to cancel)"
        sleep 5
        reboot
    else
        echo ""
        echo -e "${CYAN}${BOLD}  ▶ Reboot manually when ready:${RESET}  sudo reboot"
        echo ""
    fi
else
    echo -e "${RED}${BOLD}"
    echo "  ╔══════════════════════════════════════════════════════╗"
    echo "  ║   Installation finished but some checks FAILED.     ║"
    echo "  ║   Do NOT reboot. Check: ${LOG_FILE}"
    echo "  ╚══════════════════════════════════════════════════════╝"
    echo -e "${RESET}"
    exit 1
fi
"""

    # Inject runtime config values into the shell script placeholders
    script = script.replace("CUDA_SKIP_VERSION_PLACEHOLDER", CUDA_SKIP_VERSION)
    script = script.replace("nvidia-golden-gb300-sbsa", OUTPUT_NAME)

    install_path = os.path.join(_PAYLOAD_DIR, "install.sh")
    with open(install_path, "w", encoding="utf-8") as f:
        f.write(script)
    os.chmod(install_path, 0o755)
    print(f"  Generated: {install_path}")


def makeself_package():
    """Pack everything into a single self-executing file via makeself."""
    _banner("Step 6/6  Packaging with makeself")

    cmd = [
        "makeself",
        "--needroot",
        "--sha256",
        f"./{_PAYLOAD_DIR}",
        OUTPUT_NAME,
        f"NVIDIA Golden Triangle Installer v5.0 — {OUTPUT_NAME}",
        "./install.sh",
    ]

    print(f"  Command: {' '.join(cmd)}\n")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        sys.exit("[!] makeself packaging failed.")

    # Make executable (makeself should already do this, but ensure)
    os.chmod(OUTPUT_NAME, 0o755)

    size = os.path.getsize(OUTPUT_NAME)
    print(f"\n  Output   : {OUTPUT_NAME}")
    print(f"  Size     : {size:,} bytes  ({size//1024//1024} MB)")


def cleanup():
    """Remove intermediate build artifacts."""
    for f in [_GPU_PAYLOAD, _GPU_BIN]:
        try: os.unlink(f)
        except Exception: pass
    try: shutil.rmtree(_PAYLOAD_DIR)
    except Exception: pass


def main():
    print()
    print("  ╔══════════════════════════════════════════════════════╗")
    print("  ║   Golden Triangle Offline Installer Builder v5.0    ║")
    print(f"  ║   GPU: {GPU_RUN:<45}║")
    print(f"  ║   CUDA: {CUDA_RUN:<44}║")
    print(f"  ║   DOCA: {DOCA_DEB:<44}║")
    print("  ╚══════════════════════════════════════════════════════╝")

    check_build_env()
    key_hex, nonce_hex = encrypt_gpu_payload()
    generate_gpu_installer_src(key_hex, nonce_hex)
    compile_gpu_installer()
    prepare_payload_dir()
    generate_install_sh()
    makeself_package()
    cleanup()

    _banner("Build complete")
    print(f"  File     : {OUTPUT_NAME}")
    print(f"  Deploy to target machine (aarch64) and run:")
    print(f"    sudo ./{OUTPUT_NAME}")
    print()


if __name__ == "__main__":
    main()
