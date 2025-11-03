# 2. Secure Docker Environment Setup

## Concepts

All applications are run as containers using Docker Engine.

- **User Namespace Remapping (`userns-remap`):** It maps the `root` user (UID 0) inside a container to a high-numbered, unprivileged user on the VM host (e.g., UID 100000). This means that even if an attacker gains `root` inside a container, they are just a regular, powerless user on the host, preventing a container breakout from escalating to a full system compromise. For further information, the official docs can be found [here](https://docs.docker.com/engine/security/userns-remap/).
- **Log Rotation:** The Docker daemon is configured to use the `local` logging driver with size and file limits. This prevents container logs from growing indefinitely and consuming all available disk space.

## Setup Guide

### 1 Install Docker Engine

First, you must install the Docker Engine. Follow the official Docker documentation to add Docker's repository and install the latest version of `docker-ce`.

  - [Install Docker Engine on Debian](https://docs.docker.com/engine/install/debian/)
  - [Official Docker userns-remap guide](https://docs.docker.com/engine/security/userns-remap/)

### 2 Create the Subordinate User

Next, create the dedicated, unprivileged host user that will "own" the container processes. This user is for system use only.

```bash
# Creates a system user named 'dockeruser' with no home directory
sudo useradd --system --no-create-home dockeruser
```

### 3 Define Subordinate ID Ranges

Now, you must grant the `dockeruser` a large range of User IDs (UIDs) and Group IDs (GIDs) that it's allowed to manage for the container namespaces.

```bash
# Grant dockeruser 65,536 UIDs starting from 100000
echo "dockeruser:100000:65536" | sudo tee /etc/subuid

# Grant dockeruser 65,536 GIDs starting from 100000
echo "dockeruser:100000:65536" | sudo tee /etc/subgid
```

### 4 Configure the Docker Daemon

Create or edit the Docker daemon's configuration file at `/etc/docker/daemon.json`. This is where you will officially enable `userns-remap` and set up the logging driver.

```bash
sudo nano /etc/docker/daemon.json
```

Add the following JSON content. This tells Docker to use the `dockeruser` for remapping and to enforce log rotation on all containers.

```json
{
  "userns-remap": "dockeruser",
  "log-driver": "local",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

  - `"max-size": "10m"`: Each log file will be capped at 10MB.
  - `"max-file": "3"`: Docker will keep a maximum of 3 log files per container.

### 5 Restart and Verify

Apply the new configuration by restarting the Docker service.

```bash
sudo systemctl restart docker
```

You can now verify that both settings are active.

  - **Verify `userns-remap`:**

    1. Run a test container: `docker run -d --name test-remap alpine top`
    2. On the **host VM**, find the container's process and check its owner. The owner should be `100000` (or `dockeruser`), **not** `root`.
        ```bash
        ps aux | grep top
        ```
        **Result:** `100000   12345  0.0  0.0   2868   180 ?    Ssl  12:30   0:00 top`
    3. Clean up: `docker rm -f test-remap`

  - **Verify Logging Driver:**

      - Run `docker info` and look for the logging settings.
        ```bash
        docker info | grep -A 3 "Logging Driver"
        ```
        **Result:**
        ```
        Logging Driver: local
         ...
         Log Options:
          max-file: 3
          max-size: 10m
        ```
