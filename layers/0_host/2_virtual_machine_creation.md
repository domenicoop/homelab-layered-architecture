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
