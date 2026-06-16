# Mass Hardware Management — 10 Additional Methods

> Supplement to the Tramplus Summer Intern Onboarding meeting (Notion).
> These methods go beyond what was discussed in the meeting record.

---

## 1. PXE / iPXE Network Booting & Unattended Provisioning

**What it is**: Machines boot from the network (not local disk), pulling a kernel + initramfs via TFTP/HTTP, then auto-install the OS without any human interaction.

**How it works**:
- DHCP server tells the bare-metal machine where to find the bootloader
- iPXE (enhanced PXE) fetches boot scripts and OS images over HTTP (faster than TFTP)
- A preseed/kickstart/autoinstall file answers all installer prompts automatically
- After OS install, cloud-init or Ansible applies final configuration

**Tools**: dnsmasq + TFTP, iPXE, MAAS, Foreman, Cobbler, Digital Rebar

**Best for**: Rack-scale deployments where you add 10–100 servers at once and want them identical.

---

## 2. BMC / IPMI / Redfish Out-of-Band Management

**What it is**: Managing hardware through a separate controller (Baseboard Management Controller) that works even when the OS is dead, the machine is off, or the disk is blank.

**What you can do from anywhere**:
- Power on/off/cycle/reboot remotely
- Change BIOS boot order (e.g. force network boot next cycle)
- Read hardware sensors (temperature, fan speed, voltage)
- Capture a remote console (KVM — see screen as if you were plugged in)
- Mount virtual ISO images as if a physical CD-ROM is inserted
- Update firmware remotely

**Protocols**:
- **IPMI** (oldest, universal, less secure) — works on nearly everything pre-2018
- **Redfish** (modern, REST+JSON, DMTF standard) — Dell iDRAC 9+, HPE iLO 5+, Supermicro X11+, Lenovo XCC, OpenBMC
- **Vendor-specific**: Dell iDRAC, HPE iLO, Fujitsu iRMC

**Tools**: ipmitool, redfish-client, bmc-adapters Python library, OpenStack Ironic

---

## 3. Infrastructure as Code (IaC) for Bare Metal

**What it is**: Treating physical servers the same way you treat cloud VMs — define their entire lifecycle in version-controlled code (YAML, Terraform, Ansible).

**The workflow**:
```yaml
# Declarative: "I want 8 servers with these specs in this rack"
servers:
  - rack: A3
    count: 8
    cpu: 64 cores
    ram: 256 GB
    gpu: NVIDIA H100 × 4
    os: Ubuntu 24.04
    raid: RAID-10 (4× NVMe)
    network: 2×25 GbE bonded
    bios_policy: max-performance
```

**The tooling**:
- **Terraform + MAAS provider** — Provision physical machines via API just like `terraform apply` on AWS
- **Ansible + IPMI/Redfish modules** — Push BIOS config, RAID setup, firmware updates via playbooks
- **Digital Rebar + RackN** — Define rack definitions as code, scan IPMI ranges, auto-provision entire racks

**Why it matters**: Infrastructure code lives in git. You get diff, review, rollback, and audit trails for hardware changes — same as software.

---

## 4. Golden Image & Virtual Media Boot Provisioning

**What it is**: Instead of installing an OS from scratch every time, you maintain a single "golden image" (a pre-configured OS snapshot with all drivers and security hardening applied) and clone it to new machines rapidly.

**How it differs from network boot**:
| Network Boot (PXE) | Golden Image Boot |
|---|---|
| Installs OS from scratch | Copies pre-built image |
| Slower (15–30 min per node) | Fast (<5 min per node) |
| Custom per machine via autoinstall | Identical fleet, customized via cloud-init |
| Needs DHCP + L2 network | Works over L3 (no DHCP needed with virtual media) |

**Virtual media boot** (Redfish feature): Mount an ISO/IMG file as a virtual CD-ROM via HTTPS. The remote BMC makes the server think a physical disc is inserted. This works over routed networks and requires no local DHCP/TFTP infrastructure.

**Tools**: Packer (image builder), Virtual Media via Redfish, MAAS-image-builder

---

## 5. Hardware Commissioning & Automated Burn-In Testing

**What it is**: Before deploying a machine to production, run a suite of hardware tests to catch faulty components before they cause real problems.

**Typical commissioning tests**:
- **CPU**: stress-ng — thermal throttling, SSE/AVX, all-core turbo sustained
- **Memory**: memtest86+ — full address space, ECC error injection
- **Storage**: fio — sequential/random I/O, SMART health, bad blocks; NVMe endurance
- **Network**: iperf3 — bandwidth, packet loss, NICS bonding failover
- **GPU**: NVidia DCGM diagnostics — memory, NVLink health, PCIe errors, thermal
- **Power**: PSU redundancy test (pull one cord, system stays up)

