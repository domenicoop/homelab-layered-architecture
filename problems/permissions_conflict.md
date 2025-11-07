# **The `userns-remap` Permissions Conflict with a Multi-Service Docker Stack**

#### **1. Executive Summary (TL;DR)**

The core problem was a fundamental conflict between the enhanced security of Docker's User Namespace Remapping (`userns-remap`) and the internal startup procedures of standard container images, particularly PostgreSQL. The remapped `root` user inside a container lacks the true `root` privileges on the host needed to change file ownership (`chown`), causing the container to fail on startup.

The solution was a two-part strategy:
1. **Host-Side Preparation:** A comprehensive shell script (`shared_group.sh`) was created to pre-configure the host filesystem. It creates dedicated host users that mirror the remapped UIDs of each container's internal user (`postgres`, `node`, etc.) and sets the correct ownership on the service-specific data directories *before* the containers start.
2. **Container-Side Configuration:** The `docker-compose.yml` was modified to discard the generic `${PUID}`/`${PGID}` variables. Instead, each service was explicitly configured with a `user: "UID:GID"` directive that matched the specific internal user it was designed to run as.

This approach ensures the containers start with the file permissions they already expect, completely bypassing the failing `chown` operations and resolving the conflict.

---

#### **2. The Core Problem in Detail**

The entire issue stemmed from the use of Docker's `userns-remap` security feature.

- **What `userns-remap` Does:** It maps the `root` user (UID 0) inside a container to a high-numbered, unprivileged user on the host (e.g., UID `100000`). This is a powerful security measure that prevents a container breakout from granting an attacker `root` on the host machine.

- **How Containers Behave:** Many official container images (especially databases like PostgreSQL) are designed to be robust. Their entrypoint script, which runs on startup, performs self-healing and initialization checks. A key check is to ensure its data directory (`/var/lib/postgresql/data`) is owned by its internal, non-root user (e.g., `postgres`, UID `999`). To do this, the script runs `chown -R postgres:postgres ...`.

- **The Conflict:** When the PostgreSQL container started as `root` (remapped to host UID `100000`), its entrypoint script tried to change the file ownership to the `postgres` user (remapped to host UID `100999`). On a Linux system, only the true `root` user can change ownership from one user to another. Since the container's process was running as the unprivileged user `100000`, the kernel denied this request.

This resulted in the initial error: `chown: changing ownership of '...': Operation not permitted`.

---

#### **3. The Solution: A Two-Part Strategy**

The solution was to stop fighting the container's entrypoint script and instead prepare the environment so the script's checks would pass without needing to perform any failing operations.

##### **Part A: Preparing the Host Environment (The `shared_group.sh` Script)**

A comprehensive, idempotent shell script was developed to configure the host filesystem.

**The script's responsibilities are:**

1. **Create Mirrored Host Users:** For every distinct user inside the Docker stack (`root`, `postgres`, `node`), the script creates a corresponding system user on the host with the correct remapped UID.
  - `dockeruser`: UID `100000` (maps to in-container UID `0`)
  - `docker_user_999`: UID `100999` (maps to in-container UID `999` for Postgres/Redis)
  - `docker_user_1000`: UID `101000` (maps to in-container UID `1000` for Immich server/ML)
2. **Establish a Shared Group:** It creates a group (`storage-access`) and adds the host's administrative user (`manager`) and all the remapped Docker users to it. This allows the administrator to easily access and manage all container data without needing `sudo` for every operation.
3. **Apply Default and Specific Permissions:**
  - First, it sets the *default* ownership of the entire `/storage` directory to `dockeruser:storage-access`.
  - Then, it applies *specific overrides* for the directories that need them. For example, it runs `chown -R 100999:storage-access /datapool/services/immich/postgres`, setting the precise ownership that the PostgreSQL container expects.
4. **Set Group Inheritance:** It uses `chmod g+s` (the `setgid` bit) to ensure that any new files or directories created by the containers automatically inherit the `storage-access` group, maintaining administrative access.

