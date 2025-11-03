# 3. Usage

You interact with the system using `make` commands. The `Makefile` automatically finds the Python virtual environment and runs the `orchestrator.py` script with `sudo`.

### One-Time Setup

After installation, you **must** run the storage setup.

```bash
make setup-storage
```

This command runs the `storage_manager.py` logic to create all your ZFS datasets, create the necessary host users for UserNS remapping, and apply the correct `chown` and `chmod` permissions to all your service directories.

### Daily Docker Management

 - `make docker-up`: Builds, creates, and starts all services.
 - `make docker-down`: Stops and removes all service containers.
 - `make docker-stop`: Stops all services without removing them (useful for backups).
 - `make docker-start`: Restarts services that were stopped.

### Backup & Restore

 - `make backup-all`: Runs the entire orchestrated backup process.
 - `make list-archives SERVICE_NAME="photo"`: Lists all Borg archives for the "photo" service.
 - `make extract-archive SERVICE_NAME="photo" ARCHIVE_NAME="..." DESTINATION="/tmp/restore"`: Restores a specific archive to a destination.

### ZFS Snapshot Management

 - `make snapshot-all SNAPSHOT_NAME="my-manual-snapshot"`: Creates a recursive snapshot of *all* services with a custom name.
 - `make snapshot-one SERVICE_NAME="fun" SNAPSHOT_NAME="pre-update"`: Creates a snapshot for a single service.
 - `make list-snapshots-all`: Lists all snapshots on the parent dataset.