**Automation**: 
- **MAAS** runs commissioning scripts automatically after discovery and marks machines "Ready" or "Failed"
- **Digital Rebar** has `universal-baseline` stage for hardware validation
- **NVIDIA DGX Manageability** captures as-received hardware baselines and runs pre-deployment validation

**Why it matters**: A GPU server with one bad RAM stick can silently corrupt model training results for weeks before anyone notices.

---

## 6. Fleet-Wide Automated Firmware & BIOS Management

**What it is**: Keeping BIOS, BMC firmware, GPU firmware, NIC firmware, and storage controller firmware consistent and up-to-date across hundreds of servers.

**The challenge**: Manual firmware updates don't scale. Different vendors (Dell, HPE, Lenovo, Supermicro) each have their own tools and formats.

**The solution**:
1. **Version inventory**: Scan all servers, record current firmware versions into a database
2. **Policy definition**: "All H100 GPUs must be on firmware ≥ 6.8, all Dell R760xa on BIOS ≥ 2.1.3"
3. **Staged rollout**: Update 5% of fleet → wait 48h → 20% → 50% → 100%. Auto-rollback if error rate spikes.
4. **Compliance dashboard**: `SELECT count(*) WHERE bios_version < target` — shows drift in real time

**Tools**: 
- **NVIDIA**: NVSM (NVIDIA System Management), NVQC for GPU firmware
- **Dell**: iDRAC + RACADM + OME (OpenManage Enterprise)
- **HPE**: iLO + SUM (Smart Update Manager)
- **Open-source**: Firmware Update Manager for LVFS (Linux Vendor Firmware Service), fwupd
- **Orchestration**: Ansible + Redfish, Digital Rebar universal-hardware workflow, Karios firmware automation

---

## 7. Kubernetes-Native GPU Cluster Orchestration

**What it is**: Running GPU workloads (AI training, image generation, inference) on Kubernetes with GPU-aware scheduling, not just treating GPUs as dumb integer resources.

**Key technologies**:

**NVIDIA GPU Operator**: Automates driver deployment, device plugin, monitoring (DCGM), and MIG configuration across the cluster. One Helm install, all nodes get consistent GPU drivers.

**Dynamic Resource Allocation (DRA)** — Kubernetes 1.34+ (GA):
- Old way: `resources.limits.nvidia.com/gpu: 4` — just a count
- New way: Request GPUs by attributes — "I need 2 H100s on the same NVSwitch domain, with NVLink, from the same NUMA node"
- Uses ResourceClaim + CEL (Common Expression Language) for structured GPU requests
- GPU Operator v26.x provides stable DRA + CDI (Container Device Interface) support

**Topology-aware scheduling**:
- **KAI Scheduler** (NVIDIA): GPU-aware bin-packing, gang scheduling, fair-share, hierarchical quotas
- **Volcano**: Gang scheduling + DRF fairness for distributed training (all-or-nothing pod placement)
- **Kueue**: Admission control, quota enforcement, multi-tenant job queuing

**Real-world example** — ComfyUI on Kubernetes:
```
- A PVC with all models (SDXL, FLUX, LoRA weights) mounted read-only to all pods
- Redis job queue for request distribution
- HPA (HorizontalPodAutoscaler) scales pods based on queue depth
- GPU node autoscaling via Karpenter or Cluster Autoscaler
- each pod preloads models on startup (15-30s readiness delay)
```

---

## 8. Power-Aware Infrastructure Scheduling

**What it is**: Treating power as a programmable, first-class resource — not just "the building provides 200kW." The workload scheduler makes real-time decisions based on power availability, cost, and carbon intensity.

**Concrete techniques**:

**Dynamic Power Capping (MAX-P / MAX-Q profiles)**:
- MAX-P: Full performance, max power draw (e.g. 700W per H100)
- MAX-Q: Throttled, energy-efficient (e.g. 500W per H100)
- Switch profiles per workload: training runs at MAX-P, inference at MAX-Q, idle nodes power-gated

**Rack-Aware Power Reservation**:
- Scheduler knows each rack's power budget (e.g. Rack-12 has 25kW available)
- Won't place a 4×H100 workload (4kW) on a rack at 23kW
- Prevents tripping circuit breakers from overload

**Grid-Responsive Workloads** (NVIDIA DSX Flex):
- Connect workload scheduler to grid services API
- When grid signals "demand response event" (high prices / low renewable), scheduler:
  1. Pauses non-critical batch jobs
  2. Migrates workloads to regions with lower carbon intensity
  3. Throttles inference replicas
