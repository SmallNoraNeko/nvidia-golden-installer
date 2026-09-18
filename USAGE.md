# Usage Guide — Golden Triangle Offline Installer

> Plain-language guide. No Linux experience required.

---

## What is this file?

The installer is a **single executable file** (no extension).  
Running it automatically installs:

1. **GPU Driver** — lets the server recognize the GPU
2. **CUDA Toolkit** — lets the GPU run AI workloads
3. **DOCA Network Stack** — keeps high-speed networking working

After installation, the installer deletes itself.

---

## Requirements

| Item | Detail |
|------|--------|
| Platform | ARM64 server (aarch64) |
| OS | Ubuntu 24.04 |
| Login | root |
| Network | Not required — fully offline |
| What you need | Only the single installer file |

---

## How to install (on target machine)

### Step 1 — Copy the installer to the target machine

Use a USB drive or internal network transfer.  
Recommended location: `/root/`

### Step 2 — Give it execute permission

```bash
chmod +x /root/nvidia-golden-aarch64
```

### Step 3 — Run it

```bash
sudo /root/nvidia-golden-aarch64
```

Wait for it to finish. Do not close the terminal.  
Installation takes approximately **10–20 minutes**.

### Step 4 — Confirm success

When complete, you will see:

```
╔══════════════════════════════════════════════════════╗
║   Installation complete!  All checks passed. ✓      ║
╚══════════════════════════════════════════════════════╝
```

Type `yes` when asked to reboot, then press Enter.

### Step 5 — Verify after reboot

```bash
nvidia-smi
```

You should see a table showing GPU status and driver version.  
If this command works, the installation was successful. ✅

---

## What happens during installation

```
Step 1/5  Detect and remove old GPU driver
          → Works whether old driver was .run or apt installed
          → Does NOT touch networking drivers (DOCA/Mellanox)

Step 2/5  Install GPU Driver (encrypted — decrypts automatically)

Step 3/5  Install CUDA Toolkit
          → Auto-skips if the same version is already installed ✓

Step 4/5  Install DOCA networking stack

Step 5/5  Verify all components, clean up, prompt for reboot
```

---

## Troubleshooting

### Where are the install logs?

```
/var/log/golden-install-YYYYMMDD_HHMMSS.log
```

Send this file to your engineer if something goes wrong.

### Common questions

**Q: Installation seems stuck — what do I do?**  
Wait up to 30 minutes (CUDA takes time). Only escalate if nothing has changed for over 30 minutes.

**Q: I see `[WARN]` messages — is that bad?**  
No. `[WARN]` is informational. Only `[ERR]` requires attention.

**Q: CUDA was skipped — is that normal?**  
Yes. If the same CUDA version is already installed, the installer skips it automatically.

**Q: Will this affect my network card (InfiniBand / BlueField)?**  
No. The installer only touches GPU driver and CUDA. DOCA is updated separately.

**Q: The installer file is gone after installation — is that normal?**  
Yes. The installer deletes itself after a successful run.

---

## Build guide (for engineers)

See `README.md` for build instructions.
