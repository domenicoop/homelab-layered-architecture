# A generic service

Each application in this homelab is deployed as a self-contained **stack** using a single `docker-compose.yml` file. This approach ensures that all services follow a consistent set of architectural principles for security, isolation, and manageability.

This guide uses the **Photo** service as a working example to illustrate these core concepts.

---

### 1 Structure and Naming Philosophy

Each service is self-contained within its own directory. This structure is built on a specific naming philosophy that separates the **function** of a service from its **implementation**.

  - **The Service (The "What"):** The directory name defines the *function* or *problem* the service solves (e.g., `git`). This name is abstract and represents "what you need."
  - **The Implementation (The "How"):** The container and network names inside the `docker-compose.yml` file describe the *specific software* being used (e.g., `gitversioncontrol-gitea`).

If you later decide to replace Gitea with GitLab, the service is still just `git`. You only change the implementation *inside* the `git` directory, and the rest of your system (like your Caddyfile) remains largely unchanged. This also prevents container name conflicts if the same image (e.g., `postgres`) is used by multiple services.

A typical service directory looks like this:

```
git/                     <-- The Service
├── docker-compose.yml   <-- The Implementation
├── Dockerfile           <-- (Optional) Custom build
└── .env                 <-- Configuration & secrets
```

This philosophy extends to the files themselves. Inside the `docker-compose.yml`, the container and network names reflect the specific implementation:

```yaml
services:
  gitversioncontrol-gitea:  # Specific implementation name
    ...
  gitversioncontrol-gitea-db:
    ...

networks:
  gitversioncontrol_network: # Specific implementation network
    external: true
```

And the `Caddyfile` configuration maps the functional domain (`git.homelab.lan`) to the specific implementation container (`gitversioncontrol-gitea`):

```caddy
git.homelab.lan {
    reverse_proxy gitversioncontrol-gitea:3000
    tls internal
}
```

### 2. Multi-Container Stacks

Services are rarely a single container. A modern application stack typically consists of several interconnected components. The Immich stack, for example, is composed of four distinct services working together:
- `immich-server`: The main application backend.
- `immich-machine-learning`: A dedicated container for processing tasks like object recognition.
- `immich-redis`: A Redis container for caching and message queuing.
- `immich-database`: A PostgreSQL database for storing all metadata.

---

### 3. Network Isolation

Every service stack is deployed onto its own **dedicated, private Docker network**.
- **Complete Isolation**: The Immich stack runs exclusively on the `photo_net` network. Containers on this network are completely isolated and cannot see or interact with containers from other service stacks (e.g., Git). This is a fundamental security principle of the "hub-and-spoke" model.
- **Internal Communication**: Containers within the same stack communicate with each other using their service names as hostnames. For instance, the Immich server connects to its database using the hostname `immich-database`, which works thanks to Docker's internal DNS.
- **External Network Definition**: The network is defined as `external: true`, meaning it is created and managed externally, not by Docker Compose itself.

---

### 4. Security Principles

Security is built into the design of every service stack.
- **No Exposed Ports**: Noticeably, **no container in the stack exposes ports** to the host VM. There is no `ports:` section. All incoming traffic must be routed through the Caddy reverse proxy, which is the only service that listens on the network. This drastically reduces the attack surface.
- **Principle of Least Privilege**: Each container is configured to run as a specific, non-root user (e.g. via the `user:` directive). For example, the server runs as user `1000:1000` (the internal `node` user), while the database runs as `999:0` (the `postgres` user). This integrates directly with the host's `userns-remap` security model, ensuring that processes inside the container have minimal privileges on the host filesystem.

---

### 5. Data Persistence and Configuration

- **Persistent Storage**: Critical data that must survive container restarts and be backed up is stored on the host's ZFS filesystem. This is achieved by mounting host paths as volumes, such as `${IMMICH_DB_DATA_LOCATION}:/var/lib/postgresql/data` for the database.
- **Configuration via Environment**: All configuration, especially secrets like database passwords and usernames, is passed into the containers as environment variables. These values are stored in a separate `.env` file, cleanly separating configuration from the service definition.

---

### 6. Reliable Startup

To ensure the stack starts up in a predictable and stable manner, dependencies and health checks are used.
- **Startup Order**: The `depends_on` directive ensures that the main Immich server will only start after its dependencies are running. It waits for Redis to have started and, more importantly, for the database to pass its health check and be fully ready to accept connections.
- **Health Checks**: The database and Redis containers have `healthcheck` sections that define a command to test their status, ensuring they are not just running but are actually healthy.
