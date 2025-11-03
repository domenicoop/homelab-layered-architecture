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
