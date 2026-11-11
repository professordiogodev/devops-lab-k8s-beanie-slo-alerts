# LAB | Monitoring on Kubernetes: The Alert That Pages You

## The situation

Beanie has been live for two weeks. Last Tuesday menu started failing one request in two for forty minutes. Nobody noticed until a customer tweeted. The postmortem has one finding, and it is not "write better code": **nobody was looking, and nothing was watching for them.**

You will build the watcher. First the plumbing: Prometheus must scrape every Beanie service, and Grafana must show what the customers feel. Then the part that matters: you will turn a sentence the business understands, *"99% of orders must work"*, into an **alert that pages a human within minutes when the budget for failure is burning too fast**, and never when it is not. And you will prove it the only honest way: by breaking menu on purpose and watching the page arrive.

> **Your mission**
> - Install the Prometheus stack (Prometheus, Alertmanager, Grafana) with Helm, with values you write
> - Make Prometheus find and scrape all five services with a ServiceMonitor
> - Build a RED dashboard (Rate, Errors, Duration) and load it as code
> - Write the SLO as recording rules and a two-window burn-rate alert
> - Route the alert to a receiver, then break menu and watch it fire and arrive
> - Tear everything down and prove it

**Time:** 150-180 min | **Cost:** free on a local cluster with 4 CPUs and 8 GB (the stack is hungry) | **You need:** Docker, `kubectl`, `helm`, git, curl, Python 3 and a Kubernetes cluster with room for it (kind, OrbStack or Docker Desktop, or the cluster of the EKS lab).

---

## Part 0 - Beanie, traffic and a receiver

Fork this repository, clone your fork, and run:

```bash
./setup.sh
kubectl apply -f k8s/base/ -f monitoring/00-namespace.yaml
kubectl apply -f load/traffic.yaml -f monitoring/alert-sink.yaml
kubectl get pods -A | grep -E 'beanie|monitoring'
```

You get Beanie (with failure injection switched on, a lab-only setting), a **traffic generator** that sends about five requests a second (without traffic there is nothing to measure) and **alert-sink**, a tiny receiver that prints every notification it gets. It stands in for Slack or PagerDuty. Read the three files in `k8s/base/gateway.yaml`, `load/traffic.yaml.tpl` and `monitoring/alert-sink.yaml.tpl`.

Look at what a service exposes:

```bash
kubectl port-forward -n beanie svc/gateway 8000:8000 &
curl -s localhost:8000/metrics | grep -E '^beanie_http_requests_total' | head
```

> **Think** Counters only go up. If a counter says 5,000 you cannot tell whether that is a lot or a little. What do you need to turn it into something you can reason about? (Keep the answer for question 2.)

---

## Part 1 - Install the stack

