# Host Layer: macOS with VMware Fusion

This document details the setup of the physical host machine, which serves as the foundation for the entire Homelab. The goal of this layer is to create a stable, secure, and isolated environment for running virtual machines.

The chosen stack is:
- **Host OS:** macOS
- **Virtualization:** VMware Fusion
- **Storage:** Two dedicated, encrypted external SSD

![Host Architecture](../_assets/host_architecture.svg)

## Core Security Principles

Two key principles are enforced at this layer to enhance security:

### Principle 1: Isolate the Virtualization Process

Virtualization software is complex and, like any software, can have vulnerabilities. To mitigate the risk of a potential VM escape (where a process breaks out of the guest VM and gains access to the host), we run VMware Fusion under a **dedicated, non-administrator user account** on macOS.

This ensures that even in a worst-case scenario, an attacker would be confined to an unprivileged user account on the host, severely limiting their ability to access sensitive host data or gain administrative control.

### Principle 2: Encrypt Data at Rest

All virtual machine files—including virtual disks (`.vmdk`), snapshots, and configuration files—are stored on a dedicated external SSD. This entire drive is encrypted at the host level using macOS's built-in APFS encryption.

This guarantees that if the physical drive is ever lost or stolen, the data remains completely inaccessible.# 1. Host Preparation and Setup

This section covers the foundational steps required to prepare the macOS host machine. The focus is on establishing a secure and isolated environment for the virtualization software and ensuring all virtual machine data is encrypted at rest.

## Isolate the Virtualization Process

For security, the virtualization software (VMware Fusion) should not be run under an administrator account. By creating a dedicated **standard (non-administrator) user** solely for running VMs, we enforce the principle of least privilege. This creates a security boundary; if a vulnerability were ever to allow a process to "escape" the virtual machine, it would be confined to an unprivileged account on the host, unable to access system-level files or gain administrative control.

---

## Encrypt All Data at Rest

All files related to the virtual machines, including the virtual disks themselves, are stored on dedicated external drives. These drives are formatted with Apple's native **APFS (Encrypted)** file system. This ensures that all data is encrypted at rest. If any physical drive is ever lost or stolen, its contents will be unreadable.

---

### Setup Guide

The following steps provide a practical walkthrough for implementing the concepts described above.

### 1. Create a **standard (non-administrator) user** dedicated only for running the VM

1. Navigate to **System Settings > Users & Groups**.
2. Click **Add Account...** (you will need to authenticate as an administrator).
3. Set the account type to **Standard**.
4. Give the user a descriptive name, such as `vm-runner`.
5. Create a strong password for this user.
6. Log out of your administrator account and log in as the new `vm-runner` user to run VMware Fusion.

### 2. Format and encrypt the drive with **APFS (Encrypted)** file system

1. Connect your external SSDs to the Mac.
2. Open **Disk Utility**.
3. In the menu bar, select **View > Show All Devices**.
4. Select the top-level SSD device in the sidebar (not the volume underneath it).
5. Click **Erase**.
6. Configure the erase dialog as follows:
  - **Name:** Choose a descriptive name (e.g., `VM-Storage`).
  - **Format:** Select **APFS (Encrypted)**.
  - **Scheme:** Select **GUID Partition Map**.
7. Click **Erase**. You will be prompted to create and verify a strong encryption password for the drive.
8. Once formatted, the drive will be ready to store your VMs.
# 2. Services Virtual Machine Setup

This phase covers the creation and configuration of the _Services VM_ that will host all the containerized services. The focus is on implementing a specific hardware layout that promotes security, efficient data management, and minimal resource consumption.

## The Architecture

A core principle of this architecture is the strict separation of the operating system from the application data. To achieve this, the virtual machine is configured with **three distinct virtual disks**:

1. **OS Disk:** A small, lean disk (e.g., ~12 GB) dedicated exclusively to the Debian operating system and essential software like Docker. This disk is considered ephemeral; it can be quickly rebuilt from scratch without affecting any persistent data.
2. **Data Disk:** A much larger disk that will hold all persistent application data (databases, user uploads, etc.). This disk is passed to the guest OS as a raw, unformatted block device, ready to be managed by ZFS. This separation simplifies backups, as only the data disk needs to be targeted.
3. **Backup Data Disk:** This virtual disk will contain a mirror of all the data stored in the **Data Disk**.

## Headless Server Configuration

Since this VM will function as a headless server, it does not require a graphical user interface or any peripherals. To minimize its attack surface and reduce resource overhead (CPU/RAM), all non-essential virtual hardware is removed. This includes devices like virtual sound cards, USB controllers, and 3D graphics acceleration, creating a lean and efficient server environment.

## Bridged Networking

To ensure the VM is a first-class citizen on the local network, its network adapter is set to **Bridged Mode**. This configuration allows the VM to get its own unique IP address from your router via DHCP (or be assigned a static one later), just like any other physical device. This makes it directly accessible from other machines on your network, which is essential for hosting services.

---

## TODO list

1. Create the new virtual machine.
2. Configure the VM hardware:
    - Add one small virtual disk for the OS (~12 GB).
    - Add one/two larger, equal-sized virtual disks for Data and Backup.
    - Remove non-essential hardware (sound card, USB controller, etc.).
    - Set the network adapter to "Bridged Mode".
# 3. Seamless SSH Access from macOS Host

The goal is to create a convenient workflow that is both easy to use and adheres to security best practices, by setting up a streamlined and secure way to connect to the guest VM's terminal using SSH

---

## 1. Connection Aliasing with an SSH Config File

### Prerequisite

To set up an SSH alias, you need to know the guest's **IP address**. If you are using a **static IP address**, you can configure the SSH alias immediately. **Otherwise**, the guest system must already be running so you can first obtain the **dynamic IP address** assigned by the OS.

### Concept

Remembering IP addresses, custom port numbers, and specific usernames for each server is tedious and prone to error. The OpenSSH client provides a powerful solution: a local configuration file (`~/.ssh/config`).

By creating an entry in this file, you can define a simple **alias** or shortcut (e.g., `homelab`) that encapsulates all the connection details for your VM: its actual hostname or IP address, the remote username, the non-standard port, and which specific SSH key to use for authentication.

### Example: Creating the SSH Config Entry

1. Open or create the SSH configuration file (`~/.ssh/config`) in a text editor.

2. Add the following block to the file. Each line is a directive that tells the SSH client what to do when you try to connect to the alias `homelab`:
```sh
# A descriptive comment for your VM
# This is the alias you will type in the terminal
Host homelab

    # The actual IP address or DNS name of your VM
    HostName xxx.xxx.xxx.xxx

    # The username to log in with on the VM
    User runner

    # The custom SSH port you configured on the VM
    Port 2222

    # The path to the specific private key for this VM
    IdentityFile ~/.ssh/your_private_key_file
```

