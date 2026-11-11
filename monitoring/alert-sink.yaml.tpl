# PROVIDED. A tiny receiver that prints every notification Alertmanager sends it (a stand-in for Slack or PagerDuty).
# Read what arrives with:  kubectl logs -n monitoring deploy/alert-sink
apiVersion: apps/v1
kind: Deployment
metadata:
  name: alert-sink
  namespace: monitoring
  labels: {app: alert-sink}
spec:
  replicas: 1
  selector:
    matchLabels: {app: alert-sink}
  template:
    metadata:
      labels: {app: alert-sink}
    spec:
      containers:
        - name: sink
          image: __IMAGE__
          command: ["python", "-c"]
          args:
            - |
              import json
              from http.server import BaseHTTPRequestHandler, HTTPServer
              class H(BaseHTTPRequestHandler):
                  def do_POST(self):
                      body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                      try:
                          d = json.loads(body)
                          for a in d.get("alerts", []):
                              print("NOTIFICATION", d.get("status"), a["labels"].get("alertname"), a["labels"].get("severity"), a.get("annotations", {}).get("summary", ""), flush=True)
                      except Exception:
                          print("RAW", body[:200], flush=True)
                      self.send_response(200); self.end_headers()
                  def log_message(self, *a): pass
              HTTPServer(("0.0.0.0", 9000), H).serve_forever()
          ports:
            - containerPort: 9000
          resources:
            requests: {cpu: 20m, memory: 32Mi}
            limits: {memory: 64Mi}
          securityContext:
            runAsNonRoot: true
            allowPrivilegeEscalation: false
---
apiVersion: v1
kind: Service
metadata:
  name: alert-sink
  namespace: monitoring
spec:
  selector: {app: alert-sink}
  ports:
    - port: 9000
      targetPort: 9000
