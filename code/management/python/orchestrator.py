#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Master Orchestrator for Homelab Management

This script serves as the primary entry point for all management tasks,
replicating and replacing the functionality of the original Makefile. It uses
the dedicated Python manager classes (ZFS, Docker, Borg, etc.) to perform
all operations, providing a robust, maintainable, and Python-native CLI.

Usage: python orchestrator.py <command> [options]
Example: python orchestrator.py snapshot-one --service-name fun --snapshot-name before-update
"""

# --- STANDARD LIBRARY IMPORTS ---
import argparse
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import log_setup  # Ensure logging is configured before any other imports
import logging
import time

# --- THIRD-PARTY LIBRARY IMPORTS ---
from dotenv import load_dotenv

try:
    import sh
except ImportError:
    print("[ERROR] The 'sh' library is not installed. Please run: pip install sh")
    sys.exit(1)

# --- LOCAL APPLICATION IMPORTS ---
# These are assumed to be in the same directory or Python path
from backup_manager import BackupOrchestrator, Config as BackupConfig

# Updated import to include the high-level manager
from borg_backup_manager import BorgBackupRepoManager
from docker_manager import DockerComposeManager
from zfs_manager import ZFSManager
from storage_manager import StorageManager
from system_manager import SystemManager


# --- CONFIGURATION & INITIALIZATION ---

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


class Config:
    """Loads and centralizes all configuration from the .env file."""

    def __init__(self, env_path: Path):
        logging.info(f"Loading configuration from: {env_path}")
        if not env_path.exists():
            logging.error(f"Configuration file not found at: {env_path}")
            sys.exit(1)
        load_dotenv(dotenv_path=env_path, override=True)

        # Dynamically load all variables from the .env file as attributes
        for key, value in os.environ.items():
            setattr(self, key.lower(), value)

        self._validate_required_vars()
        self._setup_derived_vars()
        logging.info("Configuration loaded and validated successfully.")

    def _validate_required_vars(self):
        """Ensure critical variables are present."""
        required = [
            "python_dir",
            "zfs_parent_dataset",
            "zfs_base_mountpoint",
            "borg_repo_base_path",
            "borg_passphrase",
            "borg_rsh",
            "borg_compression",
            "borg_excludes_file",
            "borg_keys_dir",
            "admin_user",
        ]
        missing = [var for var in required if not hasattr(self, var)]
        if missing:
            logging.error(
                f"Missing required environment variables: {', '.join(missing)}"
            )
            sys.exit(1)

    def _setup_derived_vars(self):
        """Create composite variables needed by managers."""
        self.base_borg_env: Dict[str, str] = {
            "BORG_PASSPHRASE": self.borg_passphrase,
            "BORG_RSH": self.borg_rsh,
        }
        self.venv_dir: Path = Path(self.python_dir) / ".venv"


class MasterOrchestrator:
    """
    Coordinates all management tasks by calling the appropriate manager classes.
    """

    def __init__(self, config: Config):
        self.config = config
        self.zfs = ZFSManager(config.zfs_parent_dataset)
        self.docker = DockerComposeManager()
        self.storage = StorageManager(config, self.zfs)
        self.system = SystemManager()

    # --- Core Management ---

    def setup_storage(self):
        """Prepares storage: ZFS datasets, users, and permissions."""
        logging.info("--> Preparing ZFS datasets and permissions...")
        self.docker.down_all()
        self.storage.prepare_host()
        logging.info("--- Storage setup complete. ---")

    # --- Backup Management ---

    def init_backup(self):
        """Initializes Borg repos for all services."""
        logging.info("--> Initializing Borg repositories...")
        for dataset in self.zfs.get_datasets():
            borg_repo = self._get_borg_manager_for_dataset(dataset.name)
            borg_repo.initialize_if_needed()
        logging.info("--- All Borg repositories initialized. ---")

    def backup_all(self):
        """Runs the main backup process for all services."""
        logging.info("--> Starting the main backup process for all services...")

        self.docker.stop_all()

        env_path = Path(__file__).resolve().parent.parent / ".env"
        backup_config = BackupConfig.from_env(env_path)
        backup_orchestrator = BackupOrchestrator(backup_config)
        backup_orchestrator.backup_all()

    # --- Borg Commands ---

    def analyze_all_repos(self):
        """Analyzes all repositories corresponding to ZFS services and displays their stats."""
        logging.info("--> Analyzing all Borg repositories based on ZFS datasets...")

        datasets = list(self.zfs.get_datasets())
        if not datasets:
            logging.warning(
                "No ZFS datasets found to analyze corresponding Borg repositories."
            )
            return

        logging.info(
            f"Found {len(datasets)} ZFS datasets. Analyzing corresponding repositories..."
        )

        for i, dataset in enumerate(datasets):
            # Extract service name from dataset name (e.g., 'datapool/services/fun' -> 'fun')
            service_name = Path(dataset.name).name

            logging.info(f"\n{'#' * 80}")
            logging.info(
                f"Analyzing repository for service {i + 1}/{len(datasets)}: {service_name}"
            )
            logging.info(f"{'#' * 80}")
            try:
                # Get the specific repo manager for this service using existing helper
                repo_manager = self._get_borg_manager_for_service(service_name)
                logging.info(f"Analyzing repository at: {repo_manager.repo_path}")
                repo_manager.display_repository_info()

            except (ValueError, sh.ErrorReturnCode) as e:
                logging.error(
                    f"Could not analyze repository for service {service_name}: {e}"
                )
                logging.info(
                    f"ERROR: Failed to analyze {service_name}. See logs for details."
                )

        logging.info(f"\n{'=' * 80}")
        logging.info("Analysis of all service repositories is complete.")
        logging.info(f"{'=' * 80}")

    def export_all_keys(self):
        """Exports and verifies recovery keys for all Borg repositories."""
        logging.info("--> Exporting and verifying recovery keys for all services...")

        keys_dir = Path(self.config.borg_keys_dir)
        try:
            # Ensure the directory exists and is owned by the admin user
            # This script runs as root, so we use sh.sudo to manage permissions
            sh.sudo.mkdir("-p", str(keys_dir))
            sh.sudo.chown(
                f"{self.config.admin_user}:{self.config.admin_user}", str(keys_dir)
            )
            logging.info(f"Ensured keys directory exists: {keys_dir}")
        except Exception as e:
            logging.error(
                f"Failed to create or set permissions on keys directory {keys_dir}: {e}"
            )
            return  # Can't proceed

        datasets = list(self.zfs.get_datasets())
        if not datasets:
            logging.warning("No ZFS datasets found. No keys to export.")
            return

        logging.info(f"Found {len(datasets)} services. Exporting keys...")

        success_count = 0
        fail_count = 0

        for i, dataset in enumerate(datasets):
            service_name = Path(dataset.name).name
            # Create a unique key filename based on the full dataset path
            # e.g., datapool/services/fun -> datapool_services_fun.key
            repo_id = dataset.name.replace("/", "_")
            key_file_name = f"{repo_id}.key"
            key_export_path = keys_dir / key_file_name

            logging.info(f"\n{'=' * 60}")
            logging.info(
                f"Processing {i + 1}/{len(datasets)}: {service_name} (Repo: {repo_id})"
            )
            logging.info(f"Exporting key to: {key_export_path}")

            try:
                # Get the manager using the full dataset name
                repo_manager = self._get_borg_manager_for_dataset(dataset.name)
                repo_manager.export_recovery_key(key_export_path)

                # Set secure permissions on the exported key file
                # The file is created by the borg process (running as root)
                sh.sudo.chown(
                    f"{self.config.admin_user}:{self.config.admin_user}",
                    str(key_export_path),
                )
                sh.sudo.chmod("600", str(key_export_path))  # Read/Write for owner only

                logging.info(
                    f"Successfully exported and verified key for {service_name}."
                )
                success_count += 1
            except Exception as e:
                logging.error(
                    f"Failed to export or verify key for service {service_name}: {e}"
                )
                fail_count += 1

        logging.info(f"\n{'#' * 80}")
        logging.info("Key Export Summary:")
        logging.info(f"  Successfully exported: {success_count}")
        logging.info(f"  Failed to export:      {fail_count}")
        logging.info(f"  Keys are located in: {self.config.borg_keys_dir}")
        logging.info(f"{'#' * 80}")

    def _get_borg_manager_for_service(self, service_name: str) -> BorgBackupRepoManager:
        """Helper to create a BorgManager for a specific service repo."""
        dataset_name = f"{self.config.zfs_parent_dataset}/{service_name}"
        sanitized_name = dataset_name.replace("/", "_")
        repo_path = f"{self.config.borg_repo_base_path}/{sanitized_name}"
        return BorgBackupRepoManager(repo_path, self.config.base_borg_env)

    def _get_borg_manager_for_dataset(self, dataset_name: str) -> BorgBackupRepoManager:
        """Helper to create a BorgManager for a specific dataset repo."""
        sanitized_name = dataset_name.replace("/", "_")
        repo_path = f"{self.config.borg_repo_base_path}/{sanitized_name}"
        return BorgBackupRepoManager(repo_path, self.config.base_borg_env)

    def create_archive(self, service_name: str, snapshot_name: str):
        """Creates a new archive from a pre-existing snapshot."""
        logging.info(f"--- Starting Borg backup for service: {service_name} ---")
        borg = self._get_borg_manager_for_service(service_name)
        source_path = (
            Path(self.config.zfs_base_mountpoint)
            / service_name
            / ".zfs"
            / "snapshot"
            / snapshot_name
        )
        if not source_path.exists():
            logging.error(f"Snapshot path not found: {source_path}")
            sys.exit(1)
        borg.create_archive(
            archive_name=snapshot_name,
            source_path=source_path,
            compression=self.config.borg_compression,
            excludes_file=self.config.borg_excludes_file,
        )
        logging.info(f"--- Borg backup for service: {service_name} complete. ---")

    def list_archives(self, service_name: str):
        """Lists archives for a service."""
        logging.info(f"--- Listing archives for service: {service_name} ---")
        borg = self._get_borg_manager_for_service(service_name)
        logging.info(f"Repository: {borg.repo_path}")
        borg.list_archives(_fg=True)

    def extract_archive(self, service_name: str, archive_name: str, destination: str):
        """Extracts an archive to a destination."""
        logging.info(f"--- Extracting archive for service: {service_name} ---")
        borg = self._get_borg_manager_for_service(service_name)
        dest_path = Path(destination).resolve()
        sh.sudo.mkdir("-p", str(dest_path))
        sh.sudo.chown(
            f"{self.config.admin_user}:{self.config.admin_user}", str(dest_path)
        )
        borg.extract_archive(
            f"::{archive_name}",
            "--verbose",
            "--progress",
            "--list",
            _cwd=str(dest_path),
            _fg=True,
        )
        logging.info(f"--- Extraction complete. Files are in: {dest_path} ---")

    def delete_archive(self, service_name: str, archive_name: str):
        """Deletes a specific archive from a service repo."""
        logging.info(f"--- Deleting archive for service: {service_name} ---")
        borg = self._get_borg_manager_for_service(service_name)
        borg.delete_archive(
            f"::{archive_name}",
            "--verbose",
            "--progress",
            "--stats",
            _fg=True,
        )
        logging.info(f"--- Archive '{archive_name}' deleted. ---")

    def check_repo(self, service_name: str, verify: bool):
        """Checks a service repo integrity."""
        logging.info(f"--- Checking repository for service: {service_name} ---")
        borg = self._get_borg_manager_for_service(service_name)
        borg.check_repository(verify_data=verify)

    # --- ZFS Management ---

    def snapshot_all(self, snapshot_name: Optional[str] = None):
        """Creates a recursive snapshot for all services."""
        logging.info(f"--> Creating recursive snapshot: {snapshot_name}...")
        self.docker.down_all()
        self.zfs.create_snapshot(tag=snapshot_name, recursive=True)

    def snapshot_one(self, service_name: str, snapshot_name: Optional[str] = None):
        """Creates a snapshot for a single specified service."""
        logging.info(f"--> Creating snapshot for '{service_name}': {snapshot_name}...")
        self.docker.down_all()
        self.zfs.create_snapshot(tag=snapshot_name, dataset_name=service_name)

    def list_snapshots_all(self):
        """Lists all snapshots under the parent dataset."""
        print(f"--- Snapshots under [{self.config.zfs_parent_dataset}] ---")
        for snap in self.zfs.list_snapshots():
            print(f"- {snap.name} | Used: {snap.used} | Created: {snap.creation_date}")

    def list_snapshots_one(self, service_name: str):
        """Lists snapshots for a single specified service."""
        print(f"--- Snapshots for [{service_name}] ---")
        for snap in self.zfs.list_snapshots(dataset_name=service_name):
            print(f"- {snap.name} | Used: {snap.used} | Created: {snap.creation_date}")

    def create_service_dataset(self, service_name: str):
        """Creates a new ZFS dataset for a service."""
        logging.info(f"--> Creating ZFS dataset for: {service_name}...")
        self.docker.down_all()
        self.zfs.create_dataset(dataset_name=service_name)
        logging.info("--> Reminder: Add volumes to .env and run 'setup-storage'.")

    def snapshot_destroy_all(self, snapshot_name: str):
        """Destroys a recursive snapshot by name."""
        logging.info(f"--> Recursively destroying snapshot: {snapshot_name}...")
        self.docker.down_all()
        self.zfs.destroy_snapshot(tag=snapshot_name, recursive=True)

    # --- System Maintenance ---

    def system_maintenance(self):
        """Stops services, performs system updates, and restarts services."""
        logging.info("--> Starting system maintenance routine...")
        self.docker.down_all()
        self.system.perform_maintenance()
        self.docker.up_all()
        logging.info("--- System Maintenance Complete! ---")

    def partial_maintenance(self):
        """Runs snapshot-all then restarts services."""
        logging.info("--> Starting partial maintenance routine...")
        tag = f"partial-maintenance-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        self.snapshot_all(snapshot_name=tag)
        self.docker.up_all()
        logging.info("--- Partial Maintenance Complete! ---")

    def full_maintenance(self):
        """Runs snapshots, backup-all, then system maintenance."""
        logging.info("--> Starting full maintenance routine...")
        self.backup_all()
        self.system_maintenance()
        logging.info("--- Full Maintenance Complete! ---")


def main():
    """Main function to parse arguments and execute commands."""
    if os.geteuid() != 0:
        logging.error("This script must be run with sudo.")
        sys.exit(1)

    env_path = Path(__file__).resolve().parent.parent / ".env"
    config = Config(env_path)
    orchestrator = MasterOrchestrator(config)

    parser = argparse.ArgumentParser(description="Homelab VM Management Orchestrator.")
    subparsers = parser.add_subparsers(
        dest="command", required=True, help="Available commands"
    )

    # --- Map commands without arguments to parsers ---
    command_map = {
        "setup-storage": orchestrator.setup_storage,
        "init-backup": orchestrator.init_backup,
        "backup-all": orchestrator.backup_all,
        "borg-analyze-all": orchestrator.analyze_all_repos,
        "borg-export-keys-all": orchestrator.export_all_keys,
        "docker-up": orchestrator.docker.up_all,
        "docker-down": orchestrator.docker.down_all,
        "docker-start": orchestrator.docker.start_all,
        "docker-stop": orchestrator.docker.stop_all,
        "docker-create-networks": orchestrator.docker.create_networks,
        "list-snapshots-all": orchestrator.list_snapshots_all,
        "system-maintenance": orchestrator.system_maintenance,
        "partial-maintenance": orchestrator.partial_maintenance,
        "full-maintenance": orchestrator.full_maintenance,
    }
    for cmd, func in command_map.items():
        subparsers.add_parser(cmd, help=func.__doc__)

    # --- Define parsers for commands with arguments ---
    p_create = subparsers.add_parser(
        "create-archive", help=orchestrator.create_archive.__doc__
    )
    p_create.add_argument("--service-name", required=True)
    p_create.add_argument("--snapshot-name", required=True)

    p_list = subparsers.add_parser(
        "list-archives", help=orchestrator.list_archives.__doc__
    )
    p_list.add_argument("--service-name", required=True)

    p_extract = subparsers.add_parser(
        "extract-archive", help=orchestrator.extract_archive.__doc__
    )
    p_extract.add_argument("--service-name", required=True)
    p_extract.add_argument("--archive-name", required=True)
    p_extract.add_argument("--destination", required=True)

    p_delete = subparsers.add_parser(
        "delete-archive", help=orchestrator.delete_archive.__doc__
    )
    p_delete.add_argument("--service-name", required=True)
    p_delete.add_argument("--archive-name", required=True)

    p_check = subparsers.add_parser("check-repo", help=orchestrator.check_repo.__doc__)
    p_check.add_argument("--service-name", required=True)
    p_check.add_argument("--verify", action="store_true")

    p_snap_all = subparsers.add_parser(
        "snapshot-all", help=orchestrator.snapshot_all.__doc__
    )
    p_snap_all.add_argument("--snapshot-name", default=None)

    p_snap_one = subparsers.add_parser(
        "snapshot-one", help=orchestrator.snapshot_one.__doc__
    )
    p_snap_one.add_argument("--service-name", required=True)
    p_snap_one.add_argument("--snapshot-name", default=None)

    p_list_one = subparsers.add_parser(
        "list-snapshots-one", help=orchestrator.list_snapshots_one.__doc__
    )
    p_list_one.add_argument("--service-name", required=True)

    p_create_ds = subparsers.add_parser(
        "create-service-dataset", help=orchestrator.create_service_dataset.__doc__
    )
    p_create_ds.add_argument("--service-name", required=True)

    p_destroy_snap = subparsers.add_parser(
        "snapshot-destroy-all", help=orchestrator.snapshot_destroy_all.__doc__
    )
    p_destroy_snap.add_argument("--snapshot-name", required=True)

    args = parser.parse_args()

    # --- Execute the appropriate method based on the command ---
    try:
        # Simple command calls
        if args.command in command_map:
            command_map[args.command]()
        # Command calls with arguments
        elif args.command == "create-archive":
            orchestrator.create_archive(args.service_name, args.snapshot_name)
        elif args.command == "list-archives":
            orchestrator.list_archives(args.service_name)
        elif args.command == "extract-archive":
            orchestrator.extract_archive(
                args.service_name, args.archive_name, args.destination
            )
        elif args.command == "delete-archive":
            orchestrator.delete_archive(args.service_name, args.archive_name)
        elif args.command == "check-repo":
            orchestrator.check_repo(args.service_name, args.verify)
        elif args.command == "snapshot-all":
            orchestrator.snapshot_all(args.snapshot_name)
        elif args.command == "snapshot-one":
            orchestrator.snapshot_one(args.service_name, args.snapshot_name)
        elif args.command == "list-snapshots-one":
            orchestrator.list_snapshots_one(args.service_name)
        elif args.command == "create-service-dataset":
            orchestrator.create_service_dataset(args.service_name)
        elif args.command == "snapshot-destroy-all":
            orchestrator.snapshot_destroy_all(args.snapshot_name)
    except Exception as e:
        logging.critical(
            f"An error occurred during '{args.command}': {e}", exc_info=True
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
