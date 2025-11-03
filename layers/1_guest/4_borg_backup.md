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
