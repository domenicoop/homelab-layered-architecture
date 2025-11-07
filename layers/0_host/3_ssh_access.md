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
