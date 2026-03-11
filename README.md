# Copying_Virtual_Machine

Small operational helper for cloning VMware vSphere virtual machines with Python and `pyVmomi`.

This repository is no longer just a code example. It is designed as a practical helper for repeatable VM cloning tasks that are often done manually in the vSphere GUI.

## Why this can be useful

This tool is useful when you need to:

- clone the same VM repeatedly for test, staging, or lab environments
- reduce manual clicking in the vSphere UI
- standardize destination folder, resource pool, datastore, and host selection
- avoid naming collisions before starting a clone
- run a dry-run validation before executing the task
- automate VM cloning in scripts or operational runbooks

## Real operational use cases

Common situations where a helper like this is useful:

- creating a test copy of a production-like VM before maintenance
- preparing lab or training environments quickly
- cloning a base VM into a staging environment with a controlled naming pattern
- building repeatable internal automation around VMware without using the full GUI each time

## What this helper does

The script:

- connects to a vCenter or ESXi endpoint
- finds a source VM by name
- validates the destination VM name before cloning
- optionally resolves a target folder, host, datastore, and resource pool
- supports linked clone mode when a snapshot is provided
- supports `--dry-run` for safe validation
- optionally powers on the cloned VM after completion
- waits for the task and reports the result clearly

## Why this is better than a raw example

This version adds practical value:

- CLI arguments instead of hard-coded placeholders
- basic safety checks before the task starts
- name collision protection
- explicit timeout handling
- support for linked clone workflows
- support for annotation and controlled post-clone power-on

It is still intentionally small, but it now behaves more like an actual helper tool.

## Requirements

- Python 3
- `pyvmomi`
- access to a vCenter or ESXi environment
- permissions to read inventory and create clones

Install the dependency:

```bash
python3 -m pip install -r requirements.txt
```

## Usage

Basic full clone:

```bash
python3 copy_virtual_machine.py \
  --server vcsa.example.local \
  --username administrator@vsphere.local \
  --password 'your-password' \
  --source-vm app-server-01 \
  --target-name app-server-01-clone
```

Dry-run validation:

```bash
python3 copy_virtual_machine.py \
  --server vcsa.example.local \
  --username administrator@vsphere.local \
  --password 'your-password' \
  --source-vm app-server-01 \
  --target-name app-server-01-clone \
  --target-folder Staging \
  --resource-pool Resources \
  --dry-run
```

Linked clone from a snapshot:

```bash
python3 copy_virtual_machine.py \
  --server vcsa.example.local \
  --username administrator@vsphere.local \
  --password 'your-password' \
  --source-vm app-server-01 \
  --target-name app-server-01-linked \
  --linked-clone \
  --snapshot-name pre-patch-snapshot
```

## Supported options

- `--server`
- `--username`
- `--password`
- `--source-vm`
- `--target-name`
- `--target-folder`
- `--target-host`
- `--target-datastore`
- `--resource-pool`
- `--linked-clone`
- `--snapshot-name`
- `--power-on`
- `--annotation`
- `--disable-ssl-verification`
- `--timeout`
- `--dry-run`

## Notes

- `--linked-clone` requires a valid source snapshot
- `--disable-ssl-verification` is better kept for labs and internal environments
- datastore, host, and folder names must match inventory objects exactly
- this helper is designed for focused operational cloning, not for full provisioning workflows

## Suggested positioning

This repository makes the most sense as:

- a vSphere VM clone helper
- a pyVmomi-based cloning utility
- a small operations tool for repeatable VMware clone tasks

---

## Author

Built by **Mert Can Girgin**

**MSc | DevOps Engineer | Linux Administrator**

Guardian of the Linux realms. No outage shall pass.
