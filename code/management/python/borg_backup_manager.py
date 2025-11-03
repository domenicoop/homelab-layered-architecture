#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Provides tools for managing and analyzing BorgBackup repositories.

This module contains:
- BorgBackupRepoManager: A class dedicated to executing commands
  (init, create, prune, etc.) on a single Borg repository.

It acts as a wrapper around the Borg command-line tool, using the 'sh'
library to execute commands.
"""

# --- STANDARD LIBRARY IMPORTS ---
import log_setup
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List
from urllib.parse import urlparse

# --- THIRD-PARTY LIBRARY IMPORTS ---
try:
    import sh
except ImportError:
    logging.error("The 'sh' library is not installed. Please run: pip install sh")
    sys.exit(1)


class BorgBackupRepoManager:
    """
    Manages all operations for a single Borg repository using the 'sh' library.

    This class is responsible for the low-level execution of Borg commands like
    'init', 'create', 'prune', 'check', and 'key export'.
    """

    def __init__(self, repo_path: str, base_env: Dict[str, str]):
        """
        Initializes the repository handler with a specific path and base environment.

        Args:
            repo_path (str): The full path to the Borg repository.
            base_env (Dict[str, str]): A dictionary with environment variables
                                       required for Borg, like BORG_PASSPHRASE and BORG_RSH.
        """
        # --- Configuration Validation ---
        required_vars = ["BORG_PASSPHRASE", "BORG_RSH"]
        missing_vars = [var for var in required_vars if not base_env.get(var)]

        if missing_vars:
            error_msg = f"BorgBackupRepoManager is missing required environment configuration: {', '.join(missing_vars)}"
            logging.critical(error_msg)
            raise ValueError(error_msg)

        self.repo_path = repo_path
        self.borg_env = base_env.copy()
        self.borg_env["BORG_REPO"] = self.repo_path

        # Bake `sudo` with the `-E` flag to preserve the environment.
        # This ensures BORG_REPO and other variables are passed to the borg process.
        self.sudo_with_env = sh.sudo.bake("-E")
        self.borg = self.sudo_with_env.borg.bake(_env=self.borg_env)
        logging.info(
            f"BorgBackupRepoManager instance created for path: {self.repo_path}"
        )

    def _execute_command(self, *args, **kwargs):
        """
        A private helper to run Borg commands with consistent logging and error handling.
        """
        # Bake the final command object to get an accurate string for logging.
        final_command = self.borg.bake(*args, **kwargs)
        logging.info(f"Running command: {final_command}")
        try:
            # The environment is already baked in, so we just execute the command.
            result = final_command()
            logging.info("Command executed successfully.")
            return result
        except sh.ErrorReturnCode as e:
            logging.error(f"Command failed with exit code {e.exit_code}: {e.full_cmd}")
            if e.stdout:
                logging.error(f"Failed command stdout: {e.stdout.decode().strip()}")
            if e.stderr:
                logging.error(f"Failed command stderr: {e.stderr.decode().strip()}")
            raise

    def _repository_exists(self) -> bool:
        """
        Checks if the Borg repository exists by running 'borg info'.

        Returns:
            bool: True if the repository exists, False if it does not.
        Raises:
            sh.ErrorReturnCode: For any unexpected errors (permissions, SSH issues, etc.).
        """
        logging.info(f"Checking for existing repository at: {self.repo_path}")
        try:
            # If this command succeeds (exit code 0), the repository exists.
            # We remove _ok_code=[0, 2] so that an exit code of 2 raises an
            # exception, which we can catch and handle below.
            self.borg("info")
            return True
        except sh.ErrorReturnCode as e:
            # Borg's 'info' command returns exit code 2 if the repository does not exist.
            if e.exit_code == 2:
                logging.info("Repository does not exist (Borg exit code 2).")
                return False
            # Any other non-zero exit code indicates a genuine problem.
            logging.error(
                f"An unexpected error occurred while checking repository {self.repo_path}. "
                "This could be an SSH or permissions issue."
            )
            raise

    def _clean_remote_path(self, path: str) -> str:
        """
        Removes special SSH path prefixes like /./ or ~/ to get a path
        relative to the SSH user's home directory.
        """
        if path.startswith("/./"):
            # Path is /./borg-backups/homelabv2main -> borg-backups/homelabv2main
            return path[3:]
        if path.startswith("/~/"):  # Borg also supports this
            return path[3:]
        if path.startswith("~/"):
            return path[2:]
        # General fallback, remove leading slash to prevent absolute path
        return path.lstrip("/")

    def _initialize_repository(self):
        """Executes the 'borg init' command."""
        logging.info(f"Initializing new repository at {self.repo_path}...")
        # Borg init is responsible for creating the *final* directory
        self._execute_command("init", "--encryption=repokey-blake2")

    def initialize_if_needed(self):
        """
        Ensures the Borg repository exists, initializing it if necessary.
        This method is idempotent and follows a check-prepare-execute-verify pattern.
        """
        try:
            if self._repository_exists():
                logging.info("Repository already exists. No initialization needed.")
                return
        except sh.ErrorReturnCode:
            # The error is already logged by _repository_exists. We re-raise to halt execution.
            logging.critical(
                "A critical error occurred while checking repository status. Halting."
            )
            raise

        logging.warning(
            f"Repository not found at {self.repo_path}. Attempting to initialize."
        )

        # Execute the initialization. Borg will create the final dir.
        self._initialize_repository()

        # Verify that the initialization was successful.
        logging.info("Verifying repository initialization...")
        if not self._repository_exists():
            raise RuntimeError(
                f"FATAL: Repository initialization failed for {self.repo_path}. "
                "The repository was not found after the 'init' command."
            )

        logging.info(
            f"Successfully initialized and verified new repository at {self.repo_path}."
        )

    def export_recovery_key(self, key_file_path: Path):
        """
        Exports the repository's recovery key and verifies it.

        This method exports the key in the importable '--paper' format and then
        runs 'borg list' using *both* the original BORG_PASSPHRASE and the
        newly exported BORG_KEY_FILE.

        This proves that the key was exported correctly and that the
        passphrase on record can successfully decrypt and use this key.

        Args:
            key_file_path (Path): The full path where the key file will be saved.
        """
        logging.info(f"Exporting recovery key to: {key_file_path}")
        if key_file_path.exists():
            logging.warning(
                f"Key file {key_file_path} already exists and will be overwritten."
            )

        key_file_path.parent.mkdir(parents=True, exist_ok=True)

        # --- Step 1: Export the key in --paper format ---
        try:
            # We must explicitly pass self.repo_path as the [REPOSITORY] argument
            self._execute_command(
                "key", "export", "--paper", self.repo_path, str(key_file_path)
            )
            logging.info(f"Successfully saved key to {key_file_path}.")
        except sh.ErrorReturnCode as e:
            logging.error(f"Failed to export recovery key for {self.repo_path}")
            # If export fails, delete the potentially partial/corrupt file
            if key_file_path.exists():
                try:
                    key_file_path.unlink()
                    logging.info(f"Removed partial key file: {key_file_path}")
                except OSError as os_err:
                    logging.error(
                        f"Failed to remove partial key file {key_file_path}: {os_err}"
                    )
            raise

        # --- Step 2: Verify the exported key by using it to list archives ---
        logging.info(
            f"Verifying exported key at {key_file_path} by using it to list archives..."
        )

        # Create a special environment for verification:
        # We use the original env (with BORG_PASSPHRASE) and *add*
        # BORG_KEY_FILE. Borg will use the passphrase to decrypt the
        # key file, which is then used to decrypt the repo.
        verify_env = self.borg_env.copy()
        verify_env["BORG_KEY_FILE"] = str(key_file_path)

        try:
            # Create a new borg command baked with this verification environment
            borg_verify_cmd = self.sudo_with_env.borg.bake(_env=verify_env)

            # Run 'borg list'. It will use BORG_PASSPHRASE to unlock BORG_KEY_FILE.
            logging.info(
                f"Running verification command: {borg_verify_cmd.bake('list')}"
            )
            borg_verify_cmd("list")

            logging.info(
                "Key verification successful: The exported key file was used "
                "to successfully decrypt and list repository archives."
            )
        except sh.ErrorReturnCode as e:
            # This is a critical failure. The exported key is useless.
            logging.error(
                f"CRITICAL: Verification of exported key {key_file_path} FAILED. "
                "The key file could not be used to decrypt the repository. "
                "The file will be deleted to prevent using a bad key."
            )
            if e.stderr:
                logging.error(
                    f"Verification command stderr: {e.stderr.decode().strip()}"
                )

            # Delete the bad key
            try:
                key_file_path.unlink()
                logging.info(f"Removed invalid key file: {key_file_path}")
            except OSError as os_err:
                logging.error(
                    f"Failed to remove invalid key file {key_file_path}: {os_err}"
                )

            # Re-raise the original exception to halt any further process
            raise

    def create_archive(
        self, archive_name: str, source_path: Path, compression: str, excludes_file: str
    ):
        """
        Creates a new archive in the repository from a specified source path.

        Args:
            archive_name (str): The name for the new archive.
            source_path (Path): The path to the directory or file to back up.
            compression (str): The compression algorithm to use (e.g., 'zstd,10').
            excludes_file (str): Path to a file containing patterns to exclude.
        """
        logging.info(f"Starting Borg backup for '{source_path}'")
        self._execute_command(
            "create",
            "--verbose",
            "--stats",
            "--progress",
            f"--compression={compression}",
            f"--exclude-from={excludes_file}",
            f"::{archive_name}",
            str(source_path),
            _fg=True,
        )
        logging.info("Borg archive creation complete.")

    def prune_archives(self, prune_policy: List[str]):
        """
        Prunes old archives in the repository according to a given policy.

        Args:
            prune_policy (List[str]): A list of arguments defining the prune policy.
        """
        logging.info(f"Pruning old archives in repository: {self.repo_path}")
        self._execute_command(
            "prune",
            "--verbose",
            "--list",
            "--show-rc",
            "--progress",
            *prune_policy,
            _fg=True,
        )
        logging.info("Pruning of old archives complete.")

    def display_repository_info(self):
        """
        Displays a comprehensive status of the repository.

        This method logs the output of 'borg info' for repository-wide
        statistics and 'borg list' to show all available archives. The output
        is directed to the console for immediate review.
        """
        logging.info(f"Analyzing repository status for: {self.repo_path}")

        try:
            logging.info("\n" + "=" * 25 + " Repository Statistics " + "=" * 25)
            # Run in foreground to log directly to user's terminal
            self._execute_command("info", _fg=True)
        except sh.ErrorReturnCode:
            logging.error(
                f"Failed to retrieve info for {self.repo_path}. The repository might not be initialized or is inaccessible."
            )
            # If info fails, list will also fail, so we stop here.
            return

        try:
            logging.info("\n" + "=" * 28 + " Archives List " + "=" * 28)
            # Run in foreground to log directly to user's terminal
            self._execute_command("list", _fg=True)
            logging.info("=" * 71)
        except sh.ErrorReturnCode:
            logging.error(
                f"Failed to list archives for {self.repo_path}. The repository might be corrupted or empty."
            )

    def list_archives(self, *args, **kwargs):
        """Lists archives in the repository."""
        return self._execute_command("list", *args, **kwargs)

    def extract_archive(self, *args, **kwargs):
        """Extracts an archive from the repository."""
        return self._execute_command("extract", *args, **kwargs)

    def delete_archive(self, *args, **kwargs):
        """Deletes an archive from the repository."""
        return self._execute_command("delete", *args, **kwargs)

    def check_repository(self, verify_data: bool = False):
        """
        Checks the integrity of the Borg repository.
        """
        logging.info(f"Starting integrity check for repository: {self.repo_path}")

        args = ["check", "--verbose", "--progress"]
        if verify_data:
            logging.info(
                "Full data verification (--verify-data) is enabled. This may take a long time."
            )
            args.append("--verify-data")
        else:
            logging.info("Performing a metadata-only integrity check.")

        local_env = self.borg_env.copy()

        original_rsh = local_env.get("BORG_RSH", "")
        if "ssh " in original_rsh:
            modified_rsh = original_rsh.replace(
                "ssh ", "ssh -o ServerAliveInterval=60 ", 1
            )
            local_env["BORG_RSH"] = modified_rsh
            logging.info(f"Using modified BORG_RSH for check: {modified_rsh}")

        borg_check_cmd = self.sudo_with_env.borg.bake(_env=local_env)
        final_command = borg_check_cmd.bake(*args, _fg=True)

        logging.info(f"Running command: {final_command}")
        try:
            final_command()
            logging.info(f"Integrity check for {self.repo_path} complete.")
        except sh.ErrorReturnCode as e:
            logging.error(
                f"Integrity check failed with exit code {e.exit_code}: {e.full_cmd}"
            )
            if e.stderr:
                logging.error(f"Check command stderr: {e.stderr.decode().strip()}")
            raise


# --- SCRIPT EXECUTION LOGIC ---


if __name__ == "__main__":
    # --- CONFIGURATION ---
    # Set these environment variables before running the script.
    # export BORG_PASSPHRASE="your-super-secret-passphrase"
    # export BORG_RSH="ssh -i /home/user/.ssh/id_ed25519"
    # export BORG_REPOS_BASE_PATH="ssh://user@host/./borg-backups"
    # export BORG_KEYS_DIR="/path/to/borg_keys"

    borg_passphrase = os.environ.get("BORG_PASSPHRASE")
    borg_rsh = os.environ.get("BORG_RSH")
    repos_base_path_str = os.environ.get("BORG_REPO_BASE_PATH")
    borg_keys_dir_str = os.environ.get("BORG_KEYS_DIR")

    # --- VALIDATION ---
    required_env_vars = {
        "BORG_PASSPHRASE": borg_passphrase,
        "BORG_RSH": borg_rsh,
        "BORG_REPO_BASE_PATH": repos_base_path_str,
        "BORG_KEYS_DIR": borg_keys_dir_str,
    }

    missing_vars = [key for key, value in required_env_vars.items() if not value]

    if missing_vars:
        error_message = f"ERROR: Please set the following environment variables: {', '.join(missing_vars)}"
        logging.critical(error_message)
        sys.stderr.write(error_message + "\n")
        sys.exit(1)

    base_borg_env = {
        "BORG_PASSPHRASE": borg_passphrase,
        "BORG_RSH": borg_rsh,
    }

    # --- EXECUTION ---
    try:
        # Example usage for a single repository:
        repo_manager = BorgBackupRepoManager(repos_base_path_str, base_borg_env)

        logging.info("--- Initializing Repository (if needed) ---")
        repo_manager.initialize_if_needed()

        # --- Example of exporting and verifying the key ---

        # Get a sane filename from the repo path
        # e.g., ssh://user@host/./path/to/repo -> repo
        repo_name = Path(urlparse(repos_base_path_str).path).name
        if not repo_name:
            repo_name = "borg_repo"  # fallback

        key_file_name = f"{repo_name}.key"
        key_export_path = Path(borg_keys_dir_str) / key_file_name

        logging.info("--- Starting Key Export & Verification ---")
        repo_manager.export_recovery_key(key_export_path)
        logging.info("--- Key Export & Verification Complete ---")

        # --- Display final repository info ---
        logging.info("--- Displaying Repository Info ---")
        repo_manager.display_repository_info()

    except (FileNotFoundError, ValueError) as e:
        # Catch configuration errors from the manager's __init__
        logging.critical(f"Configuration error: {e}", exc_info=False)
        sys.exit(1)
    except Exception as e:
        logging.critical(
            f"An unexpected error occurred during execution: {e}", exc_info=True
        )
        sys.exit(1)
