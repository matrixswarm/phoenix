## Phoenix Cockpit

(from the MatrixSwarm ecosystem)

Phoenix Cockpit is the secure command bridge for the MatrixSwarm.
It’s not a toy GUI — it’s the operator’s deck: unlock the vault, connect to deployments, command the swarm, and watch the agents breathe.

Built with PyQt5.

- Enforces vault unlock → command flow (no unlocked vault, no ops).

- Visualizes universes, deployments, agents, and their threads.

- Streams logs, status, and service responses in real time.

- Every packet verified, every heartbeat tracked. 
---

## ⚡ Quick Start

### Install
````bash
pip install -e .
````
### Unlock Vault

When Phoenix starts, you’ll see only the 🔐 UNLOCK button.
Enter your vault password — the cockpit decrypts and loads trusted deployments.
No unlock = no swarm control.

#### Connect to Deployment

Right-click a deployment → 🔌 Connect.
Agents will light up in the tree.

#### Issue Commands

- Right-click an agent → restart, replace, hotswap, or delete. note: restart and hotswap are being refactored and will be implemented shortly 

- Use control panels (logs, NPC panel, forensic panel) to issue service requests.

- All commands travel securely:

```nginx
 Phoenix → matrix_https → Matrix → Agent → WebSocket Relay → Phoenix
````
### 🌌 Example Session

matrixd list <- command on server

````bash
🌌 phoenix :: 20 agents, 907.7 MB RAM, 11.3% CPU
 └── PID 2369254 :: matrix
 └── PID 2369264 :: guardian-1
 └── PID 2369265 :: matrix-https
 └── PID 2369266 :: websocket-relay
 └── PID 2369267 :: apache_watchdog-1
 └── PID 2369271 :: mysql-red-phone
 └── PID 2369272 :: log_sentinel
 └── PID 2369274 :: invisible-man
 └── PID 2369276 :: gatekeeper
 └── PID 2369279 :: discord-delta-5
 └── PID 2369281 :: forensic-detective-1
 └── PID 2369284 :: system-health-1
 └── PID 2369286 :: network-health-1
 └── PID 2369287 :: redis-hammer
 └── PID 2369289 :: telegram-bot-father-2
 └── PID 2369291 :: golden-child-4
 └── PID 2369431 :: guardian-2
 └── PID 2369471 :: guardian-3
 └── PID 2369506 :: guardian-4
````
Phoenix shows them in tree view with live updates.
Click an agent → inspect threads, spawn count, flip-tripping alerts, and configuration.

### Creating a Deployment Directive in Phoenix

1. **Start from a Template**  
   Load a directive skeleton in Directive Manager (guardian ring, relays, watchdogs).

2. **Assign Connections**  
   Use Connection Manager to map saved endpoints (HTTPS, WSS, Discord, Telegram, etc.).

3. **Select Options**  
   - **Clown-car** (embed sources in directive) → hidden by default.  
   - **Hashbang** (SHA256 hash per agent, verified on spawn) → optional.  

4. **Encrypt and Save**

   "universe" is whatever you call your swarm(cluster of agents) at boot
   
   Phoenix encrypts your directive into:  
matrix/boot_directives/<universe>.enc.json   # (relative to project root)

5. **Swarm Key**  
Phoenix also saves the matching swarm key:    
matrix/boot_directives/keys/<universe>.key     # (relative to project root)
*Same name as directive, minus `.enc.json`.* 
 
6. **Boot the Swarm**  
Run:  
```bash
  matrixd boot --universe phoenix
````
Matrix auto-resolves the directive + key, decrypts in memory, and spawns the agents slice by slice.

### Security Principles

- Vault key exists only in memory during session.
- No fallback configs, no plaintext state.
- TLS with SPKI pinning for HTTPS/WSS connections.
- Every packet cryptographically signed.
- Punji traps enforce singleton agents.

### Architecture
- Phoenix GUI (PyQt5)

    - Unlocks vault

    - Displays deployments + agent tree

    - Sends cmd_service_request via HTTPS

- MatrixSwarm Core

    - Routes packets to agents by service role

- Agents

    - Do their jobs (watchdog, oracle, npc-simulator, forensic)

    - Respond back with dict packets

- WebSocket Relay

    - Broadcasts responses to Phoenix

### Install Phoenix as a Desktop App
````bash
  pip install -e .
  phoenix
````

### License
Released under the MatrixSwarm Community License v1.1 (Modified MIT).
Free for personal, research, and non-commercial use.
For commercial use, contact: swarm@matrixswarm.com

### Authorship
MatrixOS wasn’t auto-generated.
It was co-created by Daniel F. MacDonald (vision, design, code) and ChatGPT (The General) (iteration, drafting, lore).

Every agent, directive, and heartbeat came from collaboration.

### Resources
GitHub: github.com/matrixswarm/matrixswarm

GitHub: github.com/matrixswarm/matrixos

Docs: matrixswarm.com

Discord: Join the Hive

Python: pip install matrixswarm

Codex: /agents/gatekeeper

Twitter/X: @matrixswarm

### Join the Hive
Join the Swarm → https://discord.gg/CyngHqDmku
Report bugs, fork the swarm, or log your own Codex banner.

### Status
Pre-release.

GUI live

Vault integrated

Recruiting contributors who think in systems.