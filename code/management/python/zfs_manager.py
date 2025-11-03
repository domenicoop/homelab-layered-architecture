#!/usr/bin/env python3

# ====================================================================================
#
#                      ZFS Management Utility (ZFSManager)
#
# ====================================================================================
#
# This script provides a robust, object-oriented Python interface for managing
# ZFS filesystems and snapshots. It is designed to be both a reusable class
# for other Python applications and a standalone command-line utility.
#
# The primary goal is to offer a safer and more predictable way to interact with
# the `zfs` command-line tool by wrapping its functions in Python methods that
# include pre-checks, post-verification, and detailed error handling.
#
# It leverages the `sh` library for a clean and readable syntax when executing
# shell commands.
#
# ------------------------------------------------------------------------------------
#                                 Core Algorithms
# ------------------------------------------------------------------------------------
#
# The manager's reliability stems from two key patterns used throughout the class:
#
# 1.  **Exit Code Interpretation (For Existence Checks):**
#     -   **What it is:** Methods like `dataset_exists` and `_snapshot_exists`
#         run `zfs list` and carefully inspect the command's exit code.
#     -   **How it works:**
#         -   An exit code of `0` means the resource was found (SUCCESS).
#         -   An exit code of `1` specifically means "not found" in ZFS. This is
#           treated as a normal, expected outcome, not a script-halting error.
#         -   Any other non-zero exit code indicates a genuine system or ZFS
#           error, which is then raised as an exception.
#     -   **Why it's used:** This logic prevents false positives and allows the
#         script to reliably determine the state of the system before taking action.
#
# 2.  **Command-Verify Pattern (For State-Changing Operations):**
#     -   **What it is:** A three-step process for all methods that create or
#         destroy resources (`create_dataset`, `create_snapshot`, `destroy_snapshot`).
#     -   **How it works:**
#         a.  **Pre-Check (Idempotency):** The script first checks if the
#             system is already in the desired state. For example, before
#             creating a dataset, it verifies it doesn't already exist. This
#             makes the script safe to run multiple times without causing errors.
#         b.  **Execute Command:** It runs the appropriate `zfs` command
#             (e.g., `zfs create` or `zfs destroy`).
#         c.  **Post-Verification:** After the command runs, it immediately
#             performs another existence check to *confirm* that the operation
#             succeeded. If a `create` command runs but the dataset is not found
#             afterward, it raises a `RuntimeError`.
#     -   **Why it's used:** This ensures a "fail-fast" approach. The script
#         doesn't just hope the command worked; it proves it, preventing silent
#         failures and ensuring the system's state is always consistent with
#         what the script expects.
#
# 3.  **Streaming Output (For Listing Operations):**
#     -   **What it is:** Methods like `get_datasets` and `list_snapshots` use
#         the `_iter=True` feature of the `sh` library.
#     -   **How it works:** Instead of loading all output from the `zfs list`
#         command into memory, the script processes it line-by-line as it
#         arrives.
#     -   **Why it's used:** This is highly memory-efficient and prevents the
#         script from crashing or slowing down on systems with thousands of
#         datasets or snapshots.
#
# ====================================================================================

import argparse
import log_setup
import datetime
import logging
import sys
from dataclasses import dataclass
from typing import Iterator, Optional

# Import the 'sh' library for shell command execution.
try:
    import sh
except ImportError:
    print("[ERROR] The 'sh' library is not installed. Please run: pip install sh")
    sys.exit(1)


# --- CONFIGURATION & INITIALIZATION ---

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    datefmt="%Y-%m-%d %H:%M:%S",
)


@dataclass
class ZFSDataset:
    """A simple container for ZFS dataset information."""

    name: str
    mount_point: str


@dataclass
class ZFSSnapshot:
    """A simple container for ZFS snapshot information."""

    name: str
    used: str
    creation_date: str


# --- ZFS SERVICE CLASS ---


