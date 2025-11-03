# ==============================================================================
#
#   Master Makefile for Homelab Management (Orchestrator Edition)
#
#   This Makefile serves as a simple, high-level wrapper for the master
#   `orchestrator.py` script. It translates easy-to-remember `make` commands
#   into the corresponding Python script calls with the correct arguments.
#
#   NOTE: 'install' and 'clean' are implemented directly in shell commands
#   as they manage the Python environment itself.
#
# ==============================================================================

# --- Environment and Configuration ---

# Use bash for all shell commands for consistency.
SHELL := /bin/bash

# Load environment variables from the .env file.
# The `-` prefix tells 'make' not to error out if the file doesn't exist.
ENV_FILE := .env
-include $(ENV_FILE)

# The 'export' directive makes variables available to shell commands.
export

# --- Core Script Configuration ---

# Define key paths. These require variables to be set in the .env file.
PYTHON                  := $(PYTHON_DIR)/.venv/bin/python3
ORCHESTRATOR_SCRIPT     := $(PYTHON_DIR)/orchestrator.py
VENV_DIR                := $(PYTHON_DIR)/.venv
MAINTENANCE_SCRIPT      := ./run_maintenance.sh
MAINTENANCE_CRON_SCHEDULE := 0 5 * * * # Daily at 5 AM

# Define the command for escalating privileges.
SUDO                    := sudo

# --- Dynamic Variables for Commands ---
# These variables are passed from the `make` command line to the orchestrator script.
# Example: make snapshot-one SERVICE_NAME="vpn" SNAPSHOT_NAME="test"
SERVICE_NAME  ?=
SNAPSHOT_NAME ?=
ARCHIVE_NAME  ?=
DESTINATION   ?=
VERIFY        ?= false # Set to 'true' to enable full data verification in check-repo

# --- Target Management ---

# .PHONY declares targets that are not actual files.
.PHONY: all help install setup-storage clean init-backup backup-all borg-analyze-all borg-export-keys-all
.PHONY: create-archive list-archives extract-archive delete-archive check-repo
.PHONY: snapshot-all snapshot-one list-snapshots-all list-snapshots-one create-service-dataset snapshot-destroy-all
.PHONY: docker-up docker-down docker-start docker-stop docker-create-networks
.PHONY: system-maintenance partial-maintenance full-maintenance
.PHONY: check-prereqs schedule-maintenance

# Set the default goal to 'help'. This runs if you just type 'make'.
.DEFAULT_GOAL := help

# --- Self-Documenting Help Target ---
help:
	@echo "Homelab VM Management Commands (via Python Orchestrator)"
	@echo "=============================================================================="
	@echo "Usage: make <command> [VARIABLE=\"value\"]"
	@echo ""
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-24s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo "=============================================================================="

# ==============================================================================
# --- Command Implementations ---
# ==============================================================================

# Internal Prerequisite Check (for orchestrator commands)
# -------------------------------------------------------
check-prereqs:
	@if [ ! -f "$(ENV_FILE)" ]; then \
		echo "[ERROR] Configuration file '.env' not found."; \
		exit 1; \
	fi
	@if [ ! -f "$(PYTHON)" ]; then \
		echo "[ERROR] Python virtual environment not found at '$(PYTHON)'."; \
		echo "Please run 'make install' first."; \
		exit 1; \
	fi

# --- Core Management (Shell Commands) ---

