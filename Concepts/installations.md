# Docker Installation On Linux

Guide for installing **Docker Engine** (the standard daemon + CLI) on the three major Linux families: 
- [**Arch Linux**](#1-arch-linux-rolling-release--uses-official-repos)
- [**Ubuntu**](#2-ubuntu-debian-based) 
- [**Red Hat-based**](#3-red-hat-based-rhel-910-rocky-linux-910-almalinux-910-etc)

---

### 1. Arch Linux (rolling release – uses official repos)

Arch provides the latest Docker directly in its repositories — super simple.

```bash
# 1. Update system
sudo pacman -Syu

# 2. Install Docker (includes daemon, CLI, containerd, runc)
sudo pacman -S docker

# Optional but common: Docker Compose v2 plugin + buildx
sudo pacman -S docker-compose docker-buildx

# 3. Enable & start (use socket for lazy start / faster boot)
sudo systemctl enable --now docker.socket   # ← recommended for desktops
# OR full always-on:
# sudo systemctl enable --now docker.service

# 4. Add user to docker group (no sudo needed after relogin)
sudo usermod -aG docker $USER
# Log out & log back in (or run: newgrp docker)

# 5. Verify
docker version
docker run --rm hello-world
```
---

### 2. Ubuntu (Debian-based)

Use Docker's official repo for the newest stable version.

```bash
# 1. Update & install prerequisites
sudo apt update
sudo apt install -y ca-certificates curl gnupg

# 2. Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# 3. Add Docker repo
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 4. Install Docker Engine + plugins
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 5. Enable & start
sudo systemctl enable --now docker

# 6. Add user to group
sudo usermod -aG docker $USER
# Log out & back in

# Quick convenience alternative (one-liner for testing):
# curl -fsSL https://get.docker.com | sudo sh

# Verify
docker version
docker run --rm hello-world

```
---

### 3. Red Hat-based (RHEL 9/10, Rocky Linux 9/10, AlmaLinux 9/10, etc.)

Use Docker's RPM repo (works on RHEL clones too).

```bash
# 1. Remove any old/conflicting packages (e.g., podman-docker alias)
sudo dnf remove -y docker docker-client podman buildah || true

# 2. Install dnf plugins
sudo dnf -y install dnf-plugins-core

# 3. Add Docker repo
# Use 'rhel' for official RHEL; for Rocky/Alma/CentOS Stream it usually works too
sudo dnf config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo
# If issues on clones → try: https://download.docker.com/linux/centos/docker-ce.repo

# 4. Install Docker
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 5. Enable & start
sudo systemctl enable --now docker

# 6. Add user to group
sudo usermod -aG docker $USER
# Log out & back in

# Verify
docker version
docker run --rm hello-world
```

---

**Ready to containerize!** 

**Next: [Hands-on](../hands-on/)** 

---