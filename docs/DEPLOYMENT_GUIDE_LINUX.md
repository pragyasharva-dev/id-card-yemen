# 🚀 Linux Deployment Guide (Ubuntu)

This guide explains how to deploy the authenticated e-KYC system on a Linux Ubuntu server using Docker.

## Prerequisites
*   **Ubuntu Server** (20.04 or 22.04 recommended)
*   **Docker** & **Docker Compose** installed
*   **Git** (optional, if cloning)
*   **Python 3** (optional, only if running download script on host)

## 1. Transfer Code
Copy your project files to the Linux VM. You can use `scp`, `rsync`, or Git.

```bash
# Example using SCP from your local machine
scp -r id-card-yemen/ user@your-vm-ip:~/id-card-yemen
```

## 2. Install Docker (If not installed)
Run these commands on the backend Ubuntu server:

```bash
# Add Docker's official GPG key:
sudo apt-get update
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update

# Install Docker packages
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

## 3. Prepare Offline Models
The e-KYC system requires AI models (`paddleocr`, `insightface`). Since the container is designed to run offline, you must prepare the `models/` folder.

### Option A: Download on Host (Recommended)
If you have Python installed on the VM:
```bash
cd ~/id-card-yemen

# Create a venv to install dependencies for the downloader
python3 -m venv venv
source venv/bin/activate
pip install . # Installs requirements from pyproject.toml

# Run the download script
python scripts/download_models.py
```

### Option B: Download inside Docker (One-off)
If you don't want to install Python on the host:
```bash
# Use the app image to download models to the mounted volume
docker run --rm -v $(pwd)/models:/app/models -v $(pwd)/scripts:/app/scripts -w /app ekyc-api:latest python scripts/download_models.py
```
*(Note: You need to build the image first for Option B: `docker compose build`)*

## 4. Run the Service
Use Docker Compose to start the API.

```bash
cd ~/id-card-yemen
docker compose up -d --build
```

### 5. Verify Deployment
Check if the service is running:

```bash
# Check logs
docker compose logs -f

# Check health endpoint
curl http://localhost:8000/health
# Expected: {"status":"healthy", ...}
```

## 6. Offline Mode Verification
To simulate a true offline environment (offline requirement):
1.  Disconnect internet access or block egress traffic.
2.  Restart the container: `docker compose restart`
3.  Send a `/verify` request. The system should still work because it loads models from `/app/models`.
