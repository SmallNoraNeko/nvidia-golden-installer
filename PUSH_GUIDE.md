# GitHub Push Guide

How to push this repository from your Intel NUC (via USB transfer from the build machine).

---

## Step 1 — Prepare files on USB

Copy the following folder to a USB drive from your build machine:

```
github_repo/
├── build_golden.py
├── Dockerfile.builder
├── README.md
├── USAGE.md
├── PUSH_GUIDE.md
└── .gitignore
```

Also copy your demo video to the USB:
```
No Internet_No Extension_One Command.mp4
```

**Do NOT copy:** `.run`, `.deb`, `_payload/`, `gpu_installer`, `nvidia-golden-*`

---

## Step 2 — On the Intel NUC, create GitHub repo

1. Go to https://github.com/new
2. Repository name: `nvidia-golden-installer` (or your preferred name)
3. Set to **Public**
4. Do NOT initialize with README (you're pushing your own)
5. Click **Create repository**
6. Copy the repo URL shown (e.g. `https://github.com/yourname/nvidia-golden-installer.git`)

---

## Step 3 — Push from NUC terminal

```bash
# Go to the folder you copied from USB
cd /path/to/github_repo

# Initialize git
git init
git add .
git commit -m "Initial commit: Golden Triangle offline installer framework"

# Add your GitHub repo as remote
git remote add origin https://github.com/yourname/nvidia-golden-installer.git

# Push
git branch -M main
git push -u origin main
```

If prompted for credentials: use your GitHub username + a Personal Access Token  
(GitHub no longer accepts passwords — generate one at https://github.com/settings/tokens)

---

## Step 4 — Upload the demo video

GitHub does not render local video files in README automatically.  
You need to upload the video through the GitHub web interface:

1. Open your repository on GitHub
2. Go to any **Issue** → click **New Issue** (don't worry, you won't submit it)
3. Drag and drop `No Internet_No Extension_One Command.mp4` into the text box
4. Wait for upload to complete — GitHub generates a URL like:
   ```
   https://github.com/user-attachments/assets/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
   ```
5. Copy that URL
6. Edit `README.md` — replace `REPLACE_WITH_YOUR_VIDEO_ASSET_ID` with the actual asset ID from the URL
7. Commit the change:
   ```bash
   git add README.md
   git commit -m "Add demo video to README"
   git push
   ```
8. Close the Issue without submitting

---

## Result

Your README will display the video inline, visible to anyone who visits the repo.  
The code is public, but without the NVIDIA source files it cannot produce a working installer.
