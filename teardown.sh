#!/usr/bin/env bash
# Removes the lab from your cluster and your folder. Run with: ./teardown.sh
set -u
cd "$(dirname "$0")"
kubectl cluster-info >/dev/null 2>&1 || { echo "kubectl cannot reach a cluster." >&2; exit 1; }
helm uninstall kube-prometheus-stack -n monitoring --wait >/dev/null 2>&1 && echo "uninstalled the Helm release"
kubectl delete namespace beanie monitoring --ignore-not-found --wait=true --timeout=240s
# the stack installs cluster-wide CRDs that Helm does not remove
kubectl get crd -o name | grep -E 'monitoring.coreos.com' | xargs -r kubectl delete --ignore-not-found >/dev/null 2>&1 && echo "deleted the monitoring.coreos.com CRDs"
pkill -f "port-forward.*-n (beanie|monitoring)" 2>/dev/null
rm -rf beanie .image
echo "Now run ./verify-teardown.sh"
