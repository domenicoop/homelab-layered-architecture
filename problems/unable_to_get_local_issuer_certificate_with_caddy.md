# SSL certificate problem: unable to get local issuer certificate" with Caddy

This guide explains how to solve a common problem where `git` on the command line fails with an SSL error, even when the same HTTPS site (like a self-hosted Gitea) works perfectly in your browser.

You try to clone, pull, or push to your self-hosted Git server and receive this error:

```
fatal: unable to access '[https://git.homelab.lan/admin/archive_family.git/](https://git.homelab.lan/admin/archive_family.git/)': SSL certificate problem: unable to get local issuer certificate
```

This is especially confusing because when you open `https://git.homelab.lan` in your browser (like Safari or Chrome), you see a valid HTTPS connection (you may have had to click "Trust" or "Proceed" on your first visit).

## The Core Reason: A Mismatch in Trust

The problem is a mismatch between two different **Trust Stores** on your computer.

1. **Caddy's `tls internal`:** In your Caddyfile, you are using `tls internal`. This tells Caddy *not* to get a public certificate from an authority like Let's Encrypt. Instead, Caddy creates its **own private Certificate Authority (CA)** and uses it to sign a certificate for `git.homelab.lan`.

2. **Your Browser (Safari):** When you first visited `https://git.homelab.lan`, your browser showed a big security warning. You clicked a button like "Show Details" -> "Visit this Website" -> "Trust". This action added Caddy's private CA to your **macOS Keychain** (or your browser's trust store) and marked it as trusted.

3. **Your Command Line (Git):** `git` (and other command-line tools like `curl`) **does not use the macOS Keychain** by default. It uses its own system-level list of trusted CAs. Since your Caddy's private CA isn't on this public list, `git` cannot verify the certificate. It only sees a certificate signed by an "unknown issuer" and correctly, from its perspective, aborts the connection for security.

---

## The Solutions

Here are the solutions, from most recommended to least recommended.

### Solution 1 (Recommended): Tell Git to Trust Your Caddy CA

This is the cleanest and most specific fix. You will export the Caddy root CA certificate and tell `git` to trust it.

**Step 1: Get the Root CA Certificate from Caddy**

Your Caddy container stores its root CA in its data volume. You can copy it from the running container to your local machine.

```bash
# Replace 'reverseproxy-caddy' with your Caddy container's name
# This copies the root CA to your current directory
docker cp reverseproxy-caddy:/data/caddy/pki/authorities/local/root.crt .
```

You should now have a `root.crt` file. It's a good idea to move this to a permanent location, like `~/.ssl/caddy_root.crt`.

**Step 2: Configure Git to Use This Certificate**

Now, tell `git` to use this file as part of its SSL verification:

```bash
# We use 'git config --global' to set this for all projects
git config --global http.sslCAInfo /path/to/your/root.crt
```

**⚠️ Important:** You **must** use the **full, absolute path** to the file (e.g., `/Users/yourname/ssl/caddy_root.crt` or `/home/yourname/.ssl/caddy_root.crt`).

If you use a relative path (like `root.crt`), `git` won't find it, and you will get this follow-up error:

```
fatal: unable to access '...': error setting certificate verify locations:
CAfile: root.crt
CApath: none
```

To fix the "file not found" error, simply re-run the `git config` command with the correct, full, absolute path.

### Solution 2 (Also Good): Trust the CA System-Wide (for macOS)

This solution adds the Caddy CA to your **System** Keychain, which makes most command-line tools on your Mac (including `git`) trust it automatically.

1.  **Get the `root.crt` file** (using the `docker cp` command from Solution 1).
2.  Open the **Keychain Access** app on your Mac.
3.  In the sidebar, select the **"System"** keychain (not "login").
4.  Drag your `root.crt` file and drop it onto the list of certificates. You will need to enter your admin password.
5.  Find the certificate you just added (it will be named something like "Caddy Local Authority").
6.  Double-click it to open the info window.
7.  Expand the **"Trust"** section.
8.  Change the "When using this certificate:" setting to **"Always Trust"**.
9.  Close the window (you'll be prompted for your password again).

Your command-line `git` should now work without any special configuration.
