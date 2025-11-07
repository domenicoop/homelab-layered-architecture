# My Homelab Layered Architecture

This repository documents the architecture, configuration, and solutions behind my personal Homelab. The primary goal is to present a complete, working setup that prioritizes stability, security, and ease of use.

This is not intended as a universal "how-to" guide, but rather as a detailed blueprint of one specific implementation. The choices made here were influenced by the hardware I had available, the problems I encountered, and the specific technologies I wanted to explore.

## How to Read The Docs

The architecture is organized into distinct layers and the repository mirrors it with the same structure. This modular design allows you to work at different layers, focusing on the actual layer you are working on.

Each layer's directory contains its own detailed documentation:

- [`/host-layer/`](./layers/0_host/0_index.md)
    This layer covers the physical machine and the virtualization software. It details the setup of macOS as a host, using VMware Fusion for virtualization, and the management of encrypted storage for the VMs.

- [`/guest-layer`](./layers/1_guest/0_index.md)
    This layer focuses on the main services VM. It includes help and tips for installing and hardening Debian, configuring ZFS for data management, setting up a secure Docker environment, and implementing the backup strategy.

- [`/services-layer/`](./layers/2_services/0_index.md)
    This is the application layer. It explains the "hub-and-spoke" networking model that ensures services are isolated and securely exposed.

It is recommend the following approach for a comprehensive understanding:

1. Begin with the main **[Architecture](./layers/architecture.md)** file. It provides the high-level philosophy and an overview of the entire architecture.
2. **Follow the Layers Sequentially:** For the most logical flow, read the layers in order: **Layer 0 → Layer 1 → Layer 2**. This will walk you through the entire build process from the ground up.
3. **Understand the "Why" Before the "How":** Most documents are split into two parts. They first explain the **Concepts** the reasoning and design choices behind a particular setup. Then, they could provide an example for the actual implementation. Understanding the "why" makes the "how" much clearer.

## "Why didn't you use...?"

This is a hobby project, built during the spare moments I have to experiment and learn. If you're wondering why a particular tool or technology wasn't used, the answer is likely one of the following:

- I wasn't aware of it at the time.
- The current solution worked well enough for my needs.
- I simply wanted to play with a specific technology to understand it better.

Everything here can be improved. Suggestions and constructive feedback are always appreciated. However, the primary goal was to build something functional and understandable, not necessarily to use the most complex or feature-rich tools available.

---

## **Disclaimer**

This repository is for informational and educational purposes only. All scripts, configurations, and documentation are provided 'as is' and without warranty of any kind. I am not responsible for any damage, data loss, or security vulnerabilities that may arise from implementing this architecture.

The artifacts here represent a working solution *for me*, but they are not a substitute for the official documentation of each tool. **Always refer to the official docs as the primary source of truth.**
