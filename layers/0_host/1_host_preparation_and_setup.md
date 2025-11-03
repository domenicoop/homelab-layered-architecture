# 1. Host Preparation and Setup

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
