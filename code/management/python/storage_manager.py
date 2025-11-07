#!/usr/bin/env python3

# ====================================================================================
#
#     Master Host Preparation Script for Docker Services with UserNS Remap
#
# ====================================================================================
#
# This script is now designed to be imported as a class (`StorageManager`) by an
# orchestrator, promoting code reuse and consistency. It uses the `sh` library
# for all shell commands, aligning it with the other manager components.
#
# It can still be run standalone for direct execution.
#
# ====================================================================================

import os
import sys
import log_setup
import logging

logging.getLogger(__name__)
from pathlib import Path

# --- Third-Party Imports ---
try:
    import sh
except ImportError:
    print("[ERROR] The 'sh' library is not installed. Please run: pip install sh")
    sys.exit(1)

# --- Local Imports ---
# To run standalone, these files must be in the same directory or in the PYTHONPATH
try:
    from zfs_manager import ZFSManager
except ImportError:
    # This allows standalone execution if managers are in a different path
    pass

# --- INITIALIZATION ---
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


class StorageManager:
    """
    Prepares the host environment for Docker services with UserNS Remap.
    This includes creating users, groups, ZFS datasets, and setting permissions.
    """

    def __init__(self, config: object, zfs_manager: "ZFSManager"):
        """
        Initializes the StorageManager with configuration and a ZFSManager instance.

        Args:
            config (object): A configuration object with attributes from the .env file.
            zfs_manager (ZFSManager): An instance of the ZFSManager for dataset operations.
        """
        self.config = config
        self.zfs = zfs_manager
        self.service_volume_paths_and_owners = self._parse_service_definitions()

        # Initialize base commands without baking or special arguments.
        # Error handling will be managed by try/except blocks.
        self.sudo = sh.sudo
        self.getent = sh.getent
        self.id = sh.id

        logging.info("StorageManager initialized.")

    def _parse_service_definitions(self) -> dict:
        """Parses the multi-line service definition string from the config."""
        definitions_str = getattr(self.config, "service_volume_paths_and_owners", "")
        if not definitions_str.strip():
            logging.error(
                "SERVICE_VOLUME_PATHS_AND_OWNERS is not defined in the .env file."
            )
            sys.exit(1)

        uid_map = {
            "REMAPPED_ROOT_UID": int(self.config.remapped_root_uid),
            "REMAPPED_POSTGRES_UID": int(self.config.remapped_postgres_uid),
            "REMAPPED_APP_UID": int(self.config.remapped_app_uid),
        }

        parsed_definitions = {}
        for line in definitions_str.strip().split("\n"):
            line = line.strip()
            if not line or ":" not in line:
                continue
            path, uid_key = [item.strip() for item in line.split(":", 1)]
            if uid_key not in uid_map:
                logging.error(f"Invalid UID key '{uid_key}' for path '{path}'.")
                sys.exit(1)
            parsed_definitions[path] = uid_map[uid_key]
        return parsed_definitions

    # --- Idempotency Check Helper Methods ---
    def _user_exists(self, username: str) -> bool:
        """Checks if a user exists using the 'getent' command for consistency."""
        try:
            # getent returns exit code 2 if the user does not exist. We treat this as "OK".
            self.getent("passwd", username, _ok_code=[0, 2])
            return True
        except sh.ErrorReturnCode:
            return False

    def _group_exists(self, groupname: str) -> bool:
        """Checks if a group exists using the 'getent' command for consistency."""
        try:
            # getent returns exit code 2 if the group does not exist. We treat this as "OK".
            self.getent("group", groupname, _ok_code=[0, 2])
            return True
        except sh.ErrorReturnCode:
            return False

    def _is_user_in_group(self, username: str, groupname: str) -> bool:
        """Checks if a user is a member of a group using the 'id' command."""
        try:
            groups_output = self.id("-nG", username, _text=True)
            return groupname in groups_output.strip().split()
        except sh.ErrorReturnCode:
            return False

    # --- Main Logic Methods ---

    def _configure_subids(self):
        """STEP 1: Configure Subordinate UID/GID Mappings."""
        logging.info(
            f"[STEP 1/7] Configuring subordinate UID/GID mappings for '{self.config.docker_user}'..."
        )
        mapping = f"{self.config.docker_user}:{self.config.remapped_root_uid}:65536"

        for sub_file_path_str in ["/etc/subuid", "/etc/subgid"]:
            sub_file = Path(sub_file_path_str)
            sub_file.touch(exist_ok=True)
            if mapping in sub_file.read_text():
                logging.info(f"--> Mapping already exists in {sub_file_path_str}.")
            else:
                logging.info(f"--> Adding mapping to {sub_file_path_str}...")
                # Use explicit, unambiguous calling syntax.
                self.sudo("tee", "-a", sub_file_path_str, _in=f"{mapping}\n")

    def _setup_shared_group(self):
        """STEP 2: Establish a Shared Group."""
        logging.info(
            f"[STEP 2/7] Configuring shared group '{self.config.shared_group}'..."
        )
        if not self._group_exists(self.config.shared_group):
            logging.info(f"--> Creating group: '{self.config.shared_group}'...")
            # Use explicit, unambiguous calling syntax.
            self.sudo("groupadd", self.config.shared_group)
        else:
            logging.info(f"--> Group '{self.config.shared_group}' already exists.")

        if not self._is_user_in_group(self.config.admin_user, self.config.shared_group):
            logging.info(
                f"--> Adding user '{self.config.admin_user}' to group '{self.config.shared_group}'..."
            )
            # Use explicit, unambiguous calling syntax.
            self.sudo(
                "usermod", "-aG", self.config.shared_group, self.config.admin_user
            )
        else:
            logging.info(f"--> User '{self.config.admin_user}' already in group.")

    def _create_mirrored_users(self):
        """STEP 3: Create Host Users that Mirror Container UIDs."""
        logging.info("[STEP 3/7] Creating mirrored host users for remapped UIDs...")
        users_to_create = {
            self.config.docker_user: self.config.remapped_root_uid,
            "docker_user_999": self.config.remapped_postgres_uid,
            "docker_user_1000": self.config.remapped_app_uid,
        }
        for username, uid in users_to_create.items():
            if not self._user_exists(username):
                logging.info(f"--> Creating system user '{username}' with UID {uid}...")
                # Use explicit, unambiguous calling syntax.
                self.sudo(
                    "useradd",
                    "--system",
                    "--no-create-home",
                    "--uid",
                    uid,
                    "--gid",
                    self.config.shared_group,
                    username,
                )
            else:
                logging.info(f"--> User '{username}' (UID {uid}) already exists.")

    def _create_zfs_datasets(self):
        """STEP 4: Create ZFS Datasets for Each Service using ZFSManager."""
        logging.info("[STEP 4/7] Creating ZFS datasets for each service...")
        service_names = sorted(
            list({path.split("/")[0] for path in self.service_volume_paths_and_owners})
        )
        for service_name in service_names:
            self.zfs.create_dataset(service_name)
        logging.info("--> All ZFS service datasets are configured.")

    def _create_nested_dirs(self):
        """STEP 5: Create Nested Directories."""
        logging.info(
            "[STEP 5/7] Creating nested directories within ZFS service datasets..."
        )
        base_path = Path(self.config.zfs_base_mountpoint)
        for rel_path in self.service_volume_paths_and_owners.keys():
            full_path = base_path / rel_path
            if not full_path.exists():
                logging.info(f"--> Creating directory: '{full_path}'")
                full_path.mkdir(parents=True, exist_ok=True)
            else:
                logging.info(f"--> Directory '{full_path}' already exists.")

    def _apply_ownership(self):
        """STEP 6: Apply Correct Ownership Recursively."""
        logging.info("[STEP 6/7] Applying specific ownership to directories...")
        base_path = Path(self.config.zfs_base_mountpoint)
        for rel_path, owner_uid in self.service_volume_paths_and_owners.items():
            full_path = str(base_path / rel_path)
            logging.info(
                f"--> Ensuring ownership for '{full_path}' is UID:{owner_uid} Group:'{self.config.shared_group}'."
            )
            # Use explicit, unambiguous calling syntax.
            self.sudo(
                "chown", "-R", f"{owner_uid}:{self.config.shared_group}", full_path
            )
        logging.info("--> Ownership applied successfully.")

    def _enforce_group_inheritance(self):
        """STEP 7: Enforce Group Inheritance (setgid)."""
        logging.info("[STEP 7/7] Applying group inheritance ('setgid') recursively...")
        base_path = Path(self.config.zfs_base_mountpoint)
        top_level_paths = sorted(
            list(
                {
                    str(base_path / p.split("/")[0])
                    for p in self.service_volume_paths_and_owners.keys()
                }
            )
        )
        for dir_path in top_level_paths:
            logging.info(
                f"--> Enforcing 'setgid' on '{dir_path}' and its subdirectories."
            )
            # Use explicit, unambiguous calling syntax.
            self.sudo(
                "find", dir_path, "-type", "d", "-exec", "chmod", "g+s", "{}", "+"
            )
        logging.info("--> Group inheritance enforced on all service directories.")

    def prepare_host(self):
        """
        Executes all the host preparation steps in the correct order.
        """
        if os.geteuid() != 0:
            logging.error("This operation must be run as root. Please use sudo.")
            sys.exit(1)

        logging.info("--- Starting Host Environment Setup ---")
        try:
            self._configure_subids()
            self._setup_shared_group()
            self._create_mirrored_users()
            self._create_zfs_datasets()
            self._create_nested_dirs()
            self._apply_ownership()
            self._enforce_group_inheritance()
        except sh.ErrorReturnCode as e:
            # This block will now correctly catch any command that fails (returns a non-zero exit code).
            logging.error(f"\n[FATAL] A command failed, halting execution.")
            logging.error(f"--> Command: '{e.full_cmd}'")
            logging.error(f"--> Stderr: {e.stderr.decode().strip()}")
            sys.exit(1)

        logging.info("\n--- Host Environment Setup Complete ---")
        logging.info(
            "Sub-ID mappings, users, groups, ZFS datasets, and permissions are configured."
        )


def main():
    """Standalone execution function for running this script directly."""
    from orchestrator import Config as OrchestratorConfig

    if os.geteuid() != 0:
        print("This script must be run as root. Please use sudo.", file=sys.stderr)
        sys.exit(1)

    print("Running StorageManager in standalone mode...")

    env_path = Path(__file__).resolve().parent.parent / ".env"
    config = OrchestratorConfig(env_path)
    zfs_manager = ZFSManager(config.zfs_parent_dataset)

    storage_manager = StorageManager(config, zfs_manager)
    storage_manager.prepare_host()


if __name__ == "__main__":
    main()
