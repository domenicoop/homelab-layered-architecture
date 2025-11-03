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
