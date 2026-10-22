#!/usr/bin/env bash
# Läuft einmal, wenn der Codespace erstellt wird.
set -euo pipefail

# kind und das Kubernetes im Knoten-Image gehören zusammen: v0.33.0 startet Kubernetes 1.37.
# kubectl kommt passend dazu aus devcontainer.json ("version": "1.37").
KIND_VERSION=v0.33.0
ARCH=$(uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/')
BASIS="https://github.com/kubernetes-sigs/kind/releases/download/${KIND_VERSION}"
curl -fsSLo /tmp/kind-linux-${ARCH} "${BASIS}/kind-linux-${ARCH}"
curl -fsSLo /tmp/kind.sha256sum "${BASIS}/kind-linux-${ARCH}.sha256sum"
(cd /tmp && sha256sum -c kind.sha256sum)
sudo install -m 0755 /tmp/kind-linux-${ARCH} /usr/local/bin/kind

pip install --user -r requirements-dev.txt

echo
echo "Fertig. Prüfen mit:"
echo "  docker version && kind version && kubectl version --client && aws --version && terraform version"
