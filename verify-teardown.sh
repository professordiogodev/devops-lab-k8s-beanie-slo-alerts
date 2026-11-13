#!/usr/bin/env bash
# Proves the lab left nothing in your cluster. Run with: ./verify-teardown.sh
set -u
cd "$(dirname "$0")"
echo "Checking cluster context $(kubectl config current-context 2>/dev/null)"
pass=0; failn=0
check() { local d="$1"; shift; if "$@" >/dev/null 2>&1; then echo "PASS  $d"; pass=$((pass+1)); else echo "FAIL  $d"; failn=$((failn+1)); fi; }
check "the namespaces beanie and monitoring are gone" bash -c '! kubectl get namespace beanie && ! kubectl get namespace monitoring'
check "no monitoring.coreos.com CRDs left in the cluster" bash -c '[ -z "$(kubectl get crd -o name | grep monitoring.coreos.com)" ]'
check "no leftover port-forward of the lab" bash -c '! pgrep -f "[p]ort-forward.*-n (beanie|monitoring)"'
check "the cloned Beanie source is gone from this folder" bash -c '[ ! -d beanie ]'
echo
if [ "$failn" -eq 0 ]; then echo "TEARDOWN VERIFIED ($pass/$pass) in cluster $(kubectl config current-context)"; else echo "NOT CLEAN: $failn leftover(s). Remove them and run this again."; fi
exit "$failn"