Write `monitoring/values.yaml` (the comments tell you what it must contain), then:

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack -n monitoring -f monitoring/values.yaml
kubectl get pods -n monitoring -w
```

The release **must** be called `kube-prometheus-stack` (the checker, and your port-forwards, find it by that name). It takes a few minutes.

Two settings in the values deserve a note. `serviceMonitorSelectorNilUsesHelmValues: false` exists because by default the stack's Prometheus only picks up ServiceMonitors that carry a `release` label matching the Helm release, a famous reason for "my ServiceMonitor does nothing". And the controller-manager, scheduler, etcd and proxy are switched off because on a managed or local cluster they cannot be scraped and would raise alerts all day.

> **Predict** You have not told Prometheus about Beanie yet. Open the Prometheus UI (`kubectl port-forward -n monitoring svc/kube-prometheus-stack-prometheus 9090`, then http://localhost:9090/targets). What do you expect to see for Beanie? What do you see for the cluster itself?

---

## Part 2 - Make Prometheus scrape Beanie

Write `monitoring/beanie-servicemonitor.yaml` (see its comments) and apply it. Open **Status > Targets**. All Beanie targets should be `UP`. If there are none: does the ServiceMonitor's `namespaceSelector` and `selector` match? Does the port **name** match the Service's port name?

Then run this query:

```text
sum by (service) (rate(beanie_http_requests_total[5m]))
```

It must show five services. If you see `exported_service` instead of `service`, you have met the second classic trap: Prometheus attaches a `service` label of its own (the Kubernetes Service), and when the application also exports one, Prometheus renames the application's. Beanie's README tells you the label belongs to the application. Which ServiceMonitor option says "the application's labels win"?

---

## Part 3 - RED, the dashboard

For every request-driven service, ask three questions: **R**ate (how busy?), **E**rrors (how many fail?) and **D**uration (how slow?). Open Grafana:

```bash
kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80
```

Log in as `admin` with the password from your values. Build a dashboard with three panels:

1. **Rate:** `sum by (service) (rate(beanie_http_requests_total[5m]))`
2. **Errors:** the ratio of 5xx requests to all requests, per service
3. **Duration:** the 95th percentile from the histogram, `histogram_quantile(0.95, sum by (le, service) (rate(beanie_http_request_duration_seconds_bucket[5m])))`

Export it (Share > Export > JSON) to `dashboards/beanie-red.json` and load it **as code**, so that it survives a reinstall (the instructions are in `dashboards/README.md`). The stack's Grafana has a sidecar that watches for ConfigMaps with the label `grafana_dashboard=1`.

> **Think** Why a percentile and not the average? Imagine 99 requests of 50 ms and one of 10 seconds. What does the average say, what does p95 say, and what does p99 say?

---

## Part 4 - The SLO, as rules

Your SLO: **"99% of the requests the gateway answers are not 5xx, measured over 30 days."** Compute what 1% means: 30 days is 43,200 minutes, so the **error budget** is 432 minutes of total failure. That is the amount of unreliability you are *allowed*. The alert should fire when you are spending it much too fast, not when a single request fails.

Write `monitoring/slo-rules.yaml` (see its comments): two **recording rules** that store the gateway's error ratio over 5 minutes and over 1 hour, and an **alert** that fires when both exceed `14.4 × 1%`.

```bash
kubectl apply -f monitoring/slo-rules.yaml
```

Open **Status > Rules** and **Alerts** in the Prometheus UI. The rules should be there and the alert `inactive`.

The number 14.4 comes from the burn-rate method in Google's SRE workbook: a burn rate of 14.4 spends **2% of a 30-day budget in one hour**. Two windows: the long one (1 hour) says "this is not a blip", the short one (5 minutes) says "and it is still happening right now". Together they page quickly on a real outage and stop paging soon after it ends.

> **Think** What does an alert on a single window of 5 minutes do on a bad night? What does an alert on a single window of 1 hour do after you have already fixed the problem?

---

## Part 5 - Who gets told

The alert carries `team: beanie`. In `monitoring/values.yaml` you already wrote an Alertmanager route that sends `team=beanie` to the webhook `http://alert-sink.monitoring.svc:9000/` and everything else to a receiver that does nothing. Check that Alertmanager really loaded it:

```bash
kubectl port-forward -n monitoring svc/kube-prometheus-stack-alertmanager 9093 &
curl -s localhost:9093/api/v2/status | python3 -m json.tool | head -40
```

If you changed the values, `helm upgrade kube-prometheus-stack ... -f monitoring/values.yaml`.

---

## Part 6 - Break menu. Watch the page.

