"""
Arktec Quant Developer Toolkit

This module is part of the Arktec Quant Developer Toolkit, which provides
scripts for DevOps, MLOps, and GitOps operations.

Author: Arktec Quant Team
Copyright: © Arktec Quant. All rights reserved.
"""

import json
import os
import subprocess
import sys

try:
    import toml
except ImportError:
    print("Install toml module: pip install toml")
    sys.exit(1)

DEFAULTS_FILE = "defaults.toml"


def load_defaults():
    if not os.path.exists(DEFAULTS_FILE):
        print(f"Defaults file {DEFAULTS_FILE} not found.")
        sys.exit(1)
    with open(DEFAULTS_FILE, "r") as f:
        return toml.load(f)


def prompt(msg, default):
    val = input(f"{msg} [{default}]: ").strip()
    return val if val else default


def az(cmd, capture_output=True, check=True):
    full_cmd = ["az"] + cmd
    result = subprocess.run(full_cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Command failed: {' '.join(full_cmd)}")
        print(result.stderr)
        sys.exit(1)
    return result.stdout.strip() if result.stdout else None


def get_sp(sp_name):
    out = az(["ad", "sp", "show", "--id", f"http://{sp_name}"], check=False)
    if not out:
        return False, None, None, None
    data = json.loads(out)
    client_id = data["appId"]
    object_id = data["id"]
    tenant_id = az(
        [
            "ad",
            "sp",
            "show",
            "--id",
            client_id,
            "--query",
            "appOwnerOrganizationId",
            "-o",
            "tsv",
        ]
    )
    return True, client_id, object_id, tenant_id


def create_sp(sp_name):
    out = az(
        [
            "ad",
            "sp",
            "create-for-rbac",
            "--name",
            sp_name,
            "--skip-assignment",
            "--query",
            "{clientId: appId, clientSecret: password, tenantId: tenant}",
            "-o",
            "json",
        ]
    )
    if not out:
        print("❌ No output returned by az command")
        sys.exit(1)
    data = json.loads(out)
    client_id = data["clientId"]
    client_secret = data["clientSecret"]
    tenant_id = data["tenantId"]
    object_id = az(
        ["ad", "sp", "show", "--id", client_id, "--query", "id", "-o", "tsv"]
    )
    return client_id, client_secret, tenant_id, object_id


def reset_sp_secret(client_id):
    return az(
        [
            "ad",
            "sp",
            "credential",
            "reset",
            "--id",
            client_id,
            "--query",
            "password",
            "-o",
            "tsv",
        ]
    )


def assign_rbac(object_id, role, scope):
    az(
        [
            "role",
            "assignment",
            "create",
            "--assignee",
            object_id,
            "--role",
            role,
            "--scope",
            scope,
        ],
        capture_output=False,
    )


def create_swa_app(name, resource_group, location):
    print(f"🚀 Creating Static Web App '{name}' in RG '{resource_group}'...")
    az(
        [
            "staticwebapp",
            "create",
            "--name",
            name,
            "--resource-group",
            resource_group,
            "--location",
            location,
            "--sku",
            "Free",
            "--source",
            ".",  # Placeholder for now
        ]
    )


def main():
    defaults = load_defaults()
    org_prefix = defaults.get("org_prefix", "pfx")
    tenant_id = defaults.get("azure_tenant_id", "")
    subscription_id = defaults.get("azure_subscription_id", "")
    role_scope = "resourceGroup"  # Fixed to RG-level Contributor

    sp_base_name = prompt("Service Principal name prefix", f"{org_prefix}-swa-deployer")
    sp_name = f"{sp_base_name}-sp"

    tenant_id = prompt("Azure Tenant ID", tenant_id)
    subscription_id = prompt("Azure Subscription ID", subscription_id)

    rg_name = prompt("Resource Group name", "rg-core")
    scope = f"/subscriptions/{subscription_id}/resourceGroups/{rg_name}"

    # SP create or reuse
    found, client_id, object_id, real_tenant_id = get_sp(sp_name)
    if found:
        print(f"✅ Service Principal '{sp_name}' already exists. Reusing it.")
        client_secret = reset_sp_secret(client_id)
        if not tenant_id:
            tenant_id = real_tenant_id
    else:
        print(f"==> Creating SP '{sp_name}'")
        client_id, client_secret, tenant_id, object_id = create_sp(sp_name)
        print(f"✅ SP created: {client_id}")

    print(f"🔐 Assigning role 'Contributor' to SP at scope: {scope}")
    assign_rbac(object_id, "Contributor", scope)

    create_swa = prompt("Do you want to create an Azure Static Web App?", "yes").lower()
    if create_swa in ("yes", "y"):
        swa_name = prompt("Static Web App name", f"{org_prefix}-swa")
        swa_location = prompt("SWA location", "AustraliaEast")
        create_swa_app(swa_name, rg_name, swa_location)
        print(f"\n✅ Static Web App created: {swa_name}")
        print(f"SWA_NAME={swa_name}")
        print(f"SWA_RESOURCE_GROUP={rg_name}")
        print(f"SWA_LOCATION={swa_location}")

    print("\n================== AZURE CREDENTIALS ==================")
    print(
        json.dumps(
            {
                "clientId": client_id,
                "clientSecret": client_secret,
                "tenantId": tenant_id,
                "subscriptionId": subscription_id,
            },
            indent=2,
        )
    )
    print("=======================================================")
    print("\n✅ Copy the above JSON into GitHub repo secrets as `AZURE_CREDS`")


if __name__ == "__main__":
    main()
