# Fixing ZFS Pool Import Failures on Boot

This guide explains the common ZFS import failures seen during boot, especially in virtual machines (VMs), and provides a step-by-step resolution.

## 1. What Was the Problem?

The initial error message `[FAILED] Failed to start zfs-import-cache.service` indicates that your system tried to import your ZFS storage pools during boot but failed.

This service, `zfs-import-cache.service`, relies on a cache file (located at `/etc/zfs/zpool.cache`) that contains a "map" of your ZFS pools and the disks they belong to. When your system starts, this service reads the map and expects to find those exact disks.

The failure means that when the service ran, the disks listed in its map were not yet visible to the operating system.

-----

## 2. Why Did This Happen?

This problem is extremely common in virtual machines and is caused by a **race condition** during the boot process.

1. **System Boots:** You start your VM.
2. **Services Start:** The operating system begins starting all its essential services in parallel.
3. **ZFS Tries to Import:** The `zfs-import-cache.service` starts very early in this process.
4. **VM Disks are Slow:** In a virtual environment, virtual hard disks often take a few extra seconds to be fully initialized and presented to the guest OS.
5. **The "Race":** The `zfs-import-cache.service` starts *before* the virtual disks are ready. It looks for the disks in its cache map, finds nothing, and gives up, marking itself as `[FAILED]`.

A few seconds later, the virtual disks finally appear, but by then, the import service has already failed, and your ZFS pools remain offline.

-----

## 3. How Was It Resolved?

The solution has two main parts: first, switching to a more reliable import service, and second, clearing a conflicting configuration file that prevents the new service from running.

### Step 1: Switch to the Robust Scan Service

Instead of relying on a static (and brittle) cache map, the `zfs-import-scan.service` actively scans your system's devices to *find* any available ZFS pools. This method is slightly slower but much more reliable in a VM.

1. **Disable** the failing cache-based service:
  ```bash
  sudo systemctl disable zfs-import-cache.service
  ```
2. **Enable** the more reliable scan-based service:
  ```bash
  sudo systemctl enable zfs-import-scan.service
  ```

### Step 2: What If It *Still* Fails?

After rebooting from Step 1, you might find the pool is *still* not imported, even though the original `[FAILED]` message is gone.

This is what we diagnosed. The pool was still offline, and `sudo zpool status` showed `no pools available`.

#### Diagnosis

We checked the status of the new service we just enabled:

```bash
sudo systemctl status zfs-import-scan.service
```

This revealed the "smoking gun":

```
○ zfs-import-scan.service - Import ZFS pools by device scanning
   Loaded: loaded (...)
   Active: inactive (dead)
 Condition: start condition unmet ...
      └─ ConditionFileNotEmpty=!/etc/zfs/zpool.cache was not met
```

#### The Root Cause

That `ConditionFileNotEmpty` line means the `zfs-import-scan.service` is designed to **only run if the cache file (`/etc/zfs/zpool.cache`) does NOT exist**.

This is a safety feature to prevent both the "cache" and "scan" services from trying to import the pools at the same time. Because we had disabled the `zfs-import-cache` service, and the *existence* of the cache file *prevented* the `zfs-import-scan` service from starting, **neither service was running.**

#### The Final Solution

The fix is to remove the conflicting cache file, which will finally allow the `zfs-import-scan.service` to do its job.

1. **Remove the ZFS cache file:**

  ```bash
  sudo rm /etc/zfs/zpool.cache
  ```

2. **Reboot your VM:**

  ```bash
  sudo reboot
  ```

When the VM comes back online, the `ConditionFileNotEmpty` check will pass, `zfs-import-scan.service` will run, it will scan for and find your `datapool`, and it will import it automatically.
