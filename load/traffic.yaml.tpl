# PROVIDED. A steady trickle of customers: about 5 requests per second (menu reads and orders) through the gateway.
# Without traffic there is nothing to measure. setup.sh turns this into load/traffic.yaml with your image.
apiVersion: apps/v1
kind: Deployment
metadata:
  name: traffic
  namespace: beanie
  labels: {app: traffic}
spec:
  replicas: 1
  selector:
    matchLabels: {app: traffic}
  template:
    metadata:
      labels: {app: traffic}
    spec:
      containers:
        - name: traffic
          image: __IMAGE__
          command: ["python", "-c"]
          args:
            - |
              import json, threading, time, urllib.request
              GW = "http://gateway:8000"
              ORDER = json.dumps({"customer": "load", "items": [{"item_id": "flat-white", "quantity": 1}]}).encode()
              def menu():
                  while True:
                      try: urllib.request.urlopen(GW + "/api/menu", timeout=5).read()
                      except Exception: pass
                      time.sleep(0.4)
              def order():
                  while True:
                      try: urllib.request.urlopen(urllib.request.Request(GW + "/api/orders", ORDER, {"Content-Type": "application/json"}), timeout=10).read()
                      except Exception: pass
                      time.sleep(0.5)
              for f in (menu, menu, order):
                  threading.Thread(target=f, daemon=True).start()
              threading.Event().wait()
          resources:
            requests: {cpu: 50m, memory: 48Mi}
            limits: {memory: 128Mi}
          securityContext:
            runAsNonRoot: true
            allowPrivilegeEscalation: false