After saving this file, the difference will be:
- **Before:** You would have to type the full, complex command every time:
    `ssh -p 2222 -i ~/.ssh/your_private_key_file runner@xxx.xxx.xxx.xxx`
- **After:** You can now simply type the alias:
    `ssh homelab`

-----

## 2. Automating Authentication with an SSH Agent

For security, SSH private keys are often protected with a passphrase. This passphrase encrypts the key file on your disk, so even if someone steals the file, it's useless without the passphrase. While essential, entering it every time you connect is cumbersome.

An **SSH agent** is a background program that securely holds your private keys in memory. When you add a key to the agent, you "unlock" it once with its passphrase. For the rest of your session, the agent automatically and securely handles the authentication with the server on your behalf, creating a passwordless experience.

On macOS, this process is seamlessly integrated with the system's **Keychain**.

**Note:** Always remember to backup/store all the keys and passwords in a password manager or in a secure place.

---

## Setup Guide

1. Start the guest VM and find its IP address.
2. On the macOS host, open (or create) the `~/.ssh/config` file in a text editor.
3. Add a new Host block for the VM (e.g., Host homelab).
4. Inside the block, specify the VM's HostName (IP address), User, Port, and IdentityFile (path to your private key).
5. Save the `~/.ssh/config` file.
6. Add your private key's passphrase to the macOS Keychain/agent (e.g., `ssh-add -K /path/to/key`).
7. Test the seamless connection using your new alias (e.g., ssh homelab).
8. Back up your private key file
# Guest Layer: Debian

This document details the creation of the main "Services VM," transforming a bare virtual machine into a hardened, efficient, and secure host for all containerized applications.

This layer is built on four pillars:
1. **Debian Linux** installation.
2. **ZFS filesystem** for data integrity and backups.
3. **Docker Engine** environment using User Namespace Remapping.
4. **Backup Strategy** combining ZFS snapshots with BorgBackup.

![Guest Architecture](../_assets/guest_architecture.svg)
# 1. OS Installation and Hardening

## Concepts

The foundation of the guest is a minimal Debian installation. This approach reduces the attack surface, minimizes resource consumption, and improves overall stability by only installing what is absolutely necessary.

The base OS is configured with several key security practices:
- **Static IP Address:** The VM is assigned a static IP on the local network to provide a stable, predictable endpoint for the reverse proxy and DNS records.
- **Privileged User Model:** Direct root login is disabled. A single administrative user (e.g. `runner`) is created with `sudo` privileges for all management tasks.
- **Key-Based Authentication:** Password-based authentication over SSH is disabled. Access is granted exclusively through public-key cryptography, which is significantly more secure.
- **Non-Standard SSH Port:** The SSH service listens on a port above 1024. This simple obscurity step reduces exposure to automated bots and scanners that target the default port 22.
- **Default-Deny Firewall:** A firewall (`ufw`) is configured to block all incoming traffic by default, only explicitly allowing connections on the custom SSH port.

---

## Setup Guide

### 1 Base OS Installation

First, you will install the minimal Debian operating system from the "netinstall" image.

1. **Boot from ISO:** Start the VM using the Debian Netinstall ISO.
2. **User Setup:**
   - When prompted for a **Root Password**, leave it **BLANK** and continue.
   - This is a critical step. It disables the root account and automatically grants `sudo` privileges to the administrative user you create next.
   - Create your administrative user (e.g., `runner`).
3. **Disk Partitioning:**
   - At the partitioning step, choose **Manual**.
   - Select the small OS disk (e.g., `sda`). Create a new partition table and use the guided partitioning for this disk, placing all files in one partition.
   - **Important:** Do not touch the larger data disk (e.g., `sdb`). It must be left completely unformatted for its later use with ZFS.
4. **Software Selection:**
   - On the "Software selection" screen, deselect any graphical environment (like GNOME or KDE).
   - Ensure only the following two options are checked:
     - **SSH server**
     - **Standard system utilities**
5. **Complete Installation:** Finish the installation, install the GRUB boot loader to your OS drive (e.g., `/dev/sda`), and reboot.

### 2 Network Configuration

Log in as your new `runner` user. The first post-install step is to set a static IP address.

1. Open the network configuration file:
  ```bash
  sudo nano /etc/network/interfaces
  ```
2. Modify the entry for your network adapter (e.g., `ens18` or `eth0`) to change it from `dhcp` to `static`. Use the correct IP address, netmask, and gateway for your network.
  ```
  # Change this:
  auto ens18
  iface ens18 inet dhcp

  # To this (example):
  auto ens18
  iface ens18 inet static
    address 192.168.1.100
    netmask 255.255.255.0
    gateway 192.168.1.1
  ```
3. Reboot the system (`sudo reboot`) for the changes to take effect. Log back in at the new static IP address.

### 3 Security Hardening (SSH & Firewall)

Now you will secure the server by locking down SSH and enabling the firewall.

1. **Configure SSH Server:**

   - Edit the SSH daemon configuration file:
    ```bash
    sudo nano /etc/ssh/sshd_config
    ```
   - Make the following changes to enforce the security policies:
     - **Change Port:** Find `#Port 22` and change it to a high, non-standard port (e.g., `Port 2222`).
     - **Disable Root Login:** Change `PermitRootLogin` to `no`.
     - **Disable Password Login:** Change `PasswordAuthentication` to `no`.
     - **Ensure Key Login:** Verify `PubkeyAuthentication` is set to `yes`.
   - Save the file and exit the editor.

2. **Configure Firewall (ufw):**

   - Before restarting SSH, you **must** allow your new SSH port through the firewall.
   - Set the default policies to deny all incoming traffic:
    ```bash
    sudo ufw default deny incoming
    sudo ufw default allow outgoing
    ```
   - Add an "allow" rule for your new custom SSH port (e.g., `2222`):
    ```bash
    sudo ufw allow 2222/tcp
    ```
   - Enable the firewall. It will prompt for confirmation; type `y`.
    ```bash
    sudo ufw enable
    ```

3. **Apply All Changes:**

   - Restart the SSH service to apply the new configuration.
    ```bash
    sudo systemctl restart ssh
    ```

Your server is now hardened. You will be disconnected from your current session and must reconnect using the new port (e.g., `ssh runner@192.168.1.100 -p 2222`). From this point on, you can only log in with your SSH key.
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
# 3. ZFS

Instead of a traditional filesystem like `ext4` for the data storage, this architecture uses **ZFS** on the dedicated data disk. ZFS is a logical volume manager and filesystem that provides a lot of useful features:

