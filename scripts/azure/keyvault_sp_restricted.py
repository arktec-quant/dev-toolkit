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
    print("Please install the toml package: pip install toml")
    sys.exit(1)

DEFAULTS_FILE = "defaults.toml"


def load_defaults():
    if not os.path.exists(DEFAULTS_FILE):
        print(f"Defaults file {DEFAULTS_FILE} not found!")
        sys.exit(1)
    with open(DEFAULTS_FILE, "r") as f:
        return toml.load(f)


def prompt(msg, default):
    val = input(f"{msg} [{default}]: ").strip()
    return val if val else default


def az(cmd, capture_output=True):
    full_cmd = ["az"] + cmd
    if capture_output:
        result = subprocess.run(full_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Command failed: {' '.join(full_cmd)}")
            print(result.stderr)
            sys.exit(1)
        return result.stdout.strip()
    else:
        ret = os.system(" ".join(full_cmd))
        if ret != 0:
            sys.exit(1)


def get_sp(sp_name):
    # Returns (found, client_id, object_id, tenant_id)
    try:
        out = az(["ad", "sp", "show", "--id", f"{sp_name}"])
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
    except Exception:
        return False, None, None, None


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
        print("❌ Failed to create Service Principal")
        sys.exit(1)
    d = json.loads(out)
    client_id = d["clientId"]
    client_secret = d["clientSecret"]
    tenant_id = d["tenantId"]
    object_id = az(
        ["ad", "sp", "show", "--id", client_id, "--query", "id", "-o", "tsv"]
    )
    return client_id, client_secret, tenant_id, object_id


def reset_sp_secret(client_id):
    secret = az(
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
    return secret


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


def get_secret_names(vault_name, prefix):
    out = az(
        [
            "keyvault",
            "secret",
            "list",
            "--vault-name",
            vault_name,
            "--query",
            f"[?starts_with(name, '{prefix}')].name",
            "-o",
            "tsv",
        ]
    )
    if not out:
        return []
    names = out.splitlines()
    return [n for n in names if n]


def main():
    defaults = load_defaults()
    org_prefix = defaults.get("org_prefix", "pfx")
    tenant_id = defaults.get("azure_tenant_id", "")
    subscription_id = defaults.get("azure_subscription_id", "")
    resource_group = defaults.get("azure_resource_group", "")
    keyvault_name = defaults.get("azure_keyvault_name", "")
    github_org = defaults.get("github_org", "")

    # Prompt user
    repo_name = prompt("Enter the Git repository name", f"{org_prefix}-repo")
    sp_name = f"{repo_name}-sp"

    tenant_id = prompt("Azure Tenant ID", tenant_id)
    subscription_id = prompt("Azure Subscription ID", subscription_id)
    resource_group = prompt("Azure Resource Group", resource_group)
    keyvault_name = prompt("Azure Key Vault name", keyvault_name)

    print("\n🔐 Choose Key Vault access scope for repo")
    print("1. Grant access to all secrets in the Key Vault")
    print("2. Grant access to secrets matching a prefix")
    scope_choice = prompt("Enter 1 or 2", "1")

    if scope_choice == "2":
        secret_prefix = prompt(
            "Enter the prefix to match secrets (e.g., dev-github-arc-)", f"{repo_name}-"
        )
    else:
        secret_prefix = None

    # SP Creation/Reuse
    found, client_id, object_id, real_tenant_id = get_sp(sp_name)
    if found:
        print(f"✅ Service Principal '{sp_name}' exists. Reusing it.")
        client_secret = reset_sp_secret(client_id)
        if not client_secret:
            print("❌ Failed to reset SP secret")
            sys.exit(1)
        if not tenant_id:
            tenant_id = real_tenant_id
    else:
        print(f"==> Creating Service Principal: {sp_name}")
        client_id, client_secret, tenant_id, object_id = create_sp(sp_name)
        print(f"✅ Service Principal created: {client_id}")

    # Assign RBAC
    if scope_choice == "2":
        secret_names = get_secret_names(keyvault_name, secret_prefix)
        if not secret_names:
            print(
                f"❌ No secrets found in Key Vault '{keyvault_name}' with prefix '{secret_prefix}'"
            )
            sys.exit(1)
        for name in secret_names:
            print(f"🔐 Assigning access to secret: {name}")
            scope = f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.KeyVault/vaults/{keyvault_name}/secrets/{name}"
            assign_rbac(object_id, "Key Vault Secrets User", scope)
        print(f"✅ Assigned access to secrets with prefix '{secret_prefix}'")
    else:
        print(
            f"🔓 Granting access to ALL secrets in vault '{keyvault_name}' for SP '{sp_name}'..."
        )
        scope = f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.KeyVault/vaults/{keyvault_name}"
        assign_rbac(object_id, "Key Vault Secrets User", scope)
        print(
            f"✅ SP '{sp_name}' now has access to ALL secrets in Key Vault '{keyvault_name}'."
        )

    # Output JSON for GH Secrets
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
    print(
        "\nCopy these values into your GitHub repo secrets and use in your GHA workflows."
    )


if __name__ == "__main__":
    main()