class ZFSManager:
    """Handles all ZFS-related operations using the 'sh' library."""

    def __init__(self, parent_dataset: str):
        """Initializes the manager with the top-level ZFS dataset."""
        if not parent_dataset:
            raise ValueError("parent_dataset cannot be empty.")
        self.parent_dataset = parent_dataset
        # Bake the 'sudo zfs' command for convenient reuse.
        self.zfs = sh.sudo.bake("zfs")
        logging.info(
            f"ZFSManager initialized for parent dataset: '{self.parent_dataset}'."
        )

    def _execute_command(self, command_func, *args):
        """
        A helper to run blocking sh commands with consistent logging and error handling.
        """
        final_command = command_func.bake(*args)
        cmd_str = str(final_command)

        logging.info(f"Running command: {cmd_str}")
        try:
            result = final_command()
            logging.info(f"Command '{cmd_str}' executed successfully.")
            return result
        except sh.ErrorReturnCode as e:
            logging.error(f"Command failed with exit code {e.exit_code}: {cmd_str}")
            if e.stdout:
                logging.error(f"Failed command stdout: {e.stdout.decode().strip()}")
            if e.stderr:
                logging.error(f"Failed command stderr: {e.stderr.decode().strip()}")
            raise

    def dataset_exists(self, dataset_name: Optional[str] = None) -> bool:
        """Checks if a specific ZFS dataset exists using a robust method."""
        target_dataset = (
            f"{self.parent_dataset}/{dataset_name}"
            if dataset_name
            else self.parent_dataset
        )
        logging.debug(f"Checking existence of dataset: {target_dataset}")
        try:
            # Command succeeds (exit code 0) only if the dataset exists.
            self.zfs("list", "-H", "-t", "filesystem", target_dataset)
            logging.debug(f"Dataset '{target_dataset}' exists.")
            return True
        except sh.ErrorReturnCode as e:
            # 'zfs list' returns 1 if not found; this is expected, not an error.
            if e.exit_code == 1:
                logging.debug(f"Dataset '{target_dataset}' does not exist.")
                return False
            # Any other exit code is an unexpected failure.
            else:
                logging.error(
                    f"Error checking for dataset '{target_dataset}'. Exit code: {e.exit_code}"
                )
                if e.stderr:
                    logging.error(f"Stderr: {e.stderr.decode().strip()}")
                raise  # Re-raise the exception as it's a genuine error.

    def _snapshot_exists(self, full_snapshot_name: str) -> bool:
        """Checks if a specific ZFS snapshot exists."""
        logging.debug(f"Checking existence of snapshot: {full_snapshot_name}")
        try:
            self.zfs("list", "-H", "-t", "snapshot", full_snapshot_name)
            logging.debug(f"Snapshot '{full_snapshot_name}' exists.")
            return True
        except sh.ErrorReturnCode as e:
            if e.exit_code == 1:
                logging.debug(f"Snapshot '{full_snapshot_name}' does not exist.")
                return False
            else:
                logging.error(
                    f"Error checking for snapshot '{full_snapshot_name}'. Exit code: {e.exit_code}"
                )
                if e.stderr:
                    logging.error(f"Stderr: {e.stderr.decode().strip()}")
                raise

    def create_dataset(self, dataset_name: str, create_parents: bool = True):
        """
        Creates a new ZFS dataset and verifies its creation.
        """
        full_dataset_name = f"{self.parent_dataset}/{dataset_name}"
        if self.dataset_exists(dataset_name):
            logging.info(
                f"Dataset '{full_dataset_name}' already exists. No action taken."
            )
            return

        logging.info(f"Attempting to create ZFS dataset: {full_dataset_name}")
        args = ["create"]
        if create_parents:
            args.append("-p")
        args.append(full_dataset_name)
        self._execute_command(self.zfs, *args)

        # --- Verification Step ---
        logging.info(f"Verifying creation of dataset '{full_dataset_name}'...")
        if not self.dataset_exists(dataset_name):
            error_msg = f"Verification failed! Dataset '{full_dataset_name}' was not found after creation."
            logging.error(error_msg)
            raise RuntimeError(error_msg)

        logging.info(
            f"Successfully created and verified ZFS dataset: {full_dataset_name}."
        )

    def create_snapshot(
        self,
        tag: Optional[str] = None,
        dataset_name: Optional[str] = None,
        recursive: bool = False,
    ) -> str:
        """
        Creates a ZFS snapshot and verifies its creation.
        """
        if not tag:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            tag = f"auto-{timestamp}"

        target_dataset = (
            f"{self.parent_dataset}/{dataset_name}"
            if dataset_name
            else self.parent_dataset
        )
        full_snapshot_name = f"{target_dataset}@{tag}"

        if self._snapshot_exists(full_snapshot_name):
            raise FileExistsError(f"Snapshot '{full_snapshot_name}' already exists.")

        logging.info(f"Attempting to create ZFS snapshot: {full_snapshot_name}")
        args = ["snapshot"]
        if recursive:
            args.append("-r")
        args.append(full_snapshot_name)
        self._execute_command(self.zfs, *args)

        # --- Verification Step ---
        logging.info(f"Verifying creation of snapshot '{full_snapshot_name}'...")
        if not self._snapshot_exists(full_snapshot_name):
            error_msg = f"Verification failed! Snapshot '{full_snapshot_name}' was not found after creation."
            logging.error(error_msg)
            raise RuntimeError(error_msg)

        logging.info(
            f"Successfully created and verified ZFS snapshot: {full_snapshot_name}."
        )
        return full_snapshot_name

    def destroy_snapshot(
        self, tag: str, dataset_name: Optional[str] = None, recursive: bool = False
    ):
        """
        Destroys a ZFS snapshot and verifies its destruction.
        """
        target_dataset = (
            f"{self.parent_dataset}/{dataset_name}"
            if dataset_name
            else self.parent_dataset
        )
        full_snapshot_name = f"{target_dataset}@{tag}"

        # --- Pre-check for Idempotency ---
        if not self._snapshot_exists(full_snapshot_name):
            logging.info(
                f"Snapshot '{full_snapshot_name}' does not exist. No action taken."
            )
            return

        logging.info(f"Attempting to destroy ZFS snapshot: {full_snapshot_name}")
        args = ["destroy"]
        if recursive:
            args.append("-r")
        args.append(full_snapshot_name)
        self._execute_command(self.zfs, *args)

        # --- Verification Step ---
        logging.info(f"Verifying destruction of snapshot '{full_snapshot_name}'...")
        if self._snapshot_exists(full_snapshot_name):
            error_msg = f"Verification failed! Snapshot '{full_snapshot_name}' still exists after destruction."
            logging.error(error_msg)
            raise RuntimeError(error_msg)

        logging.info(
            f"Successfully destroyed and verified ZFS snapshot: {full_snapshot_name}."
        )

    def get_datasets(self) -> Iterator[ZFSDataset]:
        """
        Streams and yields all mounted child datasets under the parent.
        """
        logging.info(f"Searching for all child datasets under '{self.parent_dataset}'.")
        command = self.zfs.bake(
            "list",
            "-r",
            "-t",
            "filesystem",
            "-o",
            "name,mountpoint",
            "-H",
            self.parent_dataset,
        )

        logging.info(f"Running command: {command}")
        try:
            for line in command(_iter=True):
                try:
                    name, mount_point = line.strip().split("\t")
                    if mount_point == "-":
                        logging.debug(f"Skipping unmounted dataset: {name}")
                        continue
                    yield ZFSDataset(name=name, mount_point=mount_point)
                except ValueError:
                    logging.warning(
                        f"Could not parse ZFS list line: '{line.strip()}'. Skipping."
                    )
        except sh.ErrorReturnCode as e:
            logging.error(f"Failed to list datasets with command: {command}")
            logging.error(f"Exit Code: {e.exit_code}, Stderr: {e.stderr.decode()}")
            raise

    def list_snapshots(
        self, dataset_name: Optional[str] = None
    ) -> Iterator[ZFSSnapshot]:
        """
        Lists snapshots, sorted by creation time, by streaming the output.
        """
        target = (
            f"{self.parent_dataset}/{dataset_name}"
            if dataset_name
            else self.parent_dataset
        )
        logging.info(f"Listing snapshots under '{target}'")
        command = self.zfs.bake(
            "list",
            "-t",
            "snapshot",
            "-r",
            "-o",
            "name,used,creation",
            "-s",
            "creation",
            "-H",
            target,
        )

        logging.info(f"Running command: {command}")
        try:
            for line in command(_iter=True):
                try:
                    name, used, *creation_parts = line.strip().split()
                    creation_date = " ".join(creation_parts)
                    yield ZFSSnapshot(name=name, used=used, creation_date=creation_date)
                except ValueError:
                    logging.warning(
                        f"Could not parse ZFS snapshot list line: '{line.strip()}'. Skipping."
                    )
        except sh.ErrorReturnCode as e:
            logging.error(f"Failed to list snapshots with command: {command}")
            logging.error(f"Exit Code: {e.exit_code}, Stderr: {e.stderr.decode()}")
            raise