- **Data Integrity:** ZFS is designed to protect data from silent data corruption (bit rot). It checksums all data and metadata, and if it detects corruption on a read, it can automatically repair the data if you have redundancy (e.g., a mirror).
- **Atomic Snapshots:** This is the cornerstone of the backup strategy. ZFS can create an instantaneous, read-only, point-in-time snapshot of the entire filesystem or a specific dataset. This takes less than a second and captures a perfectly consistent state, which is ideal for backups.
- **Datasets:** ZFS allows you to create separate filesystems, called datasets, within a single storage pool. This architecture leverages datasets to isolate the data for each service (e.g., `datapool/services/git`, `datapool/services/photo`). This allows for granular management, compression settings, and snapshots on a per-service basis.

---

## Setup Guide

This guide will walk you through installing ZFS and creating your initial storage pool and dataset.

### Step 1: Install ZFS Utilities

First, install the necessary ZFS management tools on your system.

```bash
sudo apt install -y zfsutils-linux
```

### Step 2: Identify the Data Disk

You need to find the device name for the disk you want to dedicate to ZFS. Use `lsblk` to list your block devices. Look for the large, unformatted disk you intend to use (e.g., `/dev/sdb`).

```bash
lsblk
```

### Step 3: Create the ZFS Pool

> **Warning:** This step is **destructive** and will **erase all data** on the disk you select. Double-check that you have the correct device name.

This command creates a new storage "pool" named `datapool` using the entire disk. ZFS will automatically mount this pool at `/datapool`.

```bash
# Replace /dev/sdb with your actual disk name
sudo zpool create datapool /dev/sdb
```

### Step 4: Create the Parent Dataset

It's best practice to create a parent dataset to hold all your application data, rather than storing files directly in the pool's root. This makes management and snapshots easier.

```bash
sudo zfs create datapool/services
```

You can now store your service data within this path. As you deploy new services, you can create new child datasets (e.g., `sudo zfs create datapool/services/media`) to manage them independently.

-----

## 3 Optional Troubleshooting: Fix Boot-Time Import Failure

You may see a `[FAILED] Failed to start zfs-import-cache.service` error when your system boots.

This is a common **race condition**, especially in virtual machines. The ZFS import service tries to load the pool from a cache file before the virtual disk is fully initialized by the system, so the import fails.

The fix is to disable the fast (but less reliable) cache-based import and enable the more robust **scan-based import**, which actively scans devices for pools.

### 1 Disable the Failing Cache Service

```bash
sudo systemctl disable zfs-import-cache.service
```

### 2 Enable the Scan Service

```bash
sudo systemctl enable zfs-import-scan.service
```

### 3 Reboot

The new service will take effect on the next boot.

```bash
sudo reboot
```
# 4. Borg Backup

Borg was chosen as the core backup tool for several key features that make it ideal for this architecture:

- **Deduplication:** Borg's breaks data into small, encrypted chunks. When you run a backup, it only uploads chunks that it hasn't seen before. This means that after the first backup, subsequent backups are fast and consume very little additional space, as only the changes are stored.
- **Client-Side Encryption:** All your data is encrypted on your server before it is sent to the backup destination. This means you can safely back up to untrusted, commodity cloud storage.
- **Compression:** Borg supports multiple compression algorithms (like `zstd`) to further reduce the size of your backup archives, saving storage costs.
- **Scriptability:** As a command-line tool, Borg is perfect for automation. It can be easily integrated into scripts.

-----

## Setup Guide

### Step 1: Install Borg Backup

