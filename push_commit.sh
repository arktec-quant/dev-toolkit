# Arktec Quant Helm Charts
# Copyright (c) 2025 Arktec Quant
#
# This script automates the process of staging, committing, and pushing changes.
# It supports providing an optional multi-word commit message.
#
# Usage:
#   ./push_commit.sh [<commit_message>]
#
#!/bin/bash
commit_message="${1:-Update}"

git add .

commit_changes() {
  git commit -m "$commit_message"
}

if ! commit_changes; then
  echo "Pre-commit hook failed or nothing to commit."
  exit 1
fi

git push origin || echo "Push failed or nothing to push."

git fetch --recurse-submodules=no
