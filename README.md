# Arktec Quant Developer Toolkit

This repository provides scripts for DevOps, MLOps, and GitOps operations.


## Setup

1. Copy and edit the defaults file

```
cp example.toml defaults.toml
```

Edit defaults.toml with your organization, Azure, and GitHub details.


2. Set up a Python virtual environment and install dependencies
```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Run scripts

All main scripts are located in scripts/.

Example (for Key Vault SP automation):
```
python scripts/azure/keyvault_sp_restricted.py
```


## License

See LICENSE.md for license information.

#### © Arktec Quant. All rights reserved.