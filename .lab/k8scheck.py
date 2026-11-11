#!/usr/bin/env python3
import json, os, socket, subprocess, sys, time, urllib.parse, urllib.request, urllib.error
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(ROOT)
passed = failed = 0
SERVICES = ["gateway", "menu", "orders", "payments", "notifications"]


def check(desc, ok, hint=""):
    global passed, failed
    if ok:
        passed += 1; print("PASS  " + desc)
    else:
        failed += 1; print("FAIL  " + desc + (("   -> " + hint) if hint else ""))


def k(*a, timeout=120):
    r = subprocess.run(("kubectl",) + a, capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout, r.stderr


def kj(*a):
    rc, out, _ = k(*a, "-o", "json")
    try:
        return json.loads(out) if rc == 0 else None
    except Exception:
        return None


def finish():
    print()
    print(("ALL CHECKS PASSED (%d/%d)" % (passed, passed)) if failed == 0 else ("%d check(s) failed, %d passed" % (failed, passed)))
    sys.exit(1 if failed else 0)


def wait_for(fn, secs, step=5):
    end = time.time() + secs
    while time.time() < end:
        try:
            if fn():
                return True
        except Exception:
            pass
        time.sleep(step)
    return False


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def get(url, timeout=15):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode())


def pf(ns, target, remote):
    port = free_port()
    p = subprocess.Popen(["kubectl", "port-forward", "-n", ns, target, "%d:%d" % (port, remote)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3)
    return p, "http://127.0.0.1:%d" % port


def prom_query(base, q):
    r = get(base + "/api/v1/query?" + urllib.parse.urlencode({"query": q}))
    return r["data"]["result"]


print("kubectl context: " + k("config", "current-context")[1].strip())
print("== The stack ==")
pods = (kj("get", "pods", "-n", "monitoring") or {}).get("items", [])
check("Prometheus, Alertmanager and Grafana pods are running in the namespace monitoring", all(any(n in p["metadata"]["name"] and p["status"].get("phase") == "Running" for p in pods) for n in ("prometheus-kube-prometheus-stack", "alertmanager-kube-prometheus-stack", "kube-prometheus-stack-grafana")), "helm install kube-prometheus-stack ... -n monitoring")
check("the alert receiver (alert-sink) is running", any("alert-sink" in p["metadata"]["name"] and p["status"].get("phase") == "Running" for p in pods))
beanie = (kj("get", "deployments", "-n", "beanie") or {}).get("items", [])
check("Beanie (five Deployments) and the traffic generator are running", {d["metadata"]["name"] for d in beanie} >= set(SERVICES) | {"traffic"})
if not any("prometheus-kube-prometheus-stack" in p["metadata"]["name"] for p in pods) or k("get", "svc", "kube-prometheus-stack-prometheus", "-n", "monitoring")[0] != 0:
    finish()
pp, pbase = pf("monitoring", "svc/kube-prometheus-stack-prometheus", 9090)
ap, abase = pf("monitoring", "svc/kube-prometheus-stack-alertmanager", 9093)
try:
    print("== Scraping ==")
    def targets_up():
        t = get(pbase + "/api/v1/targets")["data"]["activeTargets"]
        have = {x["labels"].get("service") for x in t if x["labels"].get("namespace") == "beanie" and x["health"] == "up"}
        return have >= set(SERVICES)
    check("Prometheus scrapes all five Beanie Services and they are up", wait_for(targets_up, 120), "ServiceMonitor: namespaceSelector, selector, port name `http`")
    def has_service_label():
        r = prom_query(pbase, 'count by (service) (beanie_http_requests_total)')
        return {x["metric"].get("service") for x in r} >= set(SERVICES)
    check("the metric label `service` from the app survives (honorLabels), so service=\"gateway\" works", wait_for(has_service_label, 60), "without honorLabels the app's label becomes exported_service")

    print("== Rules and alerts ==")
    groups = get(pbase + "/api/v1/rules")["data"]["groups"]
    rules = [r for g in groups for r in g["rules"]]
    recs = [r for r in rules if r["type"] == "recording" and "gateway" in r["query"] and "beanie_http_requests_total" in r["query"]]
    check("two recording rules for the gateway error ratio (5m and 1h windows)", any("[5m]" in r["query"] for r in recs) and any("[1h]" in r["query"] for r in recs))
    alerts = [r for r in rules if r["type"] == "alerting" and r.get("labels", {}).get("team") == "beanie"]
    check("an alert with team=beanie, a summary, for 1-5 minutes, that uses both windows", bool(alerts) and all("summary" in a.get("annotations", {}) for a in alerts) and 60 <= alerts[0].get("duration", 0) <= 300 and "5m" in alerts[0]["query"] and "1h" in alerts[0]["query"])
    check("the alert uses the burn rate 14.4 on a 1% budget (0.144)", bool(alerts) and any(s in alerts[0]["query"] for s in ("14.4", "0.144")))
    cfg = get(abase + "/api/v2/status")["config"]["original"]
    check("Alertmanager has a route for team=beanie and a webhook receiver (the URL is hidden by Alertmanager; the delivery test below proves it)", "webhook_configs" in cfg and "team" in cfg)
    cms = (kj("get", "configmaps", "-n", "monitoring", "-l", "grafana_dashboard=1") or {}).get("items", [])
    dash, exprs = None, ""
    for c in cms:
        for v in c.get("data", {}).values():
            try:
                d = json.loads(v)
            except Exception:
                continue
            ex = " ".join(t.get("expr", "") for p in d.get("panels", []) for t in p.get("targets", []))
            if len(d.get("panels", [])) >= 3 and "beanie_http_requests_total" in ex:
                dash, exprs = d, ex
    check("a Grafana dashboard ConfigMap (label grafana_dashboard=1) with 3+ panels: rate, errors, p95", bool(dash) and len(dash["panels"]) >= 3 and "beanie_http_requests_total" in exprs and "histogram_quantile" in exprs and "beanie_http_request_duration_seconds_bucket" in exprs)
    quiet = wait_for(lambda: not [x for x in prom_query(pbase, 'ALERTS{team="beanie",alertstate="firing"}')], 60)
    check("before the break, nothing of Beanie is firing", quiet, "an earlier break still burns the 1-hour window: it resolves about an hour later (that is the long window doing its job)")

    print("== Break menu on purpose ==")
    menu_pods = [p["metadata"]["name"] for p in (kj("get", "pods", "-n", "beanie", "-l", "app=menu") or {}).get("items", [])]
    chaos = ("import urllib.request;r=urllib.request.Request('http://127.0.0.1:8001/chaos',b'{\"error_rate\":0.9}',{'Content-Type':'application/json'},method='PUT');print(urllib.request.urlopen(r).read())")
    okc = 0
    for mp in menu_pods:
        rc, out, err = k("exec", "-n", "beanie", mp, "--", "python", "-c", chaos)
        okc += rc == 0
    check("menu now fails 90%% of the time (chaos enabled on %d pods)" % okc, okc == len(menu_pods) and okc > 0, "CHAOS_ENABLED=true is set by k8s/base")
    t0 = time.time()
    name = alerts[0]["name"] if alerts else "BeanieGatewayFastBurn"
    def firing():
        return bool(prom_query(pbase, 'ALERTS{alertname="%s",alertstate="firing"}' % name))
    f = wait_for(firing, 720, 10)
    check("the alert %s fired (took %d s)" % (name, int(time.time() - t0)), f, "check the rule: do the ratios exceed 0.144? kubectl port-forward the Prometheus UI and run the expression")
    def delivered():
        rc, out, _ = k("logs", "-n", "monitoring", "deploy/alert-sink", "--tail=200")
        return rc == 0 and ("NOTIFICATION firing " + name) in out
    check("the notification reached the receiver (alert-sink logged it)", wait_for(delivered, 150, 5), "kubectl logs -n monitoring deploy/alert-sink; Alertmanager route and group_wait")
    fix = chaos.replace('0.9', '0')
    for mp in menu_pods:
        k("exec", "-n", "beanie", mp, "--", "python", "-c", fix)
    print("      chaos removed from menu")
finally:
    pp.terminate(); ap.terminate()
finish()