install:
	@echo "--> Starting Homelab Environment Setup..."
	@echo "--> Step 1/5: Updating and upgrading system packages..."
	$(SUDO) apt-get update -y
	$(SUDO) apt-get upgrade -y
	@echo "[SUCCESS] System is up to date."
	@echo ""
	@echo "--> Step 2/5: Installing system dependencies..."
	$(SUDO) apt-get install -y python3 python3-pip python3-venv borgbackup zfsutils-linux
	@echo "[SUCCESS] All required system packages are installed."
	@echo ""
	@echo "--> Step 3/5: Setting up Python virtual environment..."
	@if [ ! -d "$(VENV_DIR)" ]; then \
		echo "[INFO] Creating Python virtual environment in '$(VENV_DIR)'..."; \
		if [ -z "$${ADMIN_USER}" ]; then \
			echo "[ERROR] ADMIN_USER is not set in .env. Cannot create venv for the correct user."; \
			exit 1; \
		fi; \
		$(SUDO) -u $${ADMIN_USER} python3 -m venv "$(VENV_DIR)"; \
		echo "[SUCCESS] Virtual environment created."; \
	else \
		echo "[INFO] Virtual environment already exists."; \
	fi
	@echo ""
	@echo "--> Step 4/5: Installing Python packages..."
	$(SUDO) "$(VENV_DIR)/bin/pip" install -r "$(REQUIREMENTS_FILE)"
	@echo "[SUCCESS] Python packages installed successfully."
	@echo ""
	@echo "--> Step 5/5: Setting executable permissions..."
	$(SUDO) chmod +x $(PYTHON_DIR)/*.py
	$(SUDO) chmod +x $(MAINTENANCE_SCRIPT)
	@if [ -d "$(DOCKER_DIR)" ]; then \
		$(SUDO) chmod +x $(DOCKER_DIR)/*.sh; \
	fi
	@echo "[SUCCESS] Script permissions have been set."
	@echo ""
	@echo "------------------------------------------"
	@echo "  Homelab Environment Setup Complete!  "
	@echo "------------------------------------------"

clean:
	@echo "--> Cleaning up project files (virtual environment, cache)..."
	$(SUDO) rm -rf $(PYTHON_DIR)/.venv $(PYTHON_DIR)/__pycache__
	$(SUDO) find $(PYTHON_DIR) -type f -name "*.pyc" -delete
	$(SUDO) rm -f $(PYTHON_DIR)/*.log
	@echo "Cleanup complete."

# --- Cron Job Management ---

schedule-maintenance: check-prereqs ## Checks for the maintenance script and schedules it.
	@echo "--> Configuring daily maintenance cron job..."
	@# Step 1: Verify that the runner script exists first.
	@if [ ! -f "$(MAINTENANCE_SCRIPT)" ]; then \
		echo "[ERROR] Maintenance script not found at '$(MAINTENANCE_SCRIPT)'. Please create it."; \
		exit 1; \
	fi
	$(SUDO) chmod +x $(MAINTENANCE_SCRIPT)
	@echo "[INFO] Maintenance script found at '$(MAINTENANCE_SCRIPT)'."
	@# Step 2: Define the full cron job entry as a shell variable and check/add it.
	@# The entire if/else block below is executed in a single shell instance for safety.
	@set -e; \
	MAINTENANCE_COMMAND_PATH="$(CURDIR)/$(MAINTENANCE_SCRIPT)"; \
	CRON_JOB_ENTRY="$(MAINTENANCE_CRON_SCHEDULE) $${MAINTENANCE_COMMAND_PATH}"; \
	\
	if sudo crontab -l 2>/dev/null | grep -Fxq "$${CRON_JOB_ENTRY}"; then \
		echo "[SUCCESS] The maintenance cron job is already scheduled. No changes made."; \
	else \
		echo "[INFO] Scheduling the maintenance job..."; \
		(sudo crontab -l 2>/dev/null; echo "$${CRON_JOB_ENTRY}") | sudo crontab -; \
		echo "[SUCCESS] Cron job has been successfully scheduled."; \
	fi
	@echo "--------------------------------------------------------"


# --- Orchestrator-Managed Commands ---

setup-storage: check-prereqs ## Prepares storage: ZFS datasets, users, and permissions.
	$(SUDO) $(PYTHON) $(ORCHESTRATOR_SCRIPT) setup-storage

init-backup: check-prereqs ## Initializes Borg repos for all services.
	$(SUDO) $(PYTHON) $(ORCHESTRATOR_SCRIPT) init-backup

backup-all: check-prereqs ## Runs the main automated backup process for all services.
	$(SUDO) $(PYTHON) $(ORCHESTRATOR_SCRIPT) backup-all

borg-analyze-all: check-prereqs ## Analyzes and reports stats for all Borg repositories.
	$(SUDO) $(PYTHON) $(ORCHESTRATOR_SCRIPT) borg-analyze-all

borg-export-keys-all: check-prereqs ## Exports and verifies recovery keys for all repositories.
	$(SUDO) $(PYTHON) $(ORCHESTRATOR_SCRIPT) borg-export-keys-all

create-archive: check-prereqs ## Creates a new archive from a snapshot. Ex: make $@ SERVICE_NAME="vpn" SNAPSHOT_NAME="manual-snap"
	$(SUDO) $(PYTHON) $(ORCHESTRATOR_SCRIPT) create-archive --service-name "$(SERVICE_NAME)" --snapshot-name "$(SNAPSHOT_NAME)"

list-archives: check-prereqs ## Lists archives for a service. Ex: make $@ SERVICE_NAME="vpn"
	$(SUDO) $(PYTHON) $(ORCHESTRATOR_SCRIPT) list-archives --service-name "$(SERVICE_NAME)"

extract-archive: check-prereqs ## Extracts an archive to a destination. Ex: make $@ SERVICE_NAME="vpn" ARCHIVE_NAME="..." DESTINATION="/tmp/restore"
	$(SUDO) $(PYTHON) $(ORCHESTRATOR_SCRIPT) extract-archive --service-name "$(SERVICE_NAME)" --archive-name "$(ARCHIVE_NAME)" --destination "$(DESTINATION)"

delete-archive: check-prereqs ## Deletes a specific archive from a service repo. Ex: make $@ SERVICE_NAME="vpn" ARCHIVE_NAME="manual-snap"
	$(SUDO) $(PYTHON) $(ORCHESTRATOR_SCRIPT) delete-archive --service-name "$(SERVICE_NAME)" --archive-name "$(ARCHIVE_NAME)"

check-repo: check-prereqs ## Checks a service repo integrity. Ex: make $@ SERVICE_NAME="fun" [VERIFY=true]
	@VERIFY_FLAG=""; \
	if [ "$(VERIFY)" = "true" ]; then \
		VERIFY_FLAG="--verify"; \
	fi; \
	$(SUDO) $(PYTHON) $(ORCHESTRATOR_SCRIPT) check-repo --service-name "$(SERVICE_NAME)" $$VERIFY_FLAG

snapshot-all: check-prereqs ## Creates a recursive snapshot of all services. Ex: make $@ [SNAPSHOT_NAME="nightly"]
	@SNAPSHOT_ARG=""; \
	if [ -n "$(SNAPSHOT_NAME)" ]; then \
		SNAPSHOT_ARG="--snapshot-name \"$(SNAPSHOT_NAME)\""; \
	fi; \
	$(SUDO) $(PYTHON) $(ORCHESTRATOR_SCRIPT) snapshot-all $$SNAPSHOT_ARG

snapshot-one: check-prereqs ## Creates a snapshot for a single service. Ex: make $@ SERVICE_NAME="fun" [SNAPSHOT_NAME="pre-update"]
	@SNAPSHOT_ARG=""; \
	if [ -n "$(SNAPSHOT_NAME)" ]; then \
		SNAPSHOT_ARG="--snapshot-name \"$(SNAPSHOT_NAME)\""; \
	fi; \
	$(SUDO) $(PYTHON) $(ORCHESTRATOR_SCRIPT) snapshot-one --service-name "$(SERVICE_NAME)" $$SNAPSHOT_ARG

list-snapshots-all: check-prereqs ## Lists all snapshots under the parent dataset.
	$(SUDO) $(PYTHON) $(ORCHESTRATOR_SCRIPT) list-snapshots-all

list-snapshots-one: check-prereqs ## Lists snapshots for a single service. Ex: make $@ SERVICE_NAME="fun"
	$(SUDO) $(PYTHON) $(ORCHESTRATOR_SCRIPT) list-snapshots-one --service-name "$(SERVICE_NAME)"

create-service-dataset: check-prereqs ## Creates a new ZFS dataset for a service. Ex: make $@ SERVICE_NAME="new-service"
	$(SUDO) $(PYTHON) $(ORCHESTRATOR_SCRIPT) create-service-dataset --service-name "$(SERVICE_NAME)"

snapshot-destroy-all: check-prereqs ## Destroys a recursive snapshot by name. Ex: make $@ SNAPSHOT_NAME="temp-backup"
	$(SUDO) $(PYTHON) $(ORCHESTRATOR_SCRIPT) snapshot-destroy-all --snapshot-name "$(SNAPSHOT_NAME)"

docker-up: check-prereqs ## Builds, creates, and starts all services ('docker compose up -d').
	$(SUDO) $(PYTHON) $(ORCHESTRATOR_SCRIPT) docker-up

docker-down: check-prereqs ## Stops and removes all service containers ('docker compose down').
	$(SUDO) $(PYTHON) $(ORCHESTRATOR_SCRIPT) docker-down

docker-start: check-prereqs ## Starts all previously created (but stopped) service containers.
	$(SUDO) $(PYTHON) $(ORCHESTRATOR_SCRIPT) docker-start

docker-stop: check-prereqs ## Stops all running service containers without removing them.
	$(SUDO) $(PYTHON) $(ORCHESTRATOR_SCRIPT) docker-stop

docker-create-networks: check-prereqs ## Creates all Docker networks defined in the configuration.
	$(SUDO) $(PYTHON) $(ORCHESTRATOR_SCRIPT) docker-create-networks

system-maintenance: check-prereqs ## Stops services, performs system updates/cleaning, and restarts services.
	$(SUDO) $(PYTHON) $(ORCHESTRATOR_SCRIPT) system-maintenance

partial-maintenance: check-prereqs ## Runs snapshot-all then starts back all the services.
	$(SUDO) $(PYTHON) $(ORCHESTRATOR_SCRIPT) partial-maintenance

full-maintenance: check-prereqs ## Runs a full backup, then performs system maintenance.
	$(SUDO) $(PYTHON) $(ORCHESTRATOR_SCRIPT) full-maintenance
