#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Orchestrates a ZFS-to-Borg backup process with DEDICATED repositories.

This script manages the high-level backup workflow:
1. Stops Docker services to ensure data consistency.
2. Creates a recursive ZFS snapshot.
3. Restarts Docker services immediately.
4. Iterates through each ZFS dataset, backing it up to its own Borg repo.
5. Cleans up the ZFS snapshot upon successful completion of all backups.

NOTE: This script is a high-level orchestrator. It does not directly use the
      'sh' library. Instead, it delegates all shell command responsibilities
      to the specialized manager classes. This separation of concerns is a
      best practice, and therefore, no refactoring of this file is needed.
"""

# --- STANDARD LIBRARY IMPORTS ---
import log_setup  # Ensure logging is configured before any other imports
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# --- THIRD-PARTY LIBRARY IMPORTS ---
from dotenv import load_dotenv

# --- LOCAL APPLICATION IMPORTS ---
# Import the managers for each specific responsibility.
from borg_backup_manager import BorgBackupRepoManager
from docker_manager import DockerComposeManager
from zfs_manager import ZFSDataset, ZFSManager

# --- CONFIGURATION & INITIALIZATION ---

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    datefmt="%Y-%m-%d %H:%M:%S",
)


@dataclass
class Config:
    """Manages and validates all configuration for the backup process."""

    repo_base_path: str
    passphrase: str
    rsh: str
    archive_prefix: str
    prune_policy: List[str]
    zfs_parent_dataset: str
    compression: str
    excludes_file: str
    base_borg_env: Dict[str, str] = field(init=False)

    def __post_init__(self):
        """Sets up the base environment dictionary needed by BorgBackupManager."""
        logging.info("Assembling base environment for Borg commands.")
        self.base_borg_env = os.environ.copy()
        self.base_borg_env.update(
            {"BORG_PASSPHRASE": self.passphrase, "BORG_RSH": self.rsh}
        )
        logging.info("Borg base environment configured successfully.")

    @classmethod
    def from_env(cls, env_path: Path) -> "Config":
        """Loads and validates all required configuration from a .env file."""
        logging.info(f"Loading configuration from environment file: {env_path}")
        if not env_path.exists():
            logging.error(f"Configuration file not found at: {env_path}")
            sys.exit(1)

        load_dotenv(dotenv_path=env_path, override=True)
        logging.info("Successfully loaded .env file.")

        required = [
            "BORG_REPO_BASE_PATH",
            "BORG_PASSPHRASE",
            "BORG_RSH",
            "ZFS_PARENT_DATASET",
            "ARCHIVE_PREFIX",
            "BORG_PRUNE_POLICY",
            "BORG_COMPRESSION",
            "BORG_EXCLUDES_FILE",
        ]

        logging.info("Validating required environment variables.")
        missing_vars = [var for var in required if not os.getenv(var)]
        if missing_vars:
            logging.error(
                f"Missing one or more required variables in {env_path}. "
                f"Check: {', '.join(missing_vars)}"
            )
            sys.exit(1)
        logging.info("All required environment variables are present.")

        logging.info("Configuration loaded and validated.")
        return cls(
            repo_base_path=os.getenv("BORG_REPO_BASE_PATH"),
            passphrase=os.getenv("BORG_PASSPHRASE"),
            rsh=os.getenv("BORG_RSH"),
            archive_prefix=os.getenv("ARCHIVE_PREFIX"),
            prune_policy=os.getenv("BORG_PRUNE_POLICY").split(),
            zfs_parent_dataset=os.getenv("ZFS_PARENT_DATASET"),
            compression=os.getenv("BORG_COMPRESSION"),
            excludes_file=os.getenv("BORG_EXCLUDES_FILE"),
        )


class BackupOrchestrator:
    """Coordinates the entire ZFS-to-Borg backup process."""

    def __init__(self, config: Config):
        """Initializes the orchestrator with configuration and service managers."""
        self.config = config
        self.zfs_manager = ZFSManager(config.zfs_parent_dataset)
        self.docker_manager = DockerComposeManager()
        self.snapshot_tag = self._generate_snapshot_tag()
        logging.info(f"Generated unique snapshot tag: {self.snapshot_tag}")

    def _generate_snapshot_tag(self) -> str:
        """Generates a unique tag for this backup run based on the current timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        return f"auto-backup_{timestamp}"

    def backup_all(self) -> None:
        """Executes the entire backup process, handling state and cleanup."""
        logging.info("====== Orchestrated Backup Process Starting ======")
        snapshot_created = False

        try:
            logging.info(
                "--> Step 1: Stopping all Docker services for data consistency."
            )
            self.docker_manager.stop_all()

            try:
                logging.info(
                    "--> Step 2: Creating recursive ZFS snapshot for all datasets."
                )
                self.zfs_manager.create_snapshot(self.snapshot_tag, recursive=True)
                snapshot_created = True
            finally:
                # This 'finally' block ensures services are always restarted,
                # even if snapshotting fails, minimizing downtime.
                logging.info("--> Bringing Docker services back online.")
                self.docker_manager.up_all()

            self._orchestrate_dataset_backups()

            logging.info(
                "--> Step 4: All backups successful. Cleaning up ZFS snapshot."
            )
            self.zfs_manager.destroy_snapshot(self.snapshot_tag, recursive=True)
            snapshot_created = False  # Mark as cleaned up

            logging.info(
                "====== Orchestrated Backup Process Finished Successfully ======"
            )

        except Exception as e:
            logging.critical("--- BACKUP FINISHED WITH AN UNRECOVERABLE ERROR ---")
            logging.critical(f"Error details: {e}", exc_info=True)
            if snapshot_created:
                logging.error(
                    f"The temporary snapshot '{self.snapshot_tag}' has been LEFT "
                    "for manual inspection due to the failure."
                )
            raise

    def _orchestrate_dataset_backups(self) -> None:
        """Finds all datasets and orchestrates the backup process for each one."""
        logging.info("--> Step 3: Discovering datasets and running Borg backups.")
        datasets = list(self.zfs_manager.get_datasets())

        if not datasets:
            raise RuntimeError(
                f"Found 0 mounted datasets to back up under '{self.config.zfs_parent_dataset}'."
            )

        logging.info(f"Discovered {len(datasets)} mounted datasets to process.")
        for i, dataset in enumerate(datasets, 1):
            logging.info(f"Processing dataset {i} of {len(datasets)}: {dataset.name}")
            self._backup_single_dataset(dataset)

        for i, dataset in enumerate(datasets, 1):
            logging.info(f"Checking repository {i} of {len(datasets)}: {dataset.name}")
            repo_path = self._get_repo_path(dataset)
            self._check_single_repository(repo_path)

        logging.info(f"Successfully processed all {len(datasets)} datasets.")

    def _backup_single_dataset(self, dataset: ZFSDataset) -> None:
        """Performs the backup and maintenance for a single ZFS dataset."""
        logging.info(f"--- Processing dataset: {dataset.name} ---")

        # Determine the Borg repository path for this dataset.
        repo_path = self._get_repo_path(dataset)

        # Define the exact path to the data inside the ZFS snapshot.
        snapshot_data_path = self._get_snapshot_path(dataset)

        # Define the archive name using the configured prefix and snapshot tag.
        archive_name = self._build_archive_name(
            self.config.archive_prefix, self.snapshot_tag
        )

        logging.info(
            f"Backing up dataset '{dataset.name}' to repository at: {repo_path}"
        )
        logging.info(f"Snapshot data path: {snapshot_data_path}")
        try:
            self._backup_single_snapshot(repo_path, archive_name, snapshot_data_path)
        except Exception as e:
            logging.error(
                f"Error occurred while processing dataset '{dataset.name}': {e}"
            )
            raise

        logging.info(
            f"--- Successfully finished processing dataset: {dataset.name} ---"
        )

    def _backup_single_snapshot(
        self, repo_path: str, archive_name: str, snapshot_data_path: Path
    ) -> None:
        """Performs the backup and maintenance for a single Borg repository."""
        logging.info(f"--- Processing Borg repository at: {repo_path} ---")
        # Create an instance of the Borg manager for this specific repository.
        borg_manager = BorgBackupRepoManager(repo_path, self.config.base_borg_env)

        # Run the sequence of Borg operations.
        borg_manager.initialize_if_needed()
        borg_manager.create_archive(
            archive_name,
            snapshot_data_path,
            self.config.compression,
            self.config.excludes_file,
        )
        borg_manager.prune_archives(self.config.prune_policy)

        logging.info(
            f"--- Successfully finished processing repository: {repo_path} ---"
        )

    def _check_single_repository(self, repo_path: str) -> None:
        """Checks the integrity of a single Borg repository."""
        logging.info(f"Checking integrity of Borg repository at: {repo_path}")
        borg_manager = BorgBackupRepoManager(repo_path, self.config.base_borg_env)
        borg_manager.check_repository()
        logging.info(f"Integrity check completed for repository: {repo_path}")

    def _get_repo_path(self, dataset: ZFSDataset) -> str:
        """Constructs the Borg repository path for a given dataset."""
        sanitized_name = dataset.name.replace("/", "_")
        return f"{self.config.repo_base_path}/{sanitized_name}"

    def _get_snapshot_path(self, dataset: ZFSDataset) -> Path:
        """Constructs the path to the snapshot data for a given dataset."""
        return Path(dataset.mount_point) / ".zfs" / "snapshot" / self.snapshot_tag

    def _build_archive_name(self, archive_prefix: str, snapshot_tag: str) -> str:
        """Generates a unique archive name using the given prefix and current timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        return f"{archive_prefix}_{snapshot_tag}_{timestamp}"


# --- MAIN EXECUTION ---


def main() -> None:
    """Main function to configure and run the backup orchestrator."""
    if os.geteuid() != 0:
        logging.error("This script must be run as root. Please use sudo.")
        sys.exit(1)
    logging.info("Root privileges check passed.")

    try:
        # Assumes the .env file is in the parent directory of this script's location.
        env_path = Path(__file__).resolve().parent.parent / ".env"
        config = Config.from_env(env_path)
        orchestrator = BackupOrchestrator(config)
        orchestrator.backup_all()
        sys.exit(0)  # Explicitly exit with success code.
    except Exception:
        # The specific error is already logged by the orchestrator's run method.
        # We just need to ensure the script exits with a failure code.
        sys.exit(1)


if __name__ == "__main__":
    main()
