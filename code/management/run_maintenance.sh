#!/bin/bash
#
# This script is designed to be called by cron to execute the full-maintenance task.
# It automatically locates the project root directory based on its own location.

set -e # Exit immediately if a command exits with a non-zero status.

# --- Determine Project Directory ---
# This finds the directory the script is in, then goes up one level to the project root.
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
PROJECT_DIR="$SCRIPT_DIR"

# --- Setup Logging ---
# Create a logs directory in the project root if it doesn't exist
LOG_DIR="${PROJECT_DIR}/.logs/run_mantainance"
mkdir -p "$LOG_DIR"
LOG_FILE="${LOG_DIR}/maintenance_cron.log"

# --- Execute Maintenance ---
echo "--- Starting Full Maintenance: $(date) ---" >> "${LOG_FILE}"

# Navigate to the project root and execute the make command.
# All output (stdout & stderr) is appended to the log file.
cd "${PROJECT_DIR}" && /usr/bin/make full-maintenance >> "${LOG_FILE}" 2>&1

echo "--- Finished Full Maintenance: $(date) ---" >> "${LOG_FILE}"
echo "" >> "${LOG_FILE}"

exit 0