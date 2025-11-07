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