First, you need to install the Borg software on your Debian "Services VM". The official docs of BorgBackup can be found [here](https://www.borgbackup.org/releases/).

```bash
sudo apt update
sudo apt install borgbackup -y
```

This command installs Borg and makes its command-line tools available.

### Step 2: Configure SSH Access to Remote Storage

Borg uses the **Secure Shell (SSH)** protocol to safely transfer your encrypted data to a remote location. To enable automation, you must set up key-based authentication, which allows your server to log in to the remote storage without needing a password.

#### **Concept**

You will generate a unique pair of cryptographic keys on your Homelab VM: a **private key** that stays on the server and a **public key** that you will copy to the remote storage. The remote server will then grant access to anyone who can prove they hold the corresponding private key, eliminating the need for a password.

#### **Required Actions**

1. **Generate an SSH Key Pair on your Homelab VM:**
Run the following command. When prompted, press Enter to accept the default file location, and it's highly recommended to create a **strong passphrase** for the key as an added layer of security.

> It's good practice to create a dedicated key for Borg
```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_borg
```

2. **Copy the Public Key to your Remote Storage:**
Use the `ssh-copy-id` utility to automatically install the public key on your remote storage server. Replace `user@remote-server.com` with your actual remote username and hostname/IP.

> This command will ask for your remote server's password one last time
```bash
ssh-copy-id -i ~/.ssh/id_borg.pub user@remote-server.com
```

3. **Test the Connection:**
Verify that you can now log in without a password. The server shouldn't ask for a password, but it *will* ask for the key's passphrase if you set one.

```bash
ssh -i ~/.ssh/id_borg user@remote-server.com
```

If you connect successfully, your passwordless access is configured correctly.
# 5. Backup and Recovery Strategy

The backup strategy for this Homelab is designed around two primary goals: **maximum data consistency** and **minimal service downtime**. This is achieved by combining the features of **ZFS** with the one from **BorgBackup**. This document explains the architecture, workflow, and configuration of this system.

![Backup Flow](../_assets/backup_flow.svg)

---

## The Architecture

A key architectural decision is to create **one dedicated Borg repository for each ZFS dataset**. Instead of backing up all services into a single, monolithic archive, each service's data is isolated in its own encrypted repository.

This approach provides several significant advantages:

- **Isolation & Resilience:** Corruption or an issue in one service's backup history (e.g., for a less critical app) has zero impact on the backups of your other, more critical services. This prevents a single point of failure in your backup system.
- **Granular Retention Policies:** You can apply different pruning rules to different services. For example, you can configure the system to keep a year of daily backups for your source code repository but only 90 days of backups for a media server's metadata.
- **Simplified Recovery:** In a disaster, restoring a single service is simple and clean. You only need to interact with its dedicated, smaller repository, which makes the recovery process faster and less error-prone.

---

## The Backup Workflow

The power of this setup comes from the synergy between ZFS's instantaneous snapshots and Borg's efficient, deduplicating backups. This workflow guarantees a perfect, point-in-time backup with service downtime measured in seconds, not minutes or hours.

The process unfolds in five distinct steps:

1. **Stopping Services:** All Docker containers are gracefully stopped. This is the first step because we need to ensure applications have cleanly flushed all their data to disk and that databases are in a consistent, non-transacting state.
2. **Create Atomic Snapshot:** An instantaneous ZFS snapshot of all service datasets is taken. This acts as a perfect, read-only "photograph" of the data at that exact moment. This operation typically takes less than a second to complete.
3. **Resume Services:** Immediately after the snapshot is secured, all Docker containers are restarted. The total downtime for your services is only the time it takes to complete the first two steps, which is typically just a few seconds.
4. **Perform Backup from Snapshot:** The BorgBackup process begins. Crucially, it reads data from the **static and unchanging ZFS snapshot**, not the live filesystem. This decouples the backup duration from service uptime. The backup can take as long as necessary without being affected by ongoing changes in the live services, completely avoiding issues with file locks or inconsistent data.
5. **Prune and Cleanup:** After the backup is successfully sent to the offsite location, Borg prunes any old archives according to your retention policy. Finally, the temporary ZFS snapshot is destroyed to reclaim space on the data disk.

---

## Disaster Recovery Concept

Restoring data is straightforward due to the granular repository architecture. The general process involves:
1. Setting up a new server and installing Borg.
2. Using the `borg mount` or `borg extract` command with the correct repository path, your passphrase, and (if needed) the repository's recovery key.
3. Copying the required data back to its original location.

Because each service has its own repository, you can restore a single failed service quickly and without affecting any others.# 6 Populating the Guest: Configs, Services, and Scripts

With the hardened Debian OS, ZFS, and Docker installed, the virtual machine is an empty, secure shell. This guide explains how we "fill" it with the intelligence: the **automation scripts**, the **service configurations** (Docker Compose), and the **persistent data** itself.

This "filling" happens in two distinct zones:

1. **The Automation and Service Definitions (`/home/runner`):** Located on the fast OS disk, this is where all configurations, scripts, and service *definitions* live. This area is lightweight and ideal for version control (e.g., with Git).
2. **The ZFS-Managed Persistent Data (`/datapool`):** This is the large ZFS data pool. It *only* stores the persistent, heavy-lifting data generated by your services (e.g., databases, photo libraries, Git repositories).

-----

## Automation and Service Definitions

The `runner` user's home directory is the central hub for managing the entire homelab. It's split into two key parts.

### 1. The Automation Framework (`/home/runner/management/`)

This directory contains the scripts and tools that manage the server, run backups, and automate tasks. It's the "command center" of the VM.

This directory will better described in the [Automation layer](../3-automation/0_index.md) section.

### 2. The Service Definitions (`/home/runner/services/`)

This directory contains all your **Docker Compose files** and their related configurations. It defines *what* services run and *how* they are configured.

- **Structure:** Each service or stack (e.g., `git`, `photo`) gets its own sub-directory.
- **Contents:** Inside each service directory, you'll find:
  - `docker-compose.yml`: The file that defines the containers, networks, and volumes for that service.
  - `.env`: A configuration file *specific to that service*, defining things like ports, passwords, and data paths.
- **Why this structure?**
  1. **Clean Separation:** It separates the *configuration* of a service (the `docker-compose.yml`) from its *data* (which lives on the ZFS pool).
  2. **Version Control:** This entire `/home/runner/services` directory is "stateless". You can (and should) back it up or place it under Git version control without worrying about large data files.
  3. **Automation:** The management scripts can easily find, start, stop, and update all services by simply looking through the sub-directories here.

This directory will be better defined in the [Services layer](../2-services/0_index.md) section.

-----

## ZFS-Managed Persistent Data

This is where your applications' data *actually lives*. The ZFS pool is mounted at `/datapool` and is organized using ZFS datasets for maximum data integrity and snapshot capability.

 - **ZFS Hierarchy:** We create a parent dataset (`datapool/services`) and then a **dedicated child dataset for each service** (e.g., `datapool/services/git`, `datapool/services/photo`).
 - **Benefits:** This dataset-per-service model is the core of the backup strategy. It allows you to take an atomic, instantaneous snapshot of a single service's data before backing it up.

### Connecting the pieces

The "magic" happens in your `docker-compose.yml` files, where you map a service's data directory *inside* the container to its dedicated ZFS dataset *outside* on the host.

**Example:** For a Git service, its `docker-compose.yml` (located at `/home/runner/services/git/docker-compose.yml`) would contain a volume mapping like this:

```yaml
services:
 gitea:
  image: gitea/gitea:latest
  container_name: gitea
  volumes:
   # This line maps the container's /data directory to the host's ZFS dataset.
   - /datapool/services/git:/data
  ports:
   - "3000:3000"
```

This tells Docker: "Any file the 'gitea' container writes to its `/data` folder should actually be saved on the host at `/datapool/services/git`."

 - **For Complex Services:** If a service needs multiple data paths (e.g., a database, a library, and temp files), you simply create regular directories *within* its ZFS dataset.
   - Example: `/datapool/services/photo/database`
   - Example: `/datapool/services/photo/library`

-----

## Tying It All Together: The Full Directory Map

This tree diagram shows the complete, "filled" structure of the homelab, illustrating the separation of configuration (in `/home/runner`) and data (in `/datapool`).

```
/
├── home/
│ └── runner/
│  ├── management/            <- Automation
│  │ ├── Makefile             <- Your command entrypoint
│  │ ├── .env                 <- VM-wide "single point of truth"
│  │ ├── borg_excludes.txt
│  │ ├── python/              <- Automation scripts (backup logic, etc.)
│  │ └── borg_keys/           <- Borg encryption keys
│  └── services/              <- Service Definitions
│   ├── central_hub/
│   │ ├── docker-compose.yml  <- Service docker compose definition
│   │ └── .env                <- Config for this service
│   ├── git/
│   │ ├── docker-compose.yml  <- Service docker compose definition
│   │ └── .env                <- Config for this service
│   └── ...                   <- Other service configs
│
└── datapool/                 <- The "Memory" (ZFS Pool Mount Point)
 └── services/                <- ZFS Parent Dataset
  ├── git/                    <- ZFS Dataset (mounts /datapool/services/git)
  │ └── ...                   <- Actual Git application data
  ├── photo/                  <- ZFS Dataset (mounts /datapool/services/photo)
  │ ├── database/             <- App database data
  │ ├── library/              <- App media library
  │ └── temp_uploads/         <- App temp folder
  └── ...                     <- Other service datasets and their data
```# Service Layer: Networking and Applications

This document explains the networking architecture that allows all services to run securely and communicate effectively. It also provides an overview of the services included in this repository.

![Service Architecture](../_assets/service_architecture.svg)

---

## Core Networking Concepts

### 1. The Central Hub: Caddy Reverse Proxy

A single **Caddy** container acts as the "hub" and the sole entry point for all HTTP/S traffic into the Homelab. It is the only service that exposes ports to the host VM. Its responsibilities are:

- **Traffic Routing:** It inspects incoming requests and routes them to the correct backend service based on the requested domain name (e.g., `gitea.homelab.lan`).
- **Automatic HTTPS:** Caddy automatically provisions and renews TLS certificates for all services, ensuring all traffic is encrypted with HTTPS. For internal-only domains, it runs its own internal Certificate Authority.
- **Decoupling:** Services don't need to know about each other. They only need to be reachable by Caddy.

### 2. The Spokes: Isolated Service Stacks

Each service or group of related services (a "stack," like Gitea and its database) is treated as a "spoke." To achieve maximum security and isolation, every spoke is deployed onto its own **dedicated, private Docker network**.

- **Total Isolation:** Containers on one private network (e.g., `git_net`) cannot see or interact with containers on another private network (e.g., `photo_net`). This prevents a potential compromise in one application from spreading to others.
- **The Caddy Bridge:** The Caddy container is the **only component connected to all of these private networks**. This unique position allows it to act as the central router that can forward traffic to every spoke, while the spokes remain completely isolated from each other.

### 3. The Map: Internal DNS Server

An independent DNS server (running in its own VM, e.g., AdGuard Home or Pi-hole) acts as the "map" for the entire network. Its roles are:

- **Authoritative Local DNS:** It resolves all custom local domains (e.g., `git.homelab.lan`, `photo.homelab.lan`) to the single, static IP address of the Caddy container.
- **Ad & Tracker Blocking:** It provides network-wide filtering for all devices in your home.
- **Replaces MagicDNS:** This custom DNS setup completely replaces Tailscale's MagicDNS, providing more control and network-wide ad blocking for all devices, whether they are on the local network or connected remotely via Tailscale.

### 4. The Gateway: Unified Remote Access with Tailscale

A single **Tailscale** container provides secure, unified remote access to the entire Homelab. It operates in two key roles:

- **Subnet Router:** It advertises your local LAN (e.g., `xxx.xxx.0.0/24`) to your private Tailscale network. This allows your remote devices (phone, laptop) to securely access your internal services as if you were at home. Tailscale ACLs are used to restrict remote clients so they can only access the DNS server and the Caddy VM, not your entire local network.
- **Exit Node:** You can configure your remote devices to route all their internet traffic through your home network.

---

## Service Deployment

All services are defined as Docker Compose stacks. The configuration for each is located in a dedicated subdirectory within `/services`.

- **`/services/reverseproxy/`**: Contains the `docker-compose.yml` and `Caddyfile` for the main reverse proxy.
- **`/services/git/`**: Contains the `docker-compose.yml` for the Gitea source control service and its PostgreSQL database.
- **`/services/photo/`**: Contains the `docker-compose.yml` for the Photo service.
- ...and so on for other services.

Each `docker-compose.yml` file is written to be self-contained for its specific application stack and is configured to connect to its dedicated, external Docker network that you create and manage.
# Network

The entire networking model is designed around a secure **"hub-and-spoke" architecture**.  This approach is built on three core components that work together, with a fourth providing optional remote connectivity.

At the center is the **Hub**, a reverse proxy that acts as the single, controlled entry point for all traffic. Branching from the hub are the **Spokes**—the individual services, each completely isolated in its own private network. To navigate this system, a local **DNS Server** acts as the map, translating friendly domain names to the hub's address. An optional **Remote Access Gateway** can be added to provide a secure tunnel into the homelab from anywhere.

---

## 1. The Central Hub: Reverse Proxy

A single **Caddy** container acts as the "hub" and the sole entry point for all HTTP/S traffic into the Homelab. It is the only service that exposes ports to the host VM. Its responsibilities are:

- **Traffic Routing:** It inspects incoming requests and routes them to the correct backend service based on the requested domain name (e.g., `git.homelab.lan`).
- **Automatic HTTPS:** Caddy automatically provisions and renews TLS certificates for all services, ensuring all traffic is encrypted with HTTPS. For internal-only domains, it runs its own internal Certificate Authority.
- **Decoupling:** Services don't need to know about each other. They only need to be reachable by Caddy.

## 2. The Spokes: Isolated Service Stacks

Each service or group of related services (a "stack," like Gitea and its database) is treated as a "spoke." To achieve maximum security and isolation, every spoke is deployed onto its own **dedicated, private Docker network**.

- **Total Isolation:** Containers on one private network (e.g., `git_net`) cannot see or interact with containers on another private network (e.g., `photo_net`). This prevents a potential compromise in one application from spreading to others.
- **The Caddy Bridge:** The Caddy container is the **only component connected to all of these private networks**. This unique position allows it to act as the central router that can forward traffic to every spoke, while the spokes remain completely isolated from each other.

## 3. The Map: Internal DNS Server

An independent DNS server (running in its own VM, e.g., AdGuard Home or Pi-hole) acts as the "map" for the entire network. Its roles are:

- **Authoritative Local DNS:** It resolves all custom local domains (e.g., `git.homelab.lan`, `photo.homelab.lan`) to the single, static IP address of the Caddy container.
- **Ad & Tracker Blocking:** It provides network-wide filtering for all devices in your home.
- **Replaces MagicDNS:** This custom DNS setup completely replaces Tailscale's MagicDNS, providing more control and network-wide ad blocking for all devices, whether they are on the local network or connected remotely via Tailscale.

## 4. The Gateway: Unified Remote Access with Tailscale

A single **Tailscale** container provides secure, unified remote access to the entire Homelab. It operates in two key roles:

- **Subnet Router:** It advertises your local LAN (e.g., `xxx.xxx.0.0/24`) to your private Tailscale network. This allows your remote devices (phone, laptop) to securely access your internal services as if you were at home. Tailscale ACLs are used to restrict remote clients so they can only access the DNS server and the Caddy VM, not your entire local network.
- **Exit Node:** You can configure your remote devices to route all their internet traffic through your home network.
# The Central Hub

In the homelab's "hub-and-spoke" architecture, the Caddy reverse proxy is the **central hub**. It's the sole entry point for all web traffic, routing requests to the correct backend services. This centralization is a core security principle, as it's the only service that needs to expose ports to the host VM.

Caddy's primary responsibilities are:

 - **Traffic Routing:** It directs incoming requests to the correct service based on the domain name, like `photo.homelab.lan`.
 - **Automatic HTTPS:** Caddy handles all TLS encryption, even creating its own internal Certificate Authority for local domains to provide trusted connections without any manual setup.
 - **Service Bridging:** It's the only component connected to every isolated service network, allowing it to "bridge" traffic to the spokes while they remain isolated from each other.

 -----

### How a Request Flows

Putting it all together, here is the journey of a single request from a remote user to a service:

1. **Request**: You type `https://git.homelab.lan` into your browser.
2. **DNS Resolution**: Your device queries the internal DNS server, which resolves `git.homelab.lan` to the static IP of the Caddy container.
3. **Caddy Entrypoint**: The request arrives at the Caddy container on port 443.
4. **Routing**: Caddy reads the request's `Host` header, finds the matching `git.homelab.lan` block in its Caddyfile, and terminates the TLS connection.
5. **Proxying**: Caddy then forwards the plain HTTP request to the `gitversioncontrol-gitea` container on its private network at port `3000`.
6. **Response**: The Gitea container processes the request and sends the response back to Caddy, which encrypts it and sends it back to your browser.

![Central Hub Flow](../_assets/central_hub_flow.svg)

-----

### Docker Compose Configuration

The deployment of Caddy is defined in its `docker-compose.yml` file.

Here's a breakdown of an example configuration:
```yaml
services:
 caddy:
  build: .
  container_name: central_hub
  restart: unless-stopped

  # Connects Caddy to all isolated service networks
  networks:
   - central_hub_net
   - photo_net

  # Exposes the standard web ports to the host VM
  ports:
   - "80:80"
   - "443:443"
   - "443:443/udp"

  volumes:
   # Mounts the configuration file
   - ./Caddyfile:/etc/caddy/Caddyfile:ro

   # Persists TLS certificates and other data
   - caddy_data:/data

volumes:
 caddy_data:

# Defines all networks as external
networks:
  central_hub_net:
    external: true
  photo_net:
    external: true
```

 - `networks`: This is the most critical section for the hub-and-spoke model. By connecting Caddy to every service network, it gains the ability to communicate with and route traffic to the containers on those otherwise isolated networks.
 - `ports`: Caddy listens on the standard HTTP/S ports. Port `80` is used for HTTP requests, which Caddy typically redirects to HTTPS. Port `443` is for secure HTTPS traffic, and `443/udp` enables the modern HTTP/3 protocol.
 - `volumes`:
   - The `Caddyfile` is mounted as a read-only configuration file from the host.
   - The `caddy_data` named volume is essential. It stores Caddy's generated data, most importantly the TLS certificates and the local Certificate Authority, ensuring they persist even if the container is recreated.

-----

### Caddyfile Routing Logic

The `Caddyfile` is a simple text file that defines how Caddy handles incoming requests.

```caddy
# Git Version Control Service (Gitea)
photo.homelab.lan {
  reverse_proxy photo-immich-server:2283
  tls internal
}
```

Each block in the file defines a route:

 - `photo.homelab.lan`: This is the site address. When Caddy receives a request for this domain, this block is activated.
 - `reverse_proxy  photo-immich-server:2283`: This is the core instruction. Caddy uses Docker's internal DNS to find the container named ` photo-immich-server` on the shared network and forwards (proxies) the request to its internal port `2283`. The backend service doesn't need to expose any ports to the host.
 - `tls internal`: This directive tells Caddy to use its own automatically managed internal Certificate Authority to serve a trusted TLS certificate for this local domain.
# A generic service

Each application in this homelab is deployed as a self-contained **stack** using a single `docker-compose.yml` file. This approach ensures that all services follow a consistent set of architectural principles for security, isolation, and manageability.

This guide uses the **Photo** service as a working example to illustrate these core concepts.

---

### 1 Structure and Naming Philosophy

Each service is self-contained within its own directory. This structure is built on a specific naming philosophy that separates the **function** of a service from its **implementation**.

  - **The Service (The "What"):** The directory name defines the *function* or *problem* the service solves (e.g., `git`). This name is abstract and represents "what you need."
  - **The Implementation (The "How"):** The container and network names inside the `docker-compose.yml` file describe the *specific software* being used (e.g., `gitversioncontrol-gitea`).

If you later decide to replace Gitea with GitLab, the service is still just `git`. You only change the implementation *inside* the `git` directory, and the rest of your system (like your Caddyfile) remains largely unchanged. This also prevents container name conflicts if the same image (e.g., `postgres`) is used by multiple services.

A typical service directory looks like this:

```
git/                     <-- The Service
├── docker-compose.yml   <-- The Implementation
├── Dockerfile           <-- (Optional) Custom build
└── .env                 <-- Configuration & secrets
```

This philosophy extends to the files themselves. Inside the `docker-compose.yml`, the container and network names reflect the specific implementation:

```yaml
services:
  gitversioncontrol-gitea:  # Specific implementation name
    ...
  gitversioncontrol-gitea-db:
    ...

networks:
  gitversioncontrol_network: # Specific implementation network
    external: true
```

And the `Caddyfile` configuration maps the functional domain (`git.homelab.lan`) to the specific implementation container (`gitversioncontrol-gitea`):

```caddy
git.homelab.lan {
    reverse_proxy gitversioncontrol-gitea:3000
    tls internal
}
```

### 2. Multi-Container Stacks

Services are rarely a single container. A modern application stack typically consists of several interconnected components. The Immich stack, for example, is composed of four distinct services working together:
- `immich-server`: The main application backend.
- `immich-machine-learning`: A dedicated container for processing tasks like object recognition.
- `immich-redis`: A Redis container for caching and message queuing.
- `immich-database`: A PostgreSQL database for storing all metadata.

---

### 3. Network Isolation

Every service stack is deployed onto its own **dedicated, private Docker network**.
- **Complete Isolation**: The Immich stack runs exclusively on the `photo_net` network. Containers on this network are completely isolated and cannot see or interact with containers from other service stacks (e.g., Git). This is a fundamental security principle of the "hub-and-spoke" model.
- **Internal Communication**: Containers within the same stack communicate with each other using their service names as hostnames. For instance, the Immich server connects to its database using the hostname `immich-database`, which works thanks to Docker's internal DNS.
- **External Network Definition**: The network is defined as `external: true`, meaning it is created and managed externally, not by Docker Compose itself.

---

### 4. Security Principles

Security is built into the design of every service stack.
- **No Exposed Ports**: Noticeably, **no container in the stack exposes ports** to the host VM. There is no `ports:` section. All incoming traffic must be routed through the Caddy reverse proxy, which is the only service that listens on the network. This drastically reduces the attack surface.
- **Principle of Least Privilege**: Each container is configured to run as a specific, non-root user (e.g. via the `user:` directive). For example, the server runs as user `1000:1000` (the internal `node` user), while the database runs as `999:0` (the `postgres` user). This integrates directly with the host's `userns-remap` security model, ensuring that processes inside the container have minimal privileges on the host filesystem.

---

### 5. Data Persistence and Configuration

- **Persistent Storage**: Critical data that must survive container restarts and be backed up is stored on the host's ZFS filesystem. This is achieved by mounting host paths as volumes, such as `${IMMICH_DB_DATA_LOCATION}:/var/lib/postgresql/data` for the database.
- **Configuration via Environment**: All configuration, especially secrets like database passwords and usernames, is passed into the containers as environment variables. These values are stored in a separate `.env` file, cleanly separating configuration from the service definition.

---

### 6. Reliable Startup

To ensure the stack starts up in a predictable and stable manner, dependencies and health checks are used.
- **Startup Order**: The `depends_on` directive ensures that the main Immich server will only start after its dependencies are running. It waits for Redis to have started and, more importantly, for the database to pass its health check and be fully ready to accept connections.
- **Health Checks**: The database and Redis containers have `healthcheck` sections that define a command to test their status, ensuring they are not just running but are actually healthy.
# Remote Access

The Remote Access service functions as a multi-purpose network gateway by using Tailscale. It securely connects your homelab to your private Tailscale network and provides two main capabilities: acting as a **subnet router** to access your local network remotely and as an **exit node** to route your internet traffic through your home connection.

To learn what can you do with Tailscale, you can read the official documentation [here](https://tailscale.com/kb/1017/install). The following are only the features that were useful for me.

### Subnet Router

The container is configured to act as a **subnet router**, advertising yotheur local network (e.g., `xxx.xxx.0.0/24`) to all other devices on the Tailscale network. This allows to securely access any device on the home LAN from a remote location as if you were physically there, not just the services running on the VM.

### Exit Node

By using the `--advertise-exit-node` argument, the service also offers itself as an **exit node**. This allows you to route all internet traffic from a remote device (like your phone or laptop on public Wi-Fi) through your home's internet connection.

---

## Configuration Details

The service's functionality is enabled by specific settings in its Docker Compose configuration.

- **Kernel-Level Networking**: The service operates in a high-performance kernel networking mode. This is achieved by mounting the host's TUN device (`/dev/net/tun`) into the container and explicitly setting `TS_USERSPACE=false`. This is more efficient than the default userspace mode.
- **IP Forwarding**: The container has IP forwarding enabled via `sysctls` settings (`net.ipv4.ip_forward=1` and `net.ipv6.conf.all.forwarding=1`). This is a critical kernel setting that permits the container to forward network packets between the Tailscale virtual network and your physical home network, which is the essential function of a router.
- **Elevated Privileges**: To manage network interfaces and routing rules, the container requires the `net_admin` and `sys_module` capabilities.
- **Persistent State**: The service's state and configuration are stored on the host using volumes, ensuring that the node's identity is preserved across restarts and you don't need to re-authenticate it.
- **Custom DNS**: The container is configured to use the internal DNS server, ensuring that local domain resolution works correctly even when connected remotely.# 6. Automation

The "automation" layer is a collection of scripts that provides an integrated automation system for managing the homelab server. Its primary purpose is to **orchestrate Docker Compose services, ZFS storage, and Borg backups** in a consistent manner.

This automation layer is a **living project**. It's not perfect, but usable.

## Why we need Automation

Imagine managing a server with multiple Dockerized applications, each requiring specific storage configurations, permissions, regular backups, and system updates. Manually performing these tasks would involve:

- **Dozens of Shell Commands:** Remembering commands like: `useradd`, `chown`, `zfs create`, `borg init`, `docker compose up`, `apt update`; with precise arguments and paths.
- **Sequential Dependencies:** Ensuring commands are run in the correct order (e.g., stopping services *before* a snapshot, installing packages *before* running Python scripts).
- **Error Proneness:** A single typo in a path, a forgotten flag, or an incorrect user ID could lead to failed services, corrupted data, or insecure configurations.
- **Time Consumption:** Daily or weekly maintenance routines would consume significant personal time.
- **Inconsistency:** Manual execution inherently leads to variations, making troubleshooting harder when issues arise.
# 1. Components

The system is built around a central Python **orchestrator** (`orchestrator.py`). This orchestrator calls specialized "manager" classes, each responsible for a specific task (e.g., `ZFSManager` for ZFS commands, `DockerComposeManager` for Docker).

A `Makefile` is provided as a simple, user-friendly wrapper, translating easy-to-remember commands like `make backup-all` into the correct Python script calls with the necessary permissions.

---

## Component Breakdown

The automation is divided into several files, each with a clear responsibility:

**`Makefile`**
- The primary **user-friendly entry point**. It provides simple, memorable commands (e.g., `make setup-storage`, `make docker-up`) that handle running the main orchestrator script with `sudo` and the correct Python environment.

**`orchestrator.py`**
- The **master orchestrator** and central "brain" of the system. It parses the command-line arguments and calls the appropriate manager classes in the correct sequence to perform complex tasks.

**`.env.example`**
* The template for your configuration. You **must** use this to create the `.env` file and fill in your specific details.

**`docker_manager.py`**
- Defines the `DockerComposeManager` class. This script scans the `SERVICES_DIR` (defined in your `.env`) to find all `docker-compose.yml` files and executes Docker Compose commands on them (e.g., `up`, `down`, `pull`).

**`zfs_manager.py`**
- Defines the `ZFSManager` class. This is a Python wrapper for `sudo zfs` commands. It handles creating and destroying datasets and, most importantly, creating and destroying recursive snapshots.

**`storage_manager.py`**
- Defines the `StorageManager` class. This is a critical **one-time setup** script. It reads the `SERVICE_VOLUME_PATHS_AND_OWNERS` from your `.env` and performs all the necessary steps to configure the host for secure UserNS remapping (creating users, setting permissions, etc.).

**`backup_manager.py`**
- Defines the `BackupOrchestrator` class. This script defines the **high-level backup workflow** (stop services, snapshot, start services, loop through datasets, and back them up).

**`borg_backup_manager.py`**
- Defines the `BorgBackupRepoManager` class. This is a low-level wrapper for `sudo borg` commands. It handles initializing repositories, creating archives, pruning old backups, and checking repository integrity.

**`requirements.txt`**
- A list of the required Python libraries (e.g., `sh`, `python-dotenv`, `PyYAML`).
# 2. Preparation

## 1. Env configuration (`.env` file)

You must prepare the `.env`  using a `.env.example` and edit it to match your environment.

**Key sections to edit:**
 - **General Settings:** Set `ADMIN_USER` to your main non-root user. The `MANAGEMENT_DIR` and other paths are based on this.
 - **Storage Settings:**
   - `ZFS_PARENT_DATASET`: The name of your parent ZFS dataset (e.g., `datapool/services`).
   - `ZFS_BASE_MOUNTPOINT`: The *directory* where that dataset is mounted (e.g., `/datapool/services`).
 - **Backup Settings:**
   - `BORG_REPO_BASE_PATH`: The remote SSH path to your Borg backup location.
   - `BORG_PASSPHRASE`: The encryption passphrase for your backups.
   - `BORG_RSH`: The full SSH command, including the path to the **private SSH key** that can access your backup server. This key must be accessible by the `root` user (as the script runs via `sudo`).
 - **Storage & Permissions (UserNS Remap):**
   - You can typically leave the `REMAPPED_..._UID` values as they are. These define the high-numbered UIDs that will be used for your containers.
 - **Service Definitions:**
   - `SERVICE_VOLUME_PATHS_AND_OWNERS`: This is a crucial multi-line list. For every persistent volume in your Docker services, you must add a line here.
   - **Format:** `relative/path/from/base:UID_KEY`
   - **Example:** `photo/immich-postgres:REMAPPED_POSTGRES_UID` tells the `storage_manager` to:
    1. Create the directory `/datapool/services/photo/immich-postgres`.
    2. `chown` this directory to the UID specified by `REMAPPED_POSTGRES_UID` (which is `100999`).

## 2. Copy the `management` folder into the Guest

You need to have all the files and scripts prepared on the Guest to manage the system.

The easiest way is to use `rsync`, which allows to keep syncronized the `management` directory when an update is made.

**Super simple example of rsync command:**
```bash
rsync -avh \
--exclude ".git" \
--exclude ".venv" \
--exclude "__pycache__" \
--exclude "*.pyc" \
--exclude ".DS_Store" \
./management homelab:~/
```

In this example `homelab` represent the host that was prepared on MacOS in the [1_host_preparation_and_setup](../0_host/1_host_preparation_and_setup.md) section.

## 3. Installation

Once your `.env` file is complete, run the `install` command:

```bash
make install
```

1. Runs `sudo apt-get update` and `upgrade`.
2. Installs the system dependencies (`borgbackup`, `zfsutils-linux`, etc...).
3. Creates a Python virtual environment at the path specified by `VENV_DIR` (e.g., `/home/manager/management/python/.venv`).
4. Installs the required Python packages from `requirements.txt` into that virtual environment.
5. Sets executable permissions on the scripts.

## 4. Finish

Everything should be set, and ready to be used.
# 3. Usage

You interact with the system using `make` commands. The `Makefile` automatically finds the Python virtual environment and runs the `orchestrator.py` script with `sudo`.

### One-Time Setup

After installation, you **must** run the storage setup.

```bash
make setup-storage
```

This command runs the `storage_manager.py` logic to create all your ZFS datasets, create the necessary host users for UserNS remapping, and apply the correct `chown` and `chmod` permissions to all your service directories.

### Daily Docker Management

 - `make docker-up`: Builds, creates, and starts all services.
 - `make docker-down`: Stops and removes all service containers.
 - `make docker-stop`: Stops all services without removing them (useful for backups).
 - `make docker-start`: Restarts services that were stopped.

### Backup & Restore

 - `make backup-all`: Runs the entire orchestrated backup process.
 - `make list-archives SERVICE_NAME="photo"`: Lists all Borg archives for the "photo" service.
 - `make extract-archive SERVICE_NAME="photo" ARCHIVE_NAME="..." DESTINATION="/tmp/restore"`: Restores a specific archive to a destination.

### ZFS Snapshot Management

 - `make snapshot-all SNAPSHOT_NAME="my-manual-snapshot"`: Creates a recursive snapshot of *all* services with a custom name.
 - `make snapshot-one SERVICE_NAME="fun" SNAPSHOT_NAME="pre-update"`: Creates a snapshot for a single service.
 - `make list-snapshots-all`: Lists all snapshots on the parent dataset.
# Architecture

The homelab's design is built on a **layered philosophy**. Responsibilities are split across distinct hardware, guest, and service layers.

**Guiding Principles:**

Across all layers, the architecture is guided by three principles:

  - **Host Independence**: The host should have as few responsibilities as possible. It only runs the hypervisor and provides encrypted storage. Any host machine could be swapped out, and the lab would continue to function after restoring the VMs.
  - **Data is Paramount**: Data is the most valuable asset. The configuration for services (`docker-compose` files) is version-controlled in a Git repository. The persistent application data is stored on dedicated SSDs and backed up independently by the guest. Everything else can be easily recreated.
  - **Layered Responsibility**: Each layer has a clear and distinct job. The Host provides the hardware foundation, the Guest provides the operating environment and data backup, and the Services layer runs the applications. This separation makes the system easier to manage, troubleshoot, and scale.

-----

## The Host Layer: Physical Machine

This is the physical machine that underpins the entire homelab. The goal here is to create a stable and secure foundation for running the virtual machines.

The stack consists of:

  - **Host OS**: macOS
  - **Virtualization**: VMware Fusion
  - **Storage**: Dedicated, encrypted external SSDs

-----

## The Guest Layer: Virtual Machines

This layer uses a **multi-VM philosophy**, splitting tasks across several virtual machines instead of running everything in one place.

### **1. DNS & Network VM**

This is a lightweight, independent virtual machine dedicated to a single task: **DNS resolution** for the entire network. By isolating this service, the rest of the home network remains functional even if the main services VM is rebooting or offline. It's designed to be **"fire-and-forget"**; the setup is minimal, and a simple VM snapshot or a "cold backup" is sufficient for recovery.

### **2. Services VM**

This is the main workhorse of the homelab. It's a Debian VM specifically designed to run all containerized applications via Docker. It is also responsible for handling the primary data backups.

-----

## The Services Layer: Applications

This layer defines how all the docker containerized applications run and communicate securely using a **"hub-and-spoke" architecture**.

-----

## Backup & Recovery Strategy

The backup strategy mirrors the layered architecture, assigning distinct roles to the Guest and Host layers to ensure both data integrity and rapid disaster recovery.

### Host Layer: Disaster Recovery

The **Host (macOS)** layer handles disaster recovery. Using a dedicated tool (e.g. **Borg Backup**, **Time Machine** or **rsync**), it creates "cold" backups of the entire VM disk file (`.vmwarevm`) to a separate external drive. This goal is **bare-metal disaster recovery**, allowing for a full restore if the primary drive fails or the VM becomes unrecoverable.

### Guest Layer: Primary Data Backup

The **Services VM (Debian)** handles application data backup. The backup strategy is built on a combination of **ZFS snapshots** and **BorgBackup**, designed to capture perfectly consistent data with only seconds of service downtime. The architecture is uniquely granular, isolating each service into its own dedicated backup repository. This enhances resilience and allows for custom retention policies per application.