Make menu fail 90% of the time (Beanie's failure injection; watch the dashboard while you do it):

```bash
for p in $(kubectl get pods -n beanie -l app=menu -o name); do
  kubectl exec -n beanie $p -- python -c "import urllib.request as u;print(u.urlopen(u.Request('http://127.0.0.1:8001/chaos',b'{\"error_rate\":0.9}',{'Content-Type':'application/json'},method='PUT')).read())"
done
```

Watch three things, in three terminals or tabs: the Errors panel, the alert's state in Prometheus (`inactive`, `pending`, `firing`) and the receiver:

```bash
kubectl logs -n monitoring deploy/alert-sink -f
```

Write down the time at which you broke it, the time the alert went `pending`, `firing` and the time of the line `NOTIFICATION firing ...`. Then repair menu (same command with `0`) and wait for the `resolved` message.

> **Think** From the break to the notification, how many minutes passed? A real customer who gets an error on every second order: how long would they have waited before telling someone? Would you have been told earlier or later than the tweet?

---

## Part 7 - Prove it

```bash
./verify.sh
```

It checks the stack, the scrape targets, the labels, your rules and your alert, Alertmanager's routing and the dashboard. Then it breaks menu itself and waits for the alert to fire and the notification to arrive (up to about 12 minutes). Fix what is red and run it again until it ends with **ALL CHECKS PASSED**.

> **Stuck?** No Beanie targets: ServiceMonitor `selector`, `namespaceSelector` or the port name. `service` label missing: `honorLabels`. Rules not loaded: the PrometheusRule is in a namespace Prometheus does not select (`ruleSelectorNilUsesHelmValues: false`). The alert stays `pending`: the ratio is below the threshold, run the expression in the UI; remember that rates need a few minutes of data. It fires but nothing arrives: the Alertmanager route (`matchers`) or the receiver URL. Pods `Pending` with `Insufficient memory`: give Docker Desktop or the node group more memory, or lower Prometheus' requests.

---

## Level up (optional)

- Add the *slow burn* alert of the SRE workbook (burn rate 6 over 30 minutes and 6 hours, severity `ticket`). What does it catch that the fast one does not?
- Add an alert on **latency**: the p95 of the gateway above one second for five minutes. Break payments with `{"latency_ms": 3000}` and see which of your alerts fires (and which does not).
- Add an alert on a cause (`KubePodCrashLooping`, or `up == 0` for a Beanie target) with severity `ticket`. Why should causes not page?
- Write the dashboard as a Grafana provisioning file in git instead of a ConfigMap. What is better and worse?

<!-- teardown:start (generated by labs.py, do not edit) -->
## Tear down (mandatory)

Resources left behind cost money, keep doors open and pollute the next lab. Removing what you created is part of the job, so it is part of the submission: **you must prove it is gone**.

Do this **last**, after you have pasted your `verify` output into `SUBMISSION.md` (once you tear down, the lab can no longer be verified).

1. Run `./teardown.sh`. It uninstalls the Helm release, deletes the CRDs the stack installed, and the namespaces `monitoring` and `beanie`.

Then run the proof:

```bash
./verify-teardown.sh
```

It prints a list of checks and must end with **TEARDOWN VERIFIED**. If it reports leftovers, remove them and run it again. Paste the full output in your submission.
<!-- teardown:end -->

<!-- submission:start (generated by labs.py, do not edit) -->
## Submission

Answer the questions in `SUBMISSION.md` in **your fork** (paste output in code blocks where asked), push, then submit the **URL of your fork**.

**Files to commit**

- `monitoring/values.yaml`: Helm values for the stack
- `monitoring/beanie-servicemonitor.yaml`, `monitoring/slo-rules.yaml`, `monitoring/alertmanager-config.yaml`
- `dashboards/beanie-red.json`: your dashboard, exported from Grafana

**Questions to answer**

1. Paste the Prometheus targets page (or `up{namespace="beanie"}`) with all Beanie targets up. Your first ServiceMonitor found nothing: what were the two reasons it can fail to match (release label / selector, and the named port)?
2. Paste your three RED queries (rate, errors, duration p95). Why `rate()` and not the raw counter, and why `histogram_quantile` over the buckets summed by `le`?
3. State your SLO in one sentence. What is the error budget for 30 days in minutes of total failure? Paste your recording rules and say why you record the ratio instead of computing it in the alert.
4. Why does your alert need two windows (5 minutes AND 1 hour) at a burn rate of 14.4? What does each window protect you from?
5. Break menu (error rate 90%) and paste the moment the alert went from pending to firing, and the message that reached the receiver. How long after the break was it? How long would a customer have waited?
6. Alert on symptoms or causes? Say which your alert is, and name one cause-based alert you would add as a ticket, not a page.
7. Paste the output of `./verify.sh`. It must end with **ALL CHECKS PASSED**.
8. **Tear down.** Paste the output of `./verify-teardown.sh`. It must end with **TEARDOWN VERIFIED**.
<!-- submission:end -->
