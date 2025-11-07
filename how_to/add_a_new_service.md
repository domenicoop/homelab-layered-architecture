# How to add a new service

## Phase 1: Service Definition & Planning

### Step 1: Identify Service Components

Analyze the service you want to add.

 - **What containers make up the stack?** (e.g., a "wiki" service might have `wikijs-app` and `wikijs-db`).
 - **How do they communicate?** (e.g., the app container needs to reach the DB container).

### Step 2: Identify Persistent Data & Permissions

This is the most critical step for integrating with the homelab's security model.

 - **What data needs to be saved?** For each container, list the paths that must persist (e.g., `wikijs-db` needs `/var/lib/postgresql/data`).
 - **What user *inside* the container owns this data?** Check the container's documentation.
   - If it's `postgres`, its default UID is `999`.
   - If it's a general app, it might be `1000`.
   - If it's `root`, it's UID `0`.
 - **Map this to your host's remapped UIDs.**
   - `postgres` (UID 999) $\rightarrow$ Host Remapped UID `100999`.
   - App (UID 1000) $\rightarrow$ Host Remapped UID `101000`.
   - `root` (UID 0) $\rightarrow$ Host Remapped UID `100000`.

You now have a "shopping list" of what you need to build. For our `wiki` example, you need:

1. **Storage:** A ZFS dataset for the DB, owned by host UID `100999`.
2. **Network:** A dedicated Docker network.
3. **Config:** A `docker-compose.yml` that uses these.

-----

## Phase 2: Storage Preparation

Now you create the storage foundation based on your plan from Phase 1.

### Step 3: Create the ZFS Dataset

Every service gets its own dataset for isolated, atomic snapshots.

 - **Action:** Create the parent ZFS dataset for the new service.
 - **Example:** `sudo zfs create datapool/services/wiki`

### Step 4: Create Volume Directories & Set Permissions

Create the specific directories you planned in Step 2 and apply the correct ownership.

 - **Action:**
  1. Make the directory: `sudo mkdir -p /datapool/services/wiki/db_data`
  2. Set ownership using the remapped UID you identified: `sudo chown 100999 /datapool/services/wiki/db_data`

-----

## Phase 3: Network Preparation

Create the isolated "spoke" network for your service stack.

### Step 5: Create the Isolated Docker Network

 - **Action:** Use the `docker network create` command.
 - **Example:** `docker network create wiki_net`

-----

## Phase 4: Service Deployment

With all the dependencies (storage, permissions, network) in place, you can now define and launch the service.

### Step 6: Define the Service (docker-compose.yml)

Create the directory and compose file that defines your service.

 - **Action:**
  1. Create the service definition directory: `mkdir /home/runner/services/wiki`
  2. Create the `/home/runner/services/wiki/docker-compose.yml` file.
 - **Key Compose File Rules:**
   - **Volumes:** Map the container's data path to the ZFS directory you prepared in Step 4 (e.g., `- /datapool/services/wiki/db_data:/var/lib/postgresql/data`).
   - **Network:** Connect all containers in the stack to the `external` network you created in Step 5 (e.g., `wiki_net`).
   - **No Ports:** **Do not** use the `ports:` section. The service must not be exposed to the host.

### Step 7: Launch and Test the Service

 - **Action:** `cd /home/runner/services/wiki` and run `docker compose up -d`.
 - **Verification:** Check the logs (`docker compose logs -f`) to ensure all containers started correctly and that there are no "Permission Denied" errors. This confirms your storage and permissions are correct.

-----

## Phase 5: Network Routing & Exposure

Your service is now running correctly but is completely isolated. This phase connects it to the outside world via the Caddy "hub."

### Step 8: Connect Caddy to the Service Network

Caddy must be attached to the new network to act as a "bridge."

 - **Action:**
  1. Edit Caddy's `docker-compose.yml` (e.g., `/home/runner/services/reverseproxy/docker-compose.yml`).
  2. Add `wiki_net` to its `networks:` list.
  3. Restart Caddy: `cd /home/runner/services/reverseproxy && docker compose up -d`

### Step 9: Configure the Caddy Route

Tell Caddy how to route traffic to your new service.

 - **Action:**
  1. Edit your `Caddyfile`.
  2. Add a new block that maps your desired domain to the service's container name and internal port.
 - **Example:**
  ```caddy
  wiki.homelab.lan {
   reverse_proxy wikijs-app:3000
   tls internal
  }
  ```

### Step 10: Configure DNS

The final step is to tell your network what `wiki.homelab.lan` means.

 - **Action:** Log in to your DNS server (Pi-hole, AdGuard Home) and add a new A-record for `wiki.homelab.lan` that points to the **static IP address of your Caddy VM**.
 - **Verification:** You should now be able to access `https://wiki.homelab.lan` in your browser.

-----

## Phase 6: Backup Integration

Your service is fully deployed and accessible. The final step is to add it to the backup rotation.

### Step 11: Initialize the Backup Repository

Your architecture requires one dedicated Borg repository for each ZFS dataset.

 - **Action:** Run a `borg init` command to create the new, empty repository on your remote backup storage. The repository name should correspond to the ZFS dataset name.
 - **Example:** `sudo borg init --encryption=repokey-blake2 ssh://user@remote/./borg-backups/datapool_services_wiki`

Your new service is now fully integrated, secure, and backed up.

---

## How the Automation Layer Maps to This Flow

This conceptual flow maps perfectly to your automation scripts:

 - **Phase 1 (Planning):** Still fully manual.
 - **Phase 2 (Storage):**
  1. You **manually** add `wiki/db_data:REMAPPED_POSTGRES_UID` to your `.env` file's `SERVICE_VOLUME_PATHS_AND_OWNERS` list.
  2. You run `make setup-storage`. The `storage_manager.py` script automatically handles both **Step 3 (ZFS create)** and **Step 4 (mkdir/chown)** for you.
 - **Phase 3 (Network):**
   - This is handled by `docker network create`. The `docker_manager.py` script automatically finds the `external: true` new network in your `wiki/docker-compose.yml` and create it (**Step 5**).
 - **Phase 4 (Deployment):**
   - You **manually** create the `docker-compose.yml` file (**Step 6**).
   - You run `make docker-up`, which runs `docker compose up` for you (**Step 7**).
 - **Phase 5 (Routing):**
   - This remains **fully manual**. You must still edit Caddy's `docker-compose.yml` and `Caddyfile`, and configure your DNS server.
 - **Phase 6 (Backup):**
   - You run `make init-backup`. The `orchestrator.py` script finds your new `datapool/services/wiki` dataset, sees it has no matching Borg repo, and automatically runs `borg init` for you (**Step 11**).