- Saves 20–40% on electricity costs in regions with time-of-use pricing

**Tools**: NVIDIA Mission Control 3.0 Domain Power Service, DSX MaxLPS, Run:ai power-aware scheduling

---

## 9. Configuration Drift Detection & Continuous Compliance

**What it is**: Even if you provision everything perfectly on Day 0, hardware configurations drift over time. Someone manually tweaks a BIOS setting. A firmware auto-update changes a default. A swapped GPU has a different power limit. Drift detection catches this.

**How it works**:
1. **Baseline capture**: After commissioning, record a snapshot of all hardware configurations (BIOS settings, firmware versions, RAID layout, NUMA topology, PCIe device IDs, GPU power limits)
2. **Periodic re-scan**: Every 24h, re-inventory hardware and diff against baseline
3. **Alert on drift**: `BIOS.VirtualizationTechnology: expected=Enabled, actual=Disabled` → ticket/ChatOps alert
4. **Auto-remediation**: Run Ansible playbook to push config back to baseline

**NVIDIA's approach (DGX Spark Enterprise Manageability)**:
- `spark_updatectl.py` generates a JSON report of current update posture
- Compares against recorded baseline: packages needing updates, firmware applicability, pending reboots
- Staged rollouts with precheck/postcheck evidence capture
- Drift detection integrated with Canonical Landscape and Tanium

**Why it matters for GPU clusters**: A CUDA install that drifted by one minor version can cause silent performance degradation across training jobs. Without drift detection, you'd only discover this when someone asks "why is training 15% slower?"

---

## 10. TPM-Based Secure Bootstrap & Chain-of-Custody

**What it is**: Using hardware root of trust (TPM 2.0) to ensure that a server boots only cryptographically verified software, from BIOS through bootloader through OS kernel — and that provisioning secrets (SSH keys, API tokens) are delivered encrypted to a specific physical machine.

**The workflow**:

1. **TPM Endorsement Key (EK) registration**: On first boot, the machine's TPM presents its unique, burned-in EK. The provisioning system records it (TOFU — Trust On First Use).
2. **Measured Boot**: Every stage of boot (BIOS → UEFI → bootloader → kernel → initramfs) extends a hash into the TPM's Platform Configuration Registers (PCRs). If anything changes, the PCR values change.
3. **Remote Attestation**: Before delivering secrets, the provisioning system challenges the machine: "prove you're running the expected BIOS+bootloader+kernel." The TPM signs the PCR values with its Attestation Identity Key. If the hash doesn't match, provisioning is blocked — the machine may be compromised.
4. **Encrypted token delivery**: The provisioning secret is encrypted to the TPM's EK. Only the machine with the matching TPM chip can decrypt it. Intercepted network traffic is useless.

**Real-world use**:
- **Metal3 / Unbounded metalman**: TPM 2.0 encrypts Kubernetes bootstrap tokens with MakeCredential/ActivateCredential. Bootstrap tokens cannot be intercepted by another machine on the same L2 network.
- **NVIDIA DGX Enterprise Manageability**: Factory reset produces chain-of-custody evidence for audit compliance.
- **Azure / GCP bare metal**: Uses TPM attestation to verify that a physical server hasn't been tampered with between tenants.

**Why it matters**: In a shared colocation facility where your GPU servers sit in someone else's rack, TPM attestation is your only guarantee that the machine you're sending secrets to is actually your machine.

---

## Quick Reference: Which Method Solves Which Problem

| Problem | Method(s) that address it |
|---|---|
| Provision 50 identical servers in a day | #1 PXE Boot + #4 Golden Image |
| Server is on fire, OS is dead, need to diagnose | #2 IPMI/Redfish (remote KVM + sensors) |
| Need to reproduce a hardware config from 6 months ago | #3 IaC for Bare Metal + #9 Drift Detection |
| One bad DIMM corrupting AI training silently | #5 Commissioning & Burn-In Testing |
| GPU firmware mismatch causing CUDA errors | #6 Fleet-Wide Firmware Management |
| 3 researchers fighting over 8 GPUs for their experiments | #7 Kubernetes GPU Orchestration (KAI Scheduler, Kueue quotas) |
| Electricity bill is $30K/month — need to optimise | #8 Power-Aware Scheduling |
| New intern accidentally changed a BIOS setting on Prod-07 | #9 Configuration Drift Detection |
| Colocation facility — worried about physical tampering | #10 TPM-Based Secure Bootstrap |

---

*Compiled for Tramplus Summer Intern Onboarding — June 2026*  
*Supplement to the Notion meeting record at curious-citrus-dc5*
