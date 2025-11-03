# 2. Preparation

## 1. Env configuration (`.env` file)

You must prepare the `.env`  using a `.env.example` and edit it to match your environment.

**Key sections to edit:**
 - **General Settings:** Set `ADMIN_USER` to your main non-root user. The `MANAGEMENT_DIR` and other paths are based on this.
 - **Storage Settings:**
   - `ZFS_PARENT_DATASET`: The name of your parent ZFS dataset (e.g., `datapool/services`).
   - `ZFS_BASE_MOUNTPOINT`: The *directory* where that dataset is mounted (e.g., `/datapool/services`).
 - **Backup Settings:**
   - `BORG_REPO_BASE_PATH`: The remote SSH path to your Borg backup location.
   - `BORG_PASSPHRASE`: The encryption passphrase for your backups.
   - `BORG_RSH`: The full SSH command, including the path to the **private SSH key** that can access your backup server. This key must be accessible by the `root` user (as the script runs via `sudo`).
 - **Storage & Permissions (UserNS Remap):**
   - You can typically leave the `REMAPPED_..._UID` values as they are. These define the high-numbered UIDs that will be used for your containers.
 - **Service Definitions:**
   - `SERVICE_VOLUME_PATHS_AND_OWNERS`: This is a crucial multi-line list. For every persistent volume in your Docker services, you must add a line here.
   - **Format:** `relative/path/from/base:UID_KEY`
   - **Example:** `photo/immich-postgres:REMAPPED_POSTGRES_UID` tells the `storage_manager` to:
    1. Create the directory `/datapool/services/photo/immich-postgres`.
    2. `chown` this directory to the UID specified by `REMAPPED_POSTGRES_UID` (which is `100999`).

## 2. Copy the `management` folder into the Guest

You need to have all the files and scripts prepared on the Guest to manage the system.

The easiest way is to use `rsync`, which allows to keep syncronized the `management` directory when an update is made.

**Super simple example of rsync command:**
```bash
rsync -avh \
--exclude ".git" \
--exclude ".venv" \
--exclude "__pycache__" \
--exclude "*.pyc" \
--exclude ".DS_Store" \
./management homelab:~/
```

In this example `homelab` represent the host that was prepared on MacOS in the [1_host_preparation_and_setup](../0_host/1_host_preparation_and_setup.md) section.

## 3. Installation

Once your `.env` file is complete, run the `install` command:

```bash
make install
```

1. Runs `sudo apt-get update` and `upgrade`.
2. Installs the system dependencies (`borgbackup`, `zfsutils-linux`, etc...).
3. Creates a Python virtual environment at the path specified by `VENV_DIR` (e.g., `/home/manager/management/python/.venv`).
4. Installs the required Python packages from `requirements.txt` into that virtual environment.
5. Sets executable permissions on the scripts.

## 4. Finish

Everything should be set, and ready to be used.
