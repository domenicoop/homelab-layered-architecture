# 6. Automation

The "automation" layer is a collection of scripts that provides an integrated automation system for managing the homelab server. Its primary purpose is to **orchestrate Docker Compose services, ZFS storage, and Borg backups** in a consistent manner.

This automation layer is a **living project**. It's not perfect, but usable.

## Why we need Automation

Imagine managing a server with multiple Dockerized applications, each requiring specific storage configurations, permissions, regular backups, and system updates. Manually performing these tasks would involve:

- **Dozens of Shell Commands:** Remembering commands like: `useradd`, `chown`, `zfs create`, `borg init`, `docker compose up`, `apt update`; with precise arguments and paths.
- **Sequential Dependencies:** Ensuring commands are run in the correct order (e.g., stopping services *before* a snapshot, installing packages *before* running Python scripts).
- **Error Proneness:** A single typo in a path, a forgotten flag, or an incorrect user ID could lead to failed services, corrupted data, or insecure configurations.
- **Time Consumption:** Daily or weekly maintenance routines would consume significant personal time.
- **Inconsistency:** Manual execution inherently leads to variations, making troubleshooting harder when issues arise.
