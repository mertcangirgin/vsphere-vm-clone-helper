import argparse
import atexit
import ssl
import sys
import time

from pyVim import connect
from pyVmomi import vim


def parse_args():
    parser = argparse.ArgumentParser(
        description="Clone a vSphere VM with repeatable defaults and operational safety checks."
    )
    parser.add_argument("--server", required=True, help="vCenter or ESXi hostname")
    parser.add_argument("--username", required=True, help="vSphere username")
    parser.add_argument("--password", required=True, help="vSphere password")
    parser.add_argument("--source-vm", required=True, help="Source VM name")
    parser.add_argument(
        "--target-name",
        help="Name of the new VM. Default: <source-vm>-clone",
    )
    parser.add_argument("--target-folder", help="Destination VM folder name")
    parser.add_argument("--target-host", help="Destination ESXi host name")
    parser.add_argument("--target-datastore", help="Destination datastore name")
    parser.add_argument("--resource-pool", help="Destination resource pool name")
    parser.add_argument(
        "--linked-clone",
        action="store_true",
        help="Create a linked clone. Requires a source snapshot.",
    )
    parser.add_argument(
        "--snapshot-name",
        help="Snapshot to clone from. Required when --linked-clone is used.",
    )
    parser.add_argument(
        "--power-on",
        action="store_true",
        help="Power on the cloned VM after the task completes.",
    )
    parser.add_argument(
        "--annotation",
        help="Optional annotation added to the cloned VM config.",
    )
    parser.add_argument(
        "--disable-ssl-verification",
        action="store_true",
        help="Disable SSL certificate verification for lab environments.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=3600,
        help="Task timeout in seconds. Default: 3600",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate inputs and print the intended clone plan without executing it.",
    )
    args = parser.parse_args()

    if args.linked_clone and not args.snapshot_name:
        parser.error("--snapshot-name is required when --linked-clone is used")
    if args.timeout < 1:
        parser.error("--timeout must be greater than 0")
    return args


def build_ssl_context(disable_ssl_verification):
    if not disable_ssl_verification:
        return None

    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def connect_vsphere(args):
    context = build_ssl_context(args.disable_ssl_verification)
    si = connect.SmartConnect(
        host=args.server,
        user=args.username,
        pwd=args.password,
        sslContext=context,
    )
    atexit.register(connect.Disconnect, si)
    return si


def get_all_objects(content, vim_type):
    view = content.viewManager.CreateContainerView(content.rootFolder, [vim_type], True)
    try:
        return list(view.view)
    finally:
        view.Destroy()


def get_by_name(content, vim_type, name):
    for obj in get_all_objects(content, vim_type):
        if obj.name == name:
            return obj
    return None


def get_snapshot_by_name(vm, snapshot_name):
    if not vm.snapshot:
        return None

    stack = list(vm.snapshot.rootSnapshotList)
    while stack:
        current = stack.pop()
        if current.name == snapshot_name:
            return current.snapshot
        stack.extend(current.childSnapshotList)
    return None


def wait_for_task(task, timeout):
    start = time.time()
    while task.info.state not in (vim.TaskInfo.State.success, vim.TaskInfo.State.error):
        if time.time() - start > timeout:
            raise TimeoutError("Timed out while waiting for clone task to finish.")
        time.sleep(2)

    if task.info.state == vim.TaskInfo.State.error:
        raise RuntimeError(f"Clone task failed: {task.info.error.msg}")

    return task.info.result


def resolve_clone_targets(content, source_vm, args):
    target_name = args.target_name or f"{args.source_vm}-clone"
    existing_vm = get_by_name(content, vim.VirtualMachine, target_name)
    if existing_vm:
        raise ValueError(f"A VM named '{target_name}' already exists.")

    target_folder = source_vm.parent
    if args.target_folder:
        target_folder = get_by_name(content, vim.Folder, args.target_folder)
        if not target_folder:
            raise ValueError(f"Target folder '{args.target_folder}' was not found.")

    target_pool = source_vm.resourcePool
    if args.resource_pool:
        target_pool = get_by_name(content, vim.ResourcePool, args.resource_pool)
        if not target_pool:
            raise ValueError(f"Resource pool '{args.resource_pool}' was not found.")

    target_host = None
    if args.target_host:
        target_host = get_by_name(content, vim.HostSystem, args.target_host)
        if not target_host:
            raise ValueError(f"Target host '{args.target_host}' was not found.")

    target_datastore = None
    if args.target_datastore:
        target_datastore = get_by_name(content, vim.Datastore, args.target_datastore)
        if not target_datastore:
            raise ValueError(f"Target datastore '{args.target_datastore}' was not found.")

    target_snapshot = None
    if args.snapshot_name:
        target_snapshot = get_snapshot_by_name(source_vm, args.snapshot_name)
        if not target_snapshot:
            raise ValueError(f"Snapshot '{args.snapshot_name}' was not found on '{args.source_vm}'.")

    return {
        "target_name": target_name,
        "target_folder": target_folder,
        "target_pool": target_pool,
        "target_host": target_host,
        "target_datastore": target_datastore,
        "target_snapshot": target_snapshot,
    }


def build_clone_spec(source_vm, targets, args):
    relocate_spec = vim.vm.RelocateSpec()
    relocate_spec.pool = targets["target_pool"]

    if targets["target_host"]:
        relocate_spec.host = targets["target_host"]
    if targets["target_datastore"]:
        relocate_spec.datastore = targets["target_datastore"]
    if args.linked_clone:
        relocate_spec.diskMoveType = "createNewChildDiskBacking"

    clone_spec = vim.vm.CloneSpec()
    clone_spec.location = relocate_spec
    clone_spec.powerOn = args.power_on
    clone_spec.template = False

    if targets["target_snapshot"]:
        clone_spec.snapshot = targets["target_snapshot"]

    if args.annotation:
        config_spec = vim.vm.ConfigSpec()
        config_spec.annotation = args.annotation
        clone_spec.config = config_spec
    elif source_vm.config.annotation:
        config_spec = vim.vm.ConfigSpec()
        config_spec.annotation = source_vm.config.annotation
        clone_spec.config = config_spec

    return clone_spec


def print_plan(source_vm, targets, args):
    print("Clone plan")
    print(f"  Source VM: {source_vm.name}")
    print(f"  Target VM: {targets['target_name']}")
    print(f"  Folder: {targets['target_folder'].name}")
    print(f"  Resource pool: {targets['target_pool'].name}")
    print(f"  Host: {targets['target_host'].name if targets['target_host'] else 'same as source/default'}")
    print(
        "  Datastore: "
        f"{targets['target_datastore'].name if targets['target_datastore'] else 'same as source/default'}"
    )
    print(f"  Linked clone: {'yes' if args.linked_clone else 'no'}")
    print(f"  Snapshot: {args.snapshot_name or 'not specified'}")
    print(f"  Power on after clone: {'yes' if args.power_on else 'no'}")


def main():
    args = parse_args()
    si = connect_vsphere(args)
    content = si.RetrieveContent()

    source_vm = get_by_name(content, vim.VirtualMachine, args.source_vm)
    if not source_vm:
        raise ValueError(f"Source VM '{args.source_vm}' was not found.")

    targets = resolve_clone_targets(content, source_vm, args)
    clone_spec = build_clone_spec(source_vm, targets, args)

    print_plan(source_vm, targets, args)
    if args.dry_run:
        print("Dry run complete. No clone task was started.")
        return 0

    task = source_vm.Clone(
        folder=targets["target_folder"],
        name=targets["target_name"],
        spec=clone_spec,
    )
    result_vm = wait_for_task(task, timeout=args.timeout)
    print(f"Clone completed successfully: {result_vm.name}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
