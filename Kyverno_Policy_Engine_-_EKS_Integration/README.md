# Kyverno Policy Engine - EKS Integration

> **Personal note:** I wrote this up after spending a few days getting Kyverno properly wired into our existing EKS cluster. Most guides assume you're starting from scratch - this one doesn't. If you already have a running cluster with workloads on it, the order of operations matters a lot more than the docs let on. Hopefully this saves someone the same headaches I hit.

---

## What is this?

This documents how I integrated [Kyverno](https://kyverno.io/) into an **existing** Amazon EKS cluster. A Kubernetes-native policy engine that handles validation, mutation, and resource generation through plain YAML policies. No OPA(Open Policy Agent) Rego, no custom admission webhooks to maintain. Just rules you can read and understand.

I set this up because the team kept hitting the same issues:
- Pods deployed without resource limits, eventually causing node pressure
- Namespaces created with no NetworkPolicy open by default
- Inconsistent labels making cost attribution a mess in AWS Cost Explorer

Kyverno addressed all three. Here's exactly how I did it, including what broke.

---

## Prerequisites

Before starting, verify the following on your existing cluster:

```bash
# Confirm cluster is v1.21+ (Kyverno requires this minimum)
kubectl version --short

# Confirm you're pointed at the right cluster
kubectl config current-context

# Confirm you have cluster-admin - Kyverno needs it for webhook registration
kubectl auth can-i '*' '*' --all-namespaces
# Expected output: yes
```

You'll also need Helm 3.x:

```bash
helm version
# Should output: version.BuildInfo{Version:"v3.x.x", ...}
```

If Helm isn't installed:

```bash
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

---

## Step 1 - Add the Kyverno Helm Repo

```bash
helm repo add kyverno https://kyverno.github.io/kyverno/
helm repo update
```

Verify the repo is available and check available versions:

```bash
helm search repo kyverno/kyverno --versions | head -5
```

---

## Step 2 - Install Kyverno into Your Existing Cluster

Install Kyverno into its own dedicated namespace. For a production cluster, use 3 replicas. Kyverno runs as an admission webhook, so if it goes down, resource creation either gets blocked or silently bypassed depending on your `failurePolicy`.

```bash
helm install kyverno kyverno/kyverno \
  --namespace kyverno \
  --create-namespace \
  --set replicaCount=3 \
  --set config.webhooks[0].timeoutSeconds=30 \
  --version 3.2.6
```

> **Why pin the version?** Kyverno has had breaking API changes between minor versions. Pinning `--version` means you control when you upgrade. I learned this the hard way after an unintentional chart upgrade changed how mutation policies were evaluated.

> **Why `timeoutSeconds=30`?** The default is 10 seconds. Under burst load for example, a scaling event where many pods spin up simultaneously. The webhook queue backs up and you'll see timeouts that surface as misleading `etcd cluster is unavailable` errors. 30 seconds is a safe value for production.

---

## Step 3 - Verify Kyverno is Running

Don't skip this. I moved on too fast once and spent 20 minutes wondering why policies weren't applying.

```bash
kubectl get pods -n kyverno
```

Expected output:

```
NAME                       READY   STATUS    RESTARTS   AGE
kyverno-6d8f9c7b4d-4xk9z   1/1     Running   0          2m
kyverno-6d8f9c7b4d-n7pl2   1/1     Running   0          2m
kyverno-6d8f9c7b4d-r3mt8   1/1     Running   0          2m
```

Confirm the rollout completed cleanly:

```bash
kubectl rollout status deployment kyverno -n kyverno
# Expected: deployment "kyverno" successfully rolled out
```

Confirm webhook configurations were registered at the cluster level:

```bash
kubectl get validatingwebhookconfigurations | grep kyverno
kubectl get mutatingwebhookconfigurations | grep kyverno
```

If these are missing, Kyverno didn't finish installing. Check pod logs:

```bash
kubectl logs -n kyverno -l app.kubernetes.io/name=kyverno --tail=50
```

---

## Step 4 - Apply Policies

> **Important for existing clusters:** Before applying any policy in `Enforce` mode, run it in `Audit` mode first. Audit logs violations without blocking anything. This lets you see what would be affected by your existing workloads before you start breaking deployments. I keep every new policy in Audit for at least 24 hours.

### Policy 1 - Validation: Require Resource Limits

Every container must have CPU and memory limits defined. Without this, one misconfigured deployment can consume all node resources and cause evictions across the board.

Save the following as `require-resource-limits.yaml`:

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-resource-limits
  annotations:
    policies.kyverno.io/title: "Require Resource Limits"
    policies.kyverno.io/category: "Best Practices"
    policies.kyverno.io/description: >-
      Requires CPU and memory limits on all containers to prevent
      noisy-neighbour issues and uncontrolled node pressure.
spec:
  validationFailureAction: Audit   # change to Enforce after reviewing audit reports
  background: true
  rules:
    - name: check-resource-limits
      match:
        any:
          - resources:
              kinds: [Pod]
      exclude:
        any:
          - resources:
              namespaces:
                - kube-system
                - kyverno
                - kube-public
                - kube-node-lease
      validate:
        message: "CPU and memory limits are required on all containers."
        pattern:
          spec:
            containers:
              - resources:
                  limits:
                    cpu: "?*"
                    memory: "?*"
```

Apply it:

```bash
kubectl apply -f require-resource-limits.yaml
```

---

### Policy 2 - Mutation: Auto-add Default Labels

This quietly patches any pod missing standard labels. The `+()` syntax means "only add if not already present", existing labels are never overwritten.

Save as `mutate-add-labels.yaml`:

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: add-default-labels
  annotations:
    policies.kyverno.io/title: "Add Default Labels"
    policies.kyverno.io/category: "Best Practices"
    policies.kyverno.io/description: >-
      Automatically adds managed-by and env labels to pods that are missing
      them. Uses +() syntax so existing labels are never overwritten.
spec:
  rules:
    - name: add-team-label
      match:
        any:
          - resources:
              kinds: [Pod]
      mutate:
        patchStrategicMerge:
          metadata:
            labels:
              +(managed-by): kyverno
              +(env): "{{request.namespace}}"
```

Apply it:

```bash
kubectl apply -f mutate-add-labels.yaml
```

---

### Policy 3 - Generation: Auto-create NetworkPolicy on New Namespaces

Every new namespace automatically gets a `default-deny-all` NetworkPolicy. This is the one I wish we'd had from day one. New namespaces were being created completely open.

Save as `generate-networkpolicy.yaml`:

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: default-networkpolicy
  annotations:
    policies.kyverno.io/title: "Generate Default NetworkPolicy"
    policies.kyverno.io/category: "Network Security"
    policies.kyverno.io/description: >-
      Generates a default-deny-all NetworkPolicy in every new namespace
      to enforce a zero-trust network posture by default.
spec:
  rules:
    - name: generate-default-networkpolicy
      match:
        any:
          - resources:
              kinds: [Namespace]
      generate:
        apiVersion: networking.k8s.io/v1
        kind: NetworkPolicy
        name: default-deny-all
        namespace: "{{request.object.metadata.name}}"
        data:
          spec:
            podSelector: {}
            policyTypes:
              - Ingress
              - Egress
```

Apply it:

```bash
kubectl apply -f generate-networkpolicy.yaml
```

> **Note:** This policy only fires on namespace *creation* events. Namespaces that already existed before this policy was applied won't automatically get the NetworkPolicy. See the Troubleshooting section for how to handle pre-existing namespaces.

---

## Step 5 - Review Audit Reports

After running in Audit mode for a day, check what would be blocked:

```bash
# Violations across all namespaces
kubectl get policyreport -A

# Cluster-wide report
kubectl get clusterpolicyreport

# Detailed breakdown for a specific namespace
kubectl describe polr -n default
```

Go through the output carefully. If you see violations from system namespaces, add them to your exclusion list before switching to Enforce. If you see violations from your own workloads, fix the workloads or make a conscious decision to exclude them.

---

## Step 6 - Switch to Enforce Mode

Once audit reports look clean, switch the validation policy to Enforce:

```bash
kubectl patch clusterpolicy require-resource-limits \
  --type=merge \
  -p '{"spec":{"validationFailureAction":"Enforce"}}'
```

Or update the YAML and re-apply:

```bash
# In require-resource-limits.yaml, change:
#   validationFailureAction: Audit
# to:
#   validationFailureAction: Enforce

kubectl apply -f require-resource-limits.yaml
```

---

## Step 7 - Test That Blocking Works

Deploy a pod intentionally missing resource limits:

```bash
kubectl run test-pod --image=nginx --restart=Never -n default
```

Expected result in Enforce mode:

```
Error from server: admission webhook "validate.kyverno.svc-fail" denied the request:
resource Pod/default/test-pod was blocked due to the following policies

require-resource-limits:
  check-resource-limits: CPU and memory limits are required on all containers.
```

If you're still in Audit mode, the pod will be allowed but the violation will appear in the policy report:

```bash
kubectl describe polr -n default
```

---

## Step 8 - Add Pre-built Policies from the Official Library

Kyverno maintains a policy library with production-ready rules. These three are worth adding immediately:

```bash
# Require standard Kubernetes labels
kubectl apply -f https://raw.githubusercontent.com/kyverno/policies/main/best-practices/require-labels/require-labels.yaml

# Block :latest image tags - forces pinned image versions
kubectl apply -f https://raw.githubusercontent.com/kyverno/policies/main/best-practices/disallow-latest-tag/disallow-latest-tag.yaml

# Disallow privileged containers
kubectl apply -f https://raw.githubusercontent.com/kyverno/policies/main/pod-security/baseline/disallow-privileged-containers/disallow-privileged-containers.yaml
```

These come in Audit mode by default. Review violations before switching to Enforce.

---

## Step 9 - Install Policy Reporter UI (Optional but Recommended)

The CLI reports get hard to read once you have more than a handful of policies. The Policy Reporter UI gives you a clean dashboard of all violations across the cluster:

```bash
helm install policy-reporter kyverno/policy-reporter \
  --namespace kyverno \
  --set ui.enabled=true \
  --set kyvernoPlugin.enabled=true \
  --set clusterreports.enabled=true
```

Access the UI locally via port-forward:

```bash
kubectl port-forward svc/policy-reporter-ui 8082:8080 -n kyverno
# Open http://localhost:8082 in your browser
```

---

## Step 10 - Verify All Active Policies

```bash
# List all policies and their current mode (Audit/Enforce)
kubectl get clusterpolicy

# Inspect a specific policy in detail
kubectl describe clusterpolicy require-resource-limits

# Full compliance summary across all namespaces
kubectl get policyreport -A
```

---

## How Policy Enforcement Works

```
Pod/Resource Created
        │
        ▼
   Kyverno Webhook
        │
        ├─→ Mutate    → auto-add labels, annotations, defaults
        │
        ├─→ Validate  → Audit (log only) or Enforce (block)
        │
        └─→ Generate  → auto-create NetworkPolicy, ConfigMap, etc.
```

---

## Troubleshooting

These are real issues I ran into, not hypotheticals.

---

### System pods in kube-system blocked after switching to Enforce

**What happened:** I switched `validationFailureAction` to `Enforce` on the resource limits policy. Shortly after, CoreDNS pods failed to restart during a rolling update. Other system pods in `kube-system` started throwing admission errors too.

**Why it happened:** System-managed pods like CoreDNS, `aws-node`, `kube-proxy`, don't always declare explicit resource limits. They rely on node-level QoS and defaults configured elsewhere. My policy was too broad and caught them.

**Fix:** Add explicit namespace exclusions to the policy's `exclude` block:

```yaml
spec:
  rules:
    - name: check-resource-limits
      match:
        any:
          - resources:
              kinds: [Pod]
      exclude:
        any:
          - resources:
              namespaces:
                - kube-system
                - kyverno
                - kube-public
                - kube-node-lease
      validate:
        message: "CPU and memory limits are required on all containers."
        pattern:
          spec:
            containers:
              - resources:
                  limits:
                    cpu: "?*"
                    memory: "?*"
```

Apply the fix:

```bash
kubectl apply -f require-resource-limits.yaml
```

**Lesson learned:** The audit report on my cluster showed zero violations in `kube-system`, but only because those pods were already running and weren't being rescheduled during the audit window. The violations only surfaced when pods actually restarted. Always check what's running in system namespaces before switching to Enforce.

---

### Generation policy didn't create NetworkPolicies for pre-existing namespaces

**What happened:** Applied the `default-networkpolicy` generation policy, then checked several of our existing namespaces, none of them had a `default-deny-all` NetworkPolicy.

**Why it happened:** Generation policies in Kyverno only fire on resource *creation* events. Namespaces that existed before the policy was applied aren't retroactively processed.

**Fix - Option A (annotate to trigger re-evaluation):**

```bash
for ns in $(kubectl get ns --no-headers -o custom-columns=":metadata.name" \
  | grep -vE "^kube-system$|^kube-public$|^kube-node-lease$|^kyverno$"); do
  echo "Triggering generation for: $ns"
  kubectl annotate namespace "$ns" kyverno.io/trigger=generate --overwrite
done
```

**Fix - Option B (direct backfill with a one-time loop):**

```bash
for ns in $(kubectl get ns --no-headers -o custom-columns=":metadata.name" \
  | grep -vE "^kube-system$|^kube-public$|^kube-node-lease$|^kyverno$"); do
  kubectl apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: $ns
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
EOF
done
```

I went with Option A. Option B works but means you're managing those NetworkPolicies outside Kyverno's lifecycle, which creates drift risk.

Verify the NetworkPolicies were created:

```bash
kubectl get networkpolicy --all-namespaces | grep default-deny-all
```

---

### Webhook timeout errors during pod scaling events

**What happened:** During a load test where roughly 50 pods were spinning up at the same time, around 15% of them failed with:

```
Error from server: etcd cluster is unavailable
```

etcd itself was completely healthy. The real error was buried in Kyverno's logs:

```bash
kubectl logs -n kyverno -l app.kubernetes.io/name=kyverno --tail=100 | grep -i timeout
# admission webhook "validate.kyverno.svc-fail" timed out after 10s
```

**Why it happened:** Kyverno was running with `replicaCount=1` in that environment. Under burst load, the single replica's admission webhook queue backed up and hit the default 10-second timeout. The `etcd cluster is unavailable` message was just the API server's generic fallback, it had nothing to do with etcd.

**Fix:** Upgrade the Helm release to scale up and increase the timeout:

```bash
helm upgrade kyverno kyverno/kyverno \
  --namespace kyverno \
  --reuse-values \
  --set replicaCount=3 \
  --set config.webhooks[0].timeoutSeconds=30
```

Also worth checking the `failurePolicy` setting, default is `Fail`, meaning if Kyverno can't respond in time, requests are rejected:

```bash
kubectl get validatingwebhookconfigurations \
  kyverno-resource-validating-webhook-cfg \
  -o jsonpath='{.webhooks[*].failurePolicy}'
```

For non-critical dev clusters you might switch this to `Ignore` so a slow Kyverno doesn't block pod creation entirely. For production, keep it as `Fail`.

---

### Mutation policy applied a literal string instead of the evaluated namespace value

**What happened:** After upgrading one of our app's Helm chart, newly created pods had this label:

```
env: {{request.namespace}}
```

Literally that string, not the actual namespace name.

**Why it happened:** I'd edited the mutation policy YAML and ran `kubectl apply` without deleting the old `ClusterPolicy` object first. The `apply` merged new rules into the stale object instead of replacing it cleanly, resulting in a policy that wasn't evaluating JMESPath(JSON Matching Expression paths) expressions correctly.

**Fix:** Delete and recreate the policy:

```bash
kubectl delete clusterpolicy add-default-labels
kubectl apply -f mutate-add-labels.yaml
```

Then restart affected deployments to replace the pods with bad labels:

```bash
kubectl rollout restart deployment -n <your-namespace>
```

Verify the labels are now correct:

```bash
kubectl get pods -n <your-namespace> --show-labels | grep env
```

---

### kyverno namespace stuck in Terminating after uninstall

**What happened:** Ran `helm uninstall kyverno -n kyverno` then `kubectl delete namespace kyverno`. The namespace sat in `Terminating` for over 10 minutes and never resolved.

**Why it happened:** Kyverno registers `ValidatingWebhookConfiguration` and `MutatingWebhookConfiguration` objects at the cluster level, outside the kyverno namespace. When the namespace began terminating, the API server tried to call those webhooks to validate the deletion, but the webhook endpoints were already gone. It deadlocked.

**Fix:** Delete the webhook configurations manually:

```bash
kubectl delete validatingwebhookconfigurations \
  kyverno-resource-validating-webhook-cfg \
  kyverno-policy-validating-webhook-cfg

kubectl delete mutatingwebhookconfigurations \
  kyverno-resource-mutating-webhook-cfg \
  kyverno-verify-mutating-webhook-cfg
```

The namespace resolved within about 15 seconds after that. If it still doesn't clear, check for stuck finalizers:

```bash
kubectl get namespace kyverno -o json | jq '.spec.finalizers'
```

If anything is listed, patch them out:

```bash
kubectl patch namespace kyverno \
  -p '{"spec":{"finalizers":[]}}' \
  --type=merge
```

---

## Key Takeaways

1. **Start with Audit, not Enforce.** Especially on an existing cluster with running workloads. Run for at least 24 hours, review the policy reports, fix your exclusions, then switch to Enforce.

2. **Always exclude system namespaces.** `kube-system`, `kyverno`, `kube-public`, and `kube-node-lease` should be in every validation policy's exclusion list. What looks clean in Audit can bite you on the next node restart.

3. **Pin the chart version.** Use `--version` in your `helm install` command. Kyverno upgrades can introduce breaking changes in policy behavior.

4. **Generation policies don't backfill.** Handle pre-existing namespaces separately with the annotation workaround or a one-time loop script.

5. **Run 3 replicas in production.** Kyverno is an admission webhook. A single replica under burst load causes cryptic errors that point at etcd instead of Kyverno.

6. **When a mutation policy behaves strangely, delete and recreate it.** `kubectl apply` on a ClusterPolicy can produce unexpected merge behavior. A clean delete/apply is more reliable.

---

## References

- [Kyverno official docs](https://kyverno.io/docs/)
- [Kyverno policy library](https://kyverno.io/policies/)
- [AWS EKS best practices for security](https://aws.github.io/aws-eks-best-practices/security/docs/)
- [Kyverno Helm chart values reference](https://github.com/kyverno/kyverno/blob/main/charts/kyverno/values.yaml)