def main():
    """Main function to handle command-line arguments."""
    parser = argparse.ArgumentParser(description="ZFS Management Utility.")
    parser.add_argument(
        "parent_dataset", help="The parent ZFS dataset (e.g., 'zpool/services')."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- list-datasets ---
    subparsers.add_parser("list-datasets", help="List all child datasets.")

    # --- list-snapshots ---
    snap_list_parser = subparsers.add_parser("list-snapshots", help="List snapshots.")
    snap_list_parser.add_argument(
        "--dataset", help="Optional: specific dataset to list snapshots for."
    )

    # --- create-dataset ---
    ds_create_parser = subparsers.add_parser(
        "create-dataset", help="Create a new ZFS dataset."
    )
    ds_create_parser.add_argument("name", help="Name of the new dataset.")

    # --- create-snapshot ---
    snap_create_parser = subparsers.add_parser(
        "create-snapshot", help="Create a ZFS snapshot."
    )
    snap_create_parser.add_argument(
        "tag", help="Tag for the snapshot (e.g., 'backup')."
    )
    snap_create_parser.add_argument(
        "--dataset", help="Optional: specific dataset to snapshot."
    )
    snap_create_parser.add_argument(
        "-r", "--recursive", action="store_true", help="Create a recursive snapshot."
    )

    # --- destroy-snapshot ---
    snap_destroy_parser = subparsers.add_parser(
        "destroy-snapshot", help="Destroy a ZFS snapshot."
    )
    snap_destroy_parser.add_argument(
        "tag", help="Tag for the snapshot to destroy (e.g., 'backup')."
    )
    snap_destroy_parser.add_argument(
        "--dataset", help="Optional: specific dataset to destroy snapshot from."
    )
    snap_destroy_parser.add_argument(
        "-r", "--recursive", action="store_true", help="Destroy a recursive snapshot."
    )

    args = parser.parse_args()
    try:
        manager = ZFSManager(parent_dataset=args.parent_dataset)

        if args.command == "list-datasets":
            print(f"--- Datasets in {args.parent_dataset} ---")
            count = 0
            for ds in manager.get_datasets():
                print(f"- {ds.name} (mounted at {ds.mount_point})")
                count += 1
            if count == 0:
                print("No datasets found.")

        elif args.command == "list-snapshots":
            target = (
                f"{args.parent_dataset}/{args.dataset}"
                if args.dataset
                else args.parent_dataset
            )
            print(f"--- Snapshots in {target} ---")
            snapshots_found = False
            for snap in manager.list_snapshots(dataset_name=args.dataset):
                snapshots_found = True
                print(
                    f"- {snap.name} | Used: {snap.used} | Created: {snap.creation_date}"
                )
            if not snapshots_found:
                print("No snapshots found.")

        elif args.command == "create-dataset":
            manager.create_dataset(dataset_name=args.name)

        elif args.command == "create-snapshot":
            manager.create_snapshot(
                tag=args.tag, dataset_name=args.dataset, recursive=args.recursive
            )

        elif args.command == "destroy-snapshot":
            manager.destroy_snapshot(
                tag=args.tag, dataset_name=args.dataset, recursive=args.recursive
            )

    except (sh.ErrorReturnCode, RuntimeError, FileExistsError) as e:
        # Catch exceptions that propagate up to main
        print(f"\n[FATAL] An unrecoverable error occurred: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n[FATAL] A Python error occurred: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
