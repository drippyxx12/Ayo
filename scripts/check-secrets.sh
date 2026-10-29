#!/bin/sh
# Pinned upstream release; verify the downloaded executable before running it.
set -eu
scan_tmp=$(mktemp -d)
trap 'rm -rf "$scan_tmp"' EXIT HUP INT TERM
curl --fail --silent --show-error --location \
  https://github.com/gitleaks/gitleaks/releases/download/v8.30.0/gitleaks_8.30.0_linux_x64.tar.gz \
  --output "$scan_tmp/gitleaks.tar.gz"
printf '%s  %s\n' \
  79a3ab579b53f71efd634f3aaf7e04a0fa0cf206b7ed434638d1547a2470a66e \
  "$scan_tmp/gitleaks.tar.gz" | sha256sum --check --status
tar -xzf "$scan_tmp/gitleaks.tar.gz" -C "$scan_tmp" gitleaks
"$scan_tmp/gitleaks" dir --redact --no-banner .
"$scan_tmp/gitleaks" git --redact --no-banner .