##### **Part B: Configuring the Docker Containers (`docker-compose.yml`)**

The `docker-compose.yml` was updated to explicitly tell each service which user to run as. This is a more robust and clear approach than a global PUID/PGID.

1. **Removed Global Variables:** The use of `${PUID}:${PGID}` was eliminated.
2. **Set Per-Service Users:** Each service was given a specific `user: "UID:GID"` directive:
  - **`immich-database`:** `user: "999:0"`. This was the critical insight from the [GitHub discussion](https://github.com/immich-app/immich/discussions/13124). The Immich-specific image runs its `postgres` user (UID `999`) with the primary group of `root` (GID `0`).
  - **`immich-server` & `immich-machine-learning`:** `user: "1000:1000"`. These Node.js services run as the standard `node` user.
  - **`immich-redis`:** `user: "999:999"`. This service runs as its own internal `valkey`/`redis` user.
  - **`ts-immich`:** The `user:` line was removed entirely, allowing the container to run as its default `root` user, which is necessary for its networking operations.

---

#### **4. Final Outcome**

By combining these two strategies, the system now works in perfect harmony:

1. The `shared_group.sh` script pre-configures the host directories to the exact ownership state that each container requires.
2. The `docker-compose.yml` file starts each container process with the correct user and group ID.
3. When a container starts, its entrypoint script runs its ownership checks. It sees that the files are *already* owned by the correct user, so the checks pass instantly, and the failing `chown` commands are never even attempted.

The initial error is resolved, the stack runs correctly, and the host administrator retains easy access to all data through the shared `storage-access` group.

---

## The Core Problem: PostgreSQL's Internal Security

For security and data integrity, the PostgreSQL database server is designed to not run as the `root` user. Instead, it runs as a dedicated, non-root user, which is typically `postgres`.

A critical part of the official PostgreSQL container's startup process is a script that verifies the ownership of its data directory (`/var/lib/postgresql/data`). This script ensures the directory is owned by the `postgres` user (inside the container, this user has a User ID of 999). If the ownership is incorrect, the script tries to fix it by running a `chown` command.

### The Conflict with Docker's `userns-remap`
Your setup uses Docker's User Namespace Remapping (`userns-remap`), a powerful security feature that prevents a process inside a container from having actual `root` privileges on the host machine.

Here's how the conflict happens:
1.  **Remapping:** `userns-remap` maps the container's internal `root` user (UID 0) to an unprivileged, high-numbered user on your host (e.g., UID 100000).
2.  **Startup Script:** The PostgreSQL container starts, and its entrypoint script (running as the remapped `root`) tries to `chown` the data directory to the `postgres` user (which is remapped to host UID 100999).
3.  **Permission Denied:** On a Linux system, only the true `root` user can change the ownership of a file from one user to another. Since the container's process is running as the unprivileged host user `100000`, the operating system denies the `chown` request.
4.  **Container Fails:** The startup script receives an "Operation not permitted" error and exits, causing the container to fail.

### The Solution: Pre-emptive Configuration
The solution, implemented by your `shared_group.sh` script, is to prepare the host environment *before* the container starts, so the container's checks pass without needing to change anything.

1.  **Create Mirrored Host User:** The script creates a user on the host (`docker_user_999`) with the exact UID that the container's `postgres` user will be mapped to (100999).
2.  **Set Ownership in Advance:** The script runs `chown -R 100999:"$SHARED_GROUP" ...` on the PostgreSQL data directory. This sets the ownership to the correct remapped user *before* the container even exists.
3.  **Specify User in Docker Compose:** The `docker-compose.yml` explicitly tells the container to run its process as `user: "999:0"`. This means the postgres process starts as user 999 (which is remapped to 100999 on the host) and group 0.
4.  **Successful Startup:** When the container starts, its script checks the data directory's ownership. It finds that the directory is already owned by the correct user (itself), so the `chown` command is skipped, the error is avoided, and the database starts successfully.