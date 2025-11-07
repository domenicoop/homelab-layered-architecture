# ==============================================================================
#
#   Docker Compose Management Utility
#
#   This script provides functions to manage multiple Docker Compose services
#   spread across various subdirectories.
#
# ==============================================================================

import argparse
import log_setup
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional, Set

from dotenv import load_dotenv

# Import the 'sh' library.
try:
    import sh
except ImportError:
    print("[ERROR] The 'sh' library is not installed. Please run: pip install sh")
    sys.exit(1)

# Import the 'yaml' library for parsing compose files.
try:
    import yaml
except ImportError:
    print(
        "[ERROR] The 'PyYAML' library is not installed. Please run: pip install PyYAML"
    )
    sys.exit(1)


# --- INITIALIZATION ---
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


class DockerComposeManager:
    """
    A manager for handling Docker Compose services across multiple directories.
    This version implements "fail-fast" error handling and detailed logging.
    """

    def __init__(self, services_dir: Optional[str] = None) -> None:
        """
        Initializes the DockerComposeManager.
        """
        if services_dir:
            self.services_dir = Path(services_dir)
        else:
            self.services_dir = self._load_services_dir_from_env()

        self._check_services_dir()
        # Bake the base 'sudo docker' command for reuse.
        self.sudo_docker = sh.sudo.docker.bake()
        self.sudo_compose = self.sudo_docker.compose.bake()

    def _load_services_dir_from_env(self) -> Path:
        """
        Loads the SERVICES_DIR path from a .env file.
        """
        env_path = Path(__file__).resolve().parent.parent / ".env"
        load_dotenv(dotenv_path=env_path, override=True)
        services_dir = os.getenv("SERVICES_DIR")
        if not services_dir:
            logging.error(f"SERVICES_DIR not set in .env file at: {env_path}")
            sys.exit(1)
        return Path(services_dir)

    def _check_services_dir(self) -> None:
        """
        Verifies the validity of the SERVICES_DIR.
        """
        if not self.services_dir.is_dir():
            logging.error(
                f"SERVICES_DIR '{self.services_dir}' is not a valid directory."
            )
            logging.error("Please check your .env file and the directory structure.")
            sys.exit(1)

    def _find_compose_files(self) -> List[Path]:
        """
        Validates each service subdirectory and collects their docker-compose.yml files.
        """
        logging.info(f"Scanning for services in: {self.services_dir}...")
        compose_files = []

        # Assume each direct child of services_dir is a potential service.
        service_dirs = [d for d in self.services_dir.iterdir() if d.is_dir()]

        if not service_dirs:
            logging.warning(f"No service directories found in '{self.services_dir}'.")
            return []

        for service_dir in service_dirs:
            # Recursively find any docker-compose.yml within the service's directory.
            found_files = list(service_dir.rglob("docker-compose.yml"))
            if not found_files:
                logging.warning(
                    f"Service '{service_dir.name}' is missing a docker-compose.yml file. Skipping."
                )
            else:
                compose_files.extend(found_files)

        if not compose_files:
            logging.warning(
                "No valid services with docker-compose.yml files were found."
            )
        else:
            logging.info(f"Found {len(compose_files)} docker-compose.yml file(s).")
        return sorted(compose_files)

    def _log_output(self, line: str, source: str):
        """
        Callback to log command output, distinguishing between stdout and stderr.
        """
        line = line.strip()
        if not line:
            return  # Avoid logging empty lines.

        if source == "stderr":
            # Docker Compose often uses stderr for warnings and progress, so log as INFO
            # to avoid unnecessary noise, but identify the source.
            logging.info(f"[stderr] {line}")
        else:
            logging.info(line)

    def _run_command_on_all(
        self, command: str, *args: str, ok_codes: List[int] = [0]
    ) -> None:
        """
        A helper method that finds all compose files and executes a command on each one.
        If any command fails with an unexpected exit code, it raises an exception.
        """
        compose_files = self._find_compose_files()
        if not compose_files:
            return

        logging.info(
            f"--- Executing '{command}' on all {len(compose_files)} services ---"
        )

        for compose_file in compose_files:
            project_dir = compose_file.parent

            final_command = self.sudo_compose.bake(
                "-f", str(compose_file), command, *args, _cwd=project_dir
            )

            logging.info(f"Running command in '{project_dir}': {final_command}")
            try:
                # The `*a` in the lambda catches extra arguments from sh we don't need.
                final_command(
                    _ok_code=ok_codes,
                    _out=lambda line, *a: self._log_output(line, source="stdout"),
                    _err=lambda line, *a: self._log_output(line, source="stderr"),
                )
                logging.info(f"Successfully executed command for {project_dir.name}.")
            except sh.ErrorReturnCode as e:
                logging.error(
                    f"Command failed for {project_dir.name} with exit code {e.exit_code}. Halting execution."
                )
                raise e
            except sh.CommandNotFound as e:
                logging.error(f"'{e.command}' command not found. Is Docker installed?")
                raise e

        logging.info(
            f"--- Successfully executed '{command}' on all {len(compose_files)} services. ---"
        )

    def up_all(self) -> None:
        """Builds, creates, and starts all Docker Compose services."""
        self._run_command_on_all("up", "-d", "--build")

    def down_all(self) -> None:
        """Stops and removes containers for all services."""
        self._run_command_on_all("down")

    def start_all(self) -> None:
        """Starts all previously created service containers."""
        # Accept exit code 1, which Docker Compose returns if there are no containers to start.
        self._run_command_on_all("start", ok_codes=[0, 1])

    def stop_all(self) -> None:
        """Stops all running service containers without removing them."""
        # The 'stop' command is idempotent and exits with 0 even if nothing is running.
        self._run_command_on_all("stop")

    def pull_all(self) -> None:
        """Pulls the latest images for all services."""
        self._run_command_on_all("pull")

    def restart_all(self) -> None:
        """Restarts all running service containers."""
        # Accept exit code 1, which can be returned if there are no containers to restart.
        self._run_command_on_all("restart", ok_codes=[0, 1])

    def create_networks(self) -> None:
        """Finds and creates all external Docker networks defined across all compose files."""
        logging.info("--- Searching for external Docker networks ---")
        compose_files = self._find_compose_files()
        if not compose_files:
            return

        external_networks: Set[str] = set()
        for file in compose_files:
            try:
                with file.open("r") as f:
                    data = yaml.safe_load(f)
                    if not data or "networks" not in data:
                        continue

                    for name, config in data["networks"].items():
                        if config and config.get("external"):
                            external_networks.add(name)
            except yaml.YAMLError as e:
                logging.error(f"Error parsing YAML file {file}: {e}. Skipping.")
            except Exception as e:
                logging.error(f"Could not read file {file}: {e}. Skipping.")

        if not external_networks:
            logging.info("No external networks found to create.")
            return

        logging.info(
            f"Discovered external networks: {', '.join(sorted(external_networks))}"
        )

        try:
            # Get a set of already existing networks
            existing_output = self.sudo_docker.network.ls("--format", "{{.Name}}")
            existing_networks = set(existing_output.strip().split("\n"))
        except sh.ErrorReturnCode as e:
            logging.error(
                f"Failed to list existing Docker networks: {e.stderr.decode()}"
            )
            raise e

        for network in sorted(list(external_networks)):
            if network in existing_networks:
                logging.info(f"Network '{network}' already exists. Skipping.")
                continue

            logging.info(f"Creating network: '{network}'...")
            try:
                self.sudo_docker.network.create(
                    network,
                    _out=lambda line, *a: self._log_output(line, "stdout"),
                    _err=lambda line, *a: self._log_output(line, "stderr"),
                )
                logging.info(f"Successfully created network '{network}'.")
            except sh.ErrorReturnCode as e:
                logging.error(
                    f"Failed to create network '{network}': {e.stderr.decode()}"
                )
                raise e

        logging.info("--- External network creation process finished. ---")


def main() -> None:
    """
    Main function to parse command-line arguments and run the manager.
    """
    parser = argparse.ArgumentParser(
        description="A utility to manage all Docker Compose services."
    )
    parser.add_argument(
        "command",
        choices=["up", "down", "start", "stop", "pull", "restart", "create-networks"],
        help="The command to execute for all services. Use 'create-networks' to set up external networks.",
    )
    args = parser.parse_args()

    try:
        manager = DockerComposeManager()
        command_map = {
            "up": manager.up_all,
            "down": manager.down_all,
            "start": manager.start_all,
            "stop": manager.stop_all,
            "pull": manager.pull_all,
            "restart": manager.restart_all,
            "create-networks": manager.create_networks,
        }
        function_to_run = command_map[args.command]
        function_to_run()
    except Exception:
        # Catch any exceptions that bubble up and ensure the script exits
        # with a non-zero status code. Details are already logged.
        logging.critical("A critical error occurred. See logs above for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
