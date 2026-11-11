# Submission

Fork URL: <!-- paste the URL of your fork here -->

## Files to commit

- [ ] `monitoring/values.yaml`: Helm values for the stack
- [ ] `monitoring/beanie-servicemonitor.yaml`, `monitoring/slo-rules.yaml`, `monitoring/alertmanager-config.yaml`
- [ ] `dashboards/beanie-red.json`: your dashboard, exported from Grafana

## Questions

Answer in your own words. Where a question asks for output, paste it in a code block.

### Q1. Paste the Prometheus targets page (or `up{namespace="beanie"}`) with all Beanie targets up. Your first ServiceMonitor found nothing: what were the two reasons it can fail to match (release label / selector, and the named port)?

**Your answer:**

<!-- replace this line with your answer -->

### Q2. Paste your three RED queries (rate, errors, duration p95). Why `rate()` and not the raw counter, and why `histogram_quantile` over the buckets summed by `le`?

**Your answer:**

<!-- replace this line with your answer -->

### Q3. State your SLO in one sentence. What is the error budget for 30 days in minutes of total failure? Paste your recording rules and say why you record the ratio instead of computing it in the alert.

**Your answer:**

<!-- replace this line with your answer -->

### Q4. Why does your alert need two windows (5 minutes AND 1 hour) at a burn rate of 14.4? What does each window protect you from?

**Your answer:**

<!-- replace this line with your answer -->

### Q5. Break menu (error rate 90%) and paste the moment the alert went from pending to firing, and the message that reached the receiver. How long after the break was it? How long would a customer have waited?

**Your answer:**

<!-- replace this line with your answer -->

### Q6. Alert on symptoms or causes? Say which your alert is, and name one cause-based alert you would add as a ticket, not a page.

**Your answer:**

<!-- replace this line with your answer -->

### Q7. Paste the output of `./verify.sh`. It must end with **ALL CHECKS PASSED**.

**Your answer:**

<!-- replace this line with your answer -->

### Q8. **Tear down.** Paste the output of `./verify-teardown.sh`. It must end with **TEARDOWN VERIFIED**.

**Your answer:**

<!-- replace this line with your answer -->
