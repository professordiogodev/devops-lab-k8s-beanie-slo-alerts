Put your Grafana dashboard here as `beanie-red.json` (Grafana: Dashboard > Share > Export > Export as JSON).
It needs at least three panels: Rate (requests per second), Errors (5xx ratio) and Duration (p95 from the histogram buckets).
Then load it with a ConfigMap labelled `grafana_dashboard: "1"` in the namespace `monitoring`:

    kubectl create configmap beanie-red -n monitoring --from-file=dashboards/beanie-red.json
    kubectl label configmap beanie-red -n monitoring grafana_dashboard=1
