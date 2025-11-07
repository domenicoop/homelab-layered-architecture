# Remote Access

The Remote Access service functions as a multi-purpose network gateway by using Tailscale. It securely connects your homelab to your private Tailscale network and provides two main capabilities: acting as a **subnet router** to access your local network remotely and as an **exit node** to route your internet traffic through your home connection.

To learn what can you do with Tailscale, you can read the official documentation [here](https://tailscale.com/kb/1017/install). The following are only the features that were useful for me.

### Subnet Router

The container is configured to act as a **subnet router**, advertising yotheur local network (e.g., `xxx.xxx.0.0/24`) to all other devices on the Tailscale network. This allows to securely access any device on the home LAN from a remote location as if you were physically there, not just the services running on the VM.

### Exit Node

By using the `--advertise-exit-node` argument, the service also offers itself as an **exit node**. This allows you to route all internet traffic from a remote device (like your phone or laptop on public Wi-Fi) through your home's internet connection.

---

## Configuration Details

The service's functionality is enabled by specific settings in its Docker Compose configuration.

- **Kernel-Level Networking**: The service operates in a high-performance kernel networking mode. This is achieved by mounting the host's TUN device (`/dev/net/tun`) into the container and explicitly setting `TS_USERSPACE=false`. This is more efficient than the default userspace mode.
- **IP Forwarding**: The container has IP forwarding enabled via `sysctls` settings (`net.ipv4.ip_forward=1` and `net.ipv6.conf.all.forwarding=1`). This is a critical kernel setting that permits the container to forward network packets between the Tailscale virtual network and your physical home network, which is the essential function of a router.
- **Elevated Privileges**: To manage network interfaces and routing rules, the container requires the `net_admin` and `sys_module` capabilities.
- **Persistent State**: The service's state and configuration are stored on the host using volumes, ensuring that the node's identity is preserved across restarts and you don't need to re-authenticate it.
- **Custom DNS**: The container is configured to use the internal DNS server, ensuring that local domain resolution works correctly even when connected remotely.