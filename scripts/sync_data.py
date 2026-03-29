#!/usr/bin/env python3
"""
KisanMind — 3-Way Data Sync

Syncs satellite cache, price history, and mandi prices between:
  1. Local (data/)
  2. GCS bucket (gs://kisanmind-cache/)
  3. VM (/opt/kisanmind/kisanmind/data/)

Rule: Latest data wins — replicated to all other locations.

Usage:
    python scripts/sync_data.py                    # Full sync (local <-> GCS <-> VM)
    python scripts/sync_data.py --local-to-gcs     # Push local -> GCS
    python scripts/sync_data.py --gcs-to-local     # Pull GCS -> local
    python scripts/sync_data.py --gcs-to-vm        # Push GCS -> VM
    python scripts/sync_data.py --vm-to-gcs        # Pull VM -> GCS
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

GCS_BUCKET = os.getenv("GCS_CACHE_BUCKET", "kisanmind-cache")
VM_NAME = "kisanmind-vm"
VM_ZONE = "asia-south1-a"
VM_PROJECT = "lmsforshantithakur"
VM_DATA_DIR = "/opt/kisanmind/kisanmind/data"
LOCAL_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

SYNC_PATHS = [
    {
        "name": "Satellite Cache",
        "local": "satellite_cache",
        "gcs": "satellite-cache",
        "files": ["latest.json"],
    },
    {
        "name": "Price History",
        "local": "price_history",
        "gcs": "price-history",
        "files": None,  # Sync all .json files
    },
    {
        "name": "Mandi Prices",
        "local": "mandi_prices",
        "gcs": "mandi-prices",
        "files": None,  # Sync all .json files
    },
]


def run(cmd: str, capture: bool = True) -> tuple[int, str]:
    """Run shell command, return (exit_code, output)."""
    result = subprocess.run(cmd, shell=True, capture_output=capture, text=True)
    return result.returncode, (result.stdout + result.stderr).strip()


def get_gcs_file_info(gcs_path: str) -> dict:
    """Get file metadata from GCS. Returns {name: {size, updated}}."""
    code, output = run(f"gsutil ls -l gs://{GCS_BUCKET}/{gcs_path}/ 2>/dev/null")
    files = {}
    if code == 0:
        for line in output.strip().split("\n"):
            parts = line.strip().split()
            if len(parts) >= 3 and parts[0].isdigit():
                size = int(parts[0])
                date_str = parts[1]
                name = parts[2].split("/")[-1]
                if name and name.endswith(".json"):
                    files[name] = {"size": size, "updated": date_str}
    return files


def get_local_file_info(local_path: Path) -> dict:
    """Get file metadata from local directory."""
    files = {}
    if local_path.exists():
        for f in local_path.glob("*.json"):
            stat = f.stat()
            files[f.name] = {
                "size": stat.st_size,
                "updated": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            }
    return files


def sync_local_to_gcs(sync_path: dict):
    """Push local files to GCS if local is newer/larger."""
    local_dir = LOCAL_DATA_DIR / sync_path["local"]
    gcs_prefix = sync_path["gcs"]

    if not local_dir.exists():
        print(f"  Skip: {local_dir} does not exist")
        return

    local_files = get_local_file_info(local_dir)
    gcs_files = get_gcs_file_info(gcs_prefix)

    for fname, local_info in local_files.items():
        if sync_path["files"] and fname not in sync_path["files"]:
            continue
        gcs_info = gcs_files.get(fname)
        should_upload = False
        if not gcs_info:
            should_upload = True
            reason = "new file"
        elif local_info["size"] > gcs_info["size"]:
            should_upload = True
            reason = f"local larger ({local_info['size']} > {gcs_info['size']})"

        if should_upload:
            src = local_dir / fname
            dst = f"gs://{GCS_BUCKET}/{gcs_prefix}/{fname}"
            code, _ = run(f"gsutil cp {src} {dst}")
            if code == 0:
                print(f"  \u2191 {fname} \u2192 GCS ({reason})")
            else:
                print(f"  \u2717 {fname} upload failed")
        else:
            print(f"  = {fname} (GCS is current)")


def sync_gcs_to_local(sync_path: dict):
    """Pull GCS files to local if GCS is newer/larger."""
    local_dir = LOCAL_DATA_DIR / sync_path["local"]
    gcs_prefix = sync_path["gcs"]
    local_dir.mkdir(parents=True, exist_ok=True)

    gcs_files = get_gcs_file_info(gcs_prefix)
    local_files = get_local_file_info(local_dir)

    for fname, gcs_info in gcs_files.items():
        if sync_path["files"] and fname not in sync_path["files"]:
            continue
        local_info = local_files.get(fname)
        should_download = False
        if not local_info:
            should_download = True
            reason = "new file"
        elif gcs_info["size"] > local_info["size"]:
            should_download = True
            reason = f"GCS larger ({gcs_info['size']} > {local_info['size']})"

        if should_download:
            src = f"gs://{GCS_BUCKET}/{gcs_prefix}/{fname}"
            dst = local_dir / fname
            code, _ = run(f"gsutil cp {src} {dst}")
            if code == 0:
                print(f"  \u2193 {fname} \u2190 GCS ({reason})")
            else:
                print(f"  \u2717 {fname} download failed")
        else:
            print(f"  = {fname} (local is current)")


def sync_gcs_to_vm(sync_path: dict):
    """Push GCS files to VM."""
    gcs_prefix = sync_path["gcs"]
    vm_dir = f"{VM_DATA_DIR}/{sync_path['local']}"

    # Ensure VM directory exists
    run(f"gcloud compute ssh {VM_NAME} --zone={VM_ZONE} --project={VM_PROJECT} --command='sudo mkdir -p {vm_dir} && sudo chown dmj:dmj {vm_dir}'")

    gcs_files = get_gcs_file_info(gcs_prefix)
    for fname in gcs_files:
        if sync_path["files"] and fname not in sync_path["files"]:
            continue
        src = f"gs://{GCS_BUCKET}/{gcs_prefix}/{fname}"
        # Download from GCS to VM via gcloud compute scp
        code, _ = run(f"gcloud compute ssh {VM_NAME} --zone={VM_ZONE} --project={VM_PROJECT} --command='gsutil cp {src} {vm_dir}/{fname}'")
        if code == 0:
            print(f"  \u2192 {fname} \u2192 VM ({vm_dir})")
        else:
            print(f"  \u2717 {fname} VM transfer failed")


def sync_vm_to_gcs(sync_path: dict):
    """Pull VM files to GCS if VM has newer data."""
    gcs_prefix = sync_path["gcs"]
    vm_dir = f"{VM_DATA_DIR}/{sync_path['local']}"

    # Get VM file list
    code, output = run(f"gcloud compute ssh {VM_NAME} --zone={VM_ZONE} --project={VM_PROJECT} --command='ls -la {vm_dir}/*.json 2>/dev/null'")
    if code != 0:
        print(f"  Skip: no files on VM at {vm_dir}")
        return

    for line in output.strip().split("\n"):
        parts = line.split()
        if len(parts) >= 9 and parts[-1].endswith(".json"):
            fname = parts[-1].split("/")[-1]
            if sync_path["files"] and fname not in sync_path["files"]:
                continue
            vm_size = int(parts[4]) if parts[4].isdigit() else 0
            gcs_files = get_gcs_file_info(gcs_prefix)
            gcs_info = gcs_files.get(fname)

            if not gcs_info or vm_size > gcs_info.get("size", 0):
                src = f"{vm_dir}/{fname}"
                dst = f"gs://{GCS_BUCKET}/{gcs_prefix}/{fname}"
                code, _ = run(f"gcloud compute ssh {VM_NAME} --zone={VM_ZONE} --project={VM_PROJECT} --command='gsutil cp {src} {dst}'")
                if code == 0:
                    print(f"  \u2190 {fname} \u2190 VM (VM has more data)")
                else:
                    print(f"  \u2717 {fname} VM\u2192GCS failed")


def full_sync():
    """3-way sync: determine latest source and replicate to others."""
    for sp in SYNC_PATHS:
        print(f"\n{'='*40}")
        print(f"Syncing: {sp['name']}")
        print(f"{'='*40}")

        # Step 1: VM -> GCS (if VM has newer data)
        print("\n  [VM -> GCS]")
        sync_vm_to_gcs(sp)

        # Step 2: GCS -> Local (pull latest from GCS)
        print("\n  [GCS -> Local]")
        sync_gcs_to_local(sp)

        # Step 3: Local -> GCS (if local has newer data)
        print("\n  [Local -> GCS]")
        sync_local_to_gcs(sp)

        # Step 4: GCS -> VM (push latest to VM)
        print("\n  [GCS -> VM]")
        sync_gcs_to_vm(sp)

    print(f"\n{'='*40}")
    print("Sync complete.")


def main():
    parser = argparse.ArgumentParser(description="KisanMind 3-way data sync")
    parser.add_argument("--local-to-gcs", action="store_true")
    parser.add_argument("--gcs-to-local", action="store_true")
    parser.add_argument("--gcs-to-vm", action="store_true")
    parser.add_argument("--vm-to-gcs", action="store_true")
    args = parser.parse_args()

    if args.local_to_gcs:
        for sp in SYNC_PATHS:
            print(f"\n[Local -> GCS] {sp['name']}")
            sync_local_to_gcs(sp)
    elif args.gcs_to_local:
        for sp in SYNC_PATHS:
            print(f"\n[GCS -> Local] {sp['name']}")
            sync_gcs_to_local(sp)
    elif args.gcs_to_vm:
        for sp in SYNC_PATHS:
            print(f"\n[GCS -> VM] {sp['name']}")
            sync_gcs_to_vm(sp)
    elif args.vm_to_gcs:
        for sp in SYNC_PATHS:
            print(f"\n[VM -> GCS] {sp['name']}")
            sync_vm_to_gcs(sp)
    else:
        full_sync()


if __name__ == "__main__":
    main()
