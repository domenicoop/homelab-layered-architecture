# 1. Components

The system is built around a central Python **orchestrator** (`orchestrator.py`). This orchestrator calls specialized "manager" classes, each responsible for a specific task (e.g., `ZFSManager` for ZFS commands, `DockerComposeManager` for Docker).

A `Makefile` is provided as a simple, user-friendly wrapper, translating easy-to-remember commands like `make backup-all` into the correct Python script calls with the necessary permissions.

---

## Component Breakdown

The automation is divided into several files, each with a clear responsibility:

**`Makefile`**
- The primary **user-friendly entry point**. It provides simple, memorable commands (e.g., `make setup-storage`, `make docker-up`) that handle running the main orchestrator script with `sudo` and the correct Python environment.

**`orchestrator.py`**
- The **master orchestrator** and central "brain" of the system. It parses the command-line arguments and calls the appropriate manager classes in the correct sequence to perform complex tasks.

**`.env.example`**
* The template for your configuration. You **must** use this to create the `.env` file and fill in your specific details.

**`docker_manager.py`**
- Defines the `DockerComposeManager` class. This script scans the `SERVICES_DIR` (defined in your `.env`) to find all `docker-compose.yml` files and executes Docker Compose commands on them (e.g., `up`, `down`, `pull`).

**`zfs_manager.py`**
- Defines the `ZFSManager` class. This is a Python wrapper for `sudo zfs` commands. It handles creating and destroying datasets and, most importantly, creating and destroying recursive snapshots.

**`storage_manager.py`**
- Defines the `StorageManager` class. This is a critical **one-time setup** script. It reads the `SERVICE_VOLUME_PATHS_AND_OWNERS` from your `.env` and performs all the necessary steps to configure the host for secure UserNS remapping (creating users, setting permissions, etc.).

**`backup_manager.py`**
- Defines the `BackupOrchestrator` class. This script defines the **high-level backup workflow** (stop services, snapshot, start services, loop through datasets, and back them up).

**`borg_backup_manager.py`**
- Defines the `BorgBackupRepoManager` class. This is a low-level wrapper for `sudo borg` commands. It handles initializing repositories, creating archives, pruning old backups, and checking repository integrity.

**`requirements.txt`**
- A list of the required Python libraries (e.g., `sh`, `python-dotenv`, `PyYAML`).
