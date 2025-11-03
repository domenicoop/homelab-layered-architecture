#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
System Management Utility

This script provides a SystemManager class to handle system-level operations,
primarily focusing on package management with 'apt'. It follows best practices
for using the 'sh' library by relying on try/except blocks for error handling
rather than problematic internal arguments.
"""

# --- STANDARD LIBRARY IMPORTS ---
import argparse
import log_setup
import logging
import sys

# --- THIRD-PARTY LIBRARY IMPORTS ---
try:
    import sh
except ImportError:
    print("[ERROR] The 'sh' library is not installed. Please run: pip install sh")
    sys.exit(1)


# --- CONFIGURATION & INITIALIZATION ---

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


class SystemManager:
    """
    Handles system maintenance tasks like package updates using 'apt'.
    """

    def __init__(self):
        """
        Initializes the SystemManager.
        """
        # Define base commands without baking special arguments.
        # Error handling will be managed by try...except blocks.
        self.sudo = sh.sudo
        logging.info("SystemManager initialized.")

    def perform_maintenance(self, foreground: bool = True):
        """
        Performs a full system maintenance routine using apt.

        This includes updating the package list, upgrading packages, removing
        unused packages, and cleaning the local repository.

        Args:
            foreground (bool): If True, command output is streamed directly to the terminal.
                               If False, it is captured and logged upon completion/failure.
        """
        logging.info("--- Starting System Maintenance Routine ---")

        maintenance_steps = [
            ("update", "Updating package lists..."),
            ("upgrade", "Upgrading installed packages..."),
            ("autoremove", "Removing unused packages..."),
            ("autoclean", "Cleaning up old package files..."),
        ]

        try:
            for command, description in maintenance_steps:
                logging.info(f"--> {description}")

                # Use explicit, unambiguous calling syntax.
                # The '-y' flag is added to non-interactive commands.
                apt_command = self.sudo.bake("apt-get", command)
                if command in ["upgrade", "autoremove"]:
                    apt_command = apt_command.bake("-y")

                if foreground:
                    # Stream output directly to the user's terminal.
                    apt_command(_fg=True)
                else:
                    # Execute in the background and log output.
                    result = apt_command()
                    if result.stdout:
                        logging.info(f"Stdout: {result.stdout.decode().strip()}")

            logging.info("--- System Maintenance Completed Successfully ---")

        except sh.ErrorReturnCode as e:
            # This block will catch any command that fails (returns a non-zero exit code).
            logging.error("\n[FATAL] A maintenance command failed, halting execution.")
            logging.error(f"--> Command: '{e.full_cmd}'")
            logging.error(f"--> Exit Code: {e.exit_code}")
            if e.stderr:
                logging.error(f"--> Stderr: {e.stderr.decode().strip()}")
            # Re-raise the exception to allow calling scripts to handle the failure.
            raise


def main():
    """
    Main function to handle command-line arguments for the SystemManager.
    """
    if sys.platform != "linux":
        logging.error("This script is designed for Linux systems with 'apt'.")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="System Maintenance Utility.")
    parser.add_argument(
        "command",
        choices=["run-maintenance"],
        help="The maintenance task to execute.",
    )
    args = parser.parse_args()

    try:
        manager = SystemManager()
        if args.command == "run-maintenance":
            manager.perform_maintenance()
    except sh.ErrorReturnCode:
        # The detailed error is already logged by the manager.
        logging.critical(
            "A critical error occurred during system maintenance. See logs above."
        )
        sys.exit(1)
    except Exception as e:
        logging.critical(f"An unexpected Python error occurred: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
