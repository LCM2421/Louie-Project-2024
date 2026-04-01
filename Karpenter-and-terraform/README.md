# Karpenter on EKS - Production Setup with Terraform

This repo documents how I set up Karpenter v1.7.0 on an existing EKS cluster using Terraform. I built this after hitting the limits of Cluster Autoscaler in a production environment for example slow provisioning, rigid node groups, and no real cost optimization out of the box. Karpenter solved all three.

Everything here is Terraform-native. No CloudFormation wrappers, no manual console steps.

---

## Why I Built This

We were running a workload with very spiky traffic most of the day, then 10x load for a few hours. Cluster Autoscaler was taking 3–5 minutes to bring up new nodes, and we were over-provisioning just to compensate. Switching to Karpenter cut our provisioning time to under 30 seconds and dropped our EC2 bill noticeably by consolidating idle nodes automatically.

---

## What's Inside

```
.
├── main.tf            # IAM roles, SQS queue, Helm release, kubectl manifests
├── versions.tf        # Provider definitions and version constraints
├── variables.tf       # Input variables
├── outputs.tf         # Exported values
└── terraform.tfvars   # Your actual cluster values go here
```

---

## How It Works

Karpenter runs as a controller inside the cluster. When a pod can't be scheduled because there's no available node, Karpenter intercepts that event and provisions an EC2 instance that fits the pod's exact resource requests, no predefined node group needed.

```
Pod stuck in Pending
       │
       ▼
Karpenter detects unschedulable pod
       │
       ▼
Evaluates NodePool requirements
(instance type, capacity type, arch)
       │
       ▼
Calls EC2 Fleet API directly
       │
       ▼
Node joins cluster in ~30 seconds
       │
       ▼
Pod scheduled ✅
```

When traffic dies down, Karpenter's consolidation kicks in. It bins-packs workloads onto fewer nodes and terminates the ones that are no longer needed.

---

## Prerequisites

- EKS cluster (v1.33+) already running
- OIDC provider enabled on the cluster
- AWS CLI, Terraform v1.7.0+, kubectl, and Helm v3 installed

Check your OIDC provider:
```bash
aws eks describe-cluster --name <cluster-name> \
  --query "cluster.identity.oidc.issuer" --output text
```

---

## Setup

### 1. Clone and configure

```bash
git clone https://github.com/<your-username>/karpenter-eks-terraform.git
cd karpenter-eks-terraform
```

Edit `terraform.tfvars`:
```hcl
cluster_name        = "your-eks-cluster"
aws_region          = "us-east-1"
karpenter_version   = "1.7.0"
karpenter_namespace = "kube-system"
node_workload_name  = "karpenter-workload"   # change to retarget the DaemonSet
```

### 2. Provider setup - `versions.tf`

```hcl
terraform {
  required_version = ">= 1.7.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.0"
    }
    kubectl = {
      source  = "gavinbunney/kubectl"
      version = "~> 1.14"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

provider "helm" {
  kubernetes {
    host                   = data.aws_eks_cluster.cluster.endpoint
    cluster_ca_certificate = base64decode(data.aws_eks_cluster.cluster.certificate_authority[0].data)
    token                  = data.aws_eks_cluster_auth.cluster.token
  }
}

provider "kubectl" {
  host                   = data.aws_eks_cluster.cluster.endpoint
  cluster_ca_certificate = base64decode(data.aws_eks_cluster.cluster.certificate_authority[0].data)
  token                  = data.aws_eks_cluster_auth.cluster.token
  load_config_file       = false
}
```

### 3. Variables - `variables.tf`

```hcl
variable "cluster_name" {
  description = "EKS cluster name"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "karpenter_version" {
  description = "Karpenter Helm chart version"
  type        = string
  default     = "1.7.0"
}

variable "karpenter_namespace" {
  description = "Namespace to install Karpenter"
  type        = string
  default     = "kube-system"
}

variable "node_instance_types" {
  description = "Allowed EC2 instance categories"
  type        = list(string)
  default     = ["c", "m", "r"]
}

variable "node_workload_name" {
  description = "Logical workload name stamped onto every Karpenter node as a label and EC2 tag. Used by the per-node DaemonSet nodeSelector."
  type        = string
  default     = "karpenter-workload"
}
```

### 4. Core infrastructure - `main.tf`

**Fetch existing cluster data:**
```hcl
data "aws_caller_identity" "current" {}

data "aws_eks_cluster" "cluster" {
  name = var.cluster_name
}

data "aws_eks_cluster_auth" "cluster" {
  name = var.cluster_name
}

data "aws_iam_openid_connect_provider" "oidc" {
  url = data.aws_eks_cluster.cluster.identity[0].oidc[0].issuer
}
```

**Tag subnets and security groups for discovery:**
```hcl
data "aws_subnets" "karpenter" {
  filter {
    name   = "tag:kubernetes.io/cluster/${var.cluster_name}"
    values = ["shared", "owned"]
  }
}

resource "aws_ec2_tag" "subnet_karpenter_discovery" {
  for_each    = toset(data.aws_subnets.karpenter.ids)
  resource_id = each.value
  key         = "karpenter.sh/discovery"
  value       = var.cluster_name
}

data "aws_security_group" "node_sg" {
  filter {
    name   = "tag:kubernetes.io/cluster/${var.cluster_name}"
    values = ["owned"]
  }
  filter {
    name   = "tag:aws:eks:nodegroup-name"
    values = ["*"]
  }
}

resource "aws_ec2_tag" "sg_karpenter_discovery" {
  resource_id = data.aws_security_group.node_sg.id
  key         = "karpenter.sh/discovery"
  value       = var.cluster_name
}
```

**Node IAM role (for EC2 instances Karpenter provisions):**
```hcl
data "aws_iam_policy_document" "karpenter_node_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "karpenter_node" {
  name               = "KarpenterNodeRole-${var.cluster_name}"
  assume_role_policy = data.aws_iam_policy_document.karpenter_node_assume_role.json
  tags = {
    Name       = "KarpenterNodeRole-${var.cluster_name}"
    managed-by = "terraform"
  }
}

resource "aws_iam_role_policy_attachment" "karpenter_node_policies" {
  for_each = toset([
    "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
    "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy",
    "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
    "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore",
  ])
  role       = aws_iam_role.karpenter_node.name
  policy_arn = each.value
}

resource "aws_iam_instance_profile" "karpenter_node" {
  name = "KarpenterNodeInstanceProfile-${var.cluster_name}"
  role = aws_iam_role.karpenter_node.name
}
```

**Controller IAM role with IRSA (no static credentials):**
```hcl
data "aws_iam_policy_document" "karpenter_controller_assume_role" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [data.aws_iam_openid_connect_provider.oidc.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "${replace(data.aws_iam_openid_connect_provider.oidc.url, "https://", "")}:sub"
      values   = ["system:serviceaccount:${var.karpenter_namespace}:karpenter"]
    }
    condition {
      test     = "StringEquals"
      variable = "${replace(data.aws_iam_openid_connect_provider.oidc.url, "https://", "")}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "karpenter_controller" {
  name               = "KarpenterControllerRole-${var.cluster_name}"
  assume_role_policy = data.aws_iam_policy_document.karpenter_controller_assume_role.json
  tags = {
    Name       = "KarpenterControllerRole-${var.cluster_name}"
    managed-by = "terraform"
  }
}

data "aws_iam_policy_document" "karpenter_controller_policy" {
  statement {
    sid    = "AllowEC2Actions"
    effect = "Allow"
    actions = [
      "ec2:CreateFleet",
      "ec2:CreateLaunchTemplate",
      "ec2:CreateTags",
      "ec2:DeleteLaunchTemplate",
      "ec2:DescribeAvailabilityZones",
      "ec2:DescribeImages",
      "ec2:DescribeInstances",
      "ec2:DescribeInstanceTypeOfferings",
      "ec2:DescribeInstanceTypes",
      "ec2:DescribeLaunchTemplates",
      "ec2:DescribeSecurityGroups",
      "ec2:DescribeSpotPriceHistory",
      "ec2:DescribeSubnets",
      "ec2:RunInstances",
      "ec2:TerminateInstances",
    ]
    resources = ["*"]
  }

  statement {
    sid     = "AllowIAMPassRole"
    effect  = "Allow"
    actions = ["iam:PassRole"]
    resources = [aws_iam_role.karpenter_node.arn]
  }

  statement {
    sid    = "AllowSQSInterruption"
    effect = "Allow"
    actions = [
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
      "sqs:GetQueueUrl",
      "sqs:ReceiveMessage",
    ]
    resources = [aws_sqs_queue.karpenter_interruption.arn]
  }

  statement {
    sid     = "AllowSSMGetParameter"
    effect  = "Allow"
    actions = ["ssm:GetParameter"]
    resources = ["arn:aws:ssm:${var.aws_region}::parameter/aws/service/*"]
  }

  statement {
    sid    = "AllowEKSAndIAMActions"
    effect = "Allow"
    actions = [
      "eks:DescribeCluster",
      "iam:CreateInstanceProfile",
      "iam:AddRoleToInstanceProfile",
      "iam:RemoveRoleFromInstanceProfile",
      "iam:DeleteInstanceProfile",
      "iam:GetInstanceProfile",
    ]
    resources = ["*"]
  }

  statement {
    sid     = "AllowPricingActions"
    effect  = "Allow"
    actions = ["pricing:GetProducts"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "karpenter_controller" {
  name   = "KarpenterControllerPolicy-${var.cluster_name}"
  role   = aws_iam_role.karpenter_controller.id
  policy = data.aws_iam_policy_document.karpenter_controller_policy.json
}
```

**SQS queue for Spot interruption handling:**
```hcl
resource "aws_sqs_queue" "karpenter_interruption" {
  name                    = "${var.cluster_name}-karpenter-interruption"
  message_retention_seconds = 300
  sqs_managed_sse_enabled = true
  tags = {
    Name       = "${var.cluster_name}-karpenter-interruption"
    managed-by = "terraform"
  }
}

resource "aws_sqs_queue_policy" "karpenter_interruption" {
  queue_url = aws_sqs_queue.karpenter_interruption.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = ["events.amazonaws.com", "sqs.amazonaws.com"] }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.karpenter_interruption.arn
    }]
  })
}

locals {
  interruption_rules = {
    spot_interruption  = { source = "aws.ec2",    detail_type = ["EC2 Spot Instance Interruption Warning"] }
    instance_rebalance = { source = "aws.ec2",    detail_type = ["EC2 Instance Rebalance Recommendation"] }
    instance_state     = { source = "aws.ec2",    detail_type = ["EC2 Instance State-change Notification"] }
    scheduled_change   = { source = "aws.health", detail_type = ["AWS Health Event"] }
  }
}

resource "aws_cloudwatch_event_rule" "karpenter_interruption" {
  for_each    = local.interruption_rules
  name        = "${var.cluster_name}-karpenter-${each.key}"
  description = "Karpenter interruption rule for ${each.key}"
  event_pattern = jsonencode({
    source      = [each.value.source]
    detail-type = each.value.detail_type
  })
}

resource "aws_cloudwatch_event_target" "karpenter_interruption" {
  for_each  = aws_cloudwatch_event_rule.karpenter_interruption
  rule      = each.value.name
  target_id = "KarpenterInterruptionQueueTarget"
  arn       = aws_sqs_queue.karpenter_interruption.arn
}
```

**Allow Karpenter nodes to join the cluster:**
```hcl
resource "aws_eks_access_entry" "karpenter_node" {
  cluster_name  = var.cluster_name
  principal_arn = aws_iam_role.karpenter_node.arn
  type          = "EC2_LINUX"
  depends_on    = [aws_iam_role.karpenter_node]
}
```

**Install Karpenter via Helm:**
```hcl
resource "helm_release" "karpenter" {
  name       = "karpenter"
  repository = "oci://public.ecr.aws/karpenter"
  chart      = "karpenter"
  version    = var.karpenter_version
  namespace  = var.karpenter_namespace

  set {
    name  = "settings.clusterName"
    value = var.cluster_name
  }
  set {
    name  = "settings.interruptionQueue"
    value = aws_sqs_queue.karpenter_interruption.name
  }
  set {
    name  = "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
    value = aws_iam_role.karpenter_controller.arn
  }
  set {
    name  = "controller.resources.requests.cpu"
    value = "1"
  }
  set {
    name  = "controller.resources.requests.memory"
    value = "1Gi"
  }
  set {
    name  = "replicas"
    value = "2"
  }

  # Spread Karpenter controller pods across availability zones
  set {
    name  = "topologySpreadConstraints[0].maxSkew"
    value = "1"
  }
  set {
    name  = "topologySpreadConstraints[0].topologyKey"
    value = "topology.kubernetes.io/zone"
  }
  set {
    name  = "topologySpreadConstraints[0].whenUnsatisfiable"
    value = "DoNotSchedule"
  }
  set {
    name  = "topologySpreadConstraints[0].labelSelector.matchLabels.app\\.kubernetes\\.io/name"
    value = "karpenter"
  }

  # Prevent two Karpenter pods from landing on the same node
  set {
    name  = "affinity.podAntiAffinity.requiredDuringSchedulingIgnoredDuringExecution[0].topologyKey"
    value = "kubernetes.io/hostname"
  }
  set {
    name  = "affinity.podAntiAffinity.requiredDuringSchedulingIgnoredDuringExecution[0].labelSelector.matchLabels.app\\.kubernetes\\.io/name"
    value = "karpenter"
  }

  depends_on = [
    aws_iam_role_policy.karpenter_controller,
    aws_eks_access_entry.karpenter_node,
    aws_sqs_queue.karpenter_interruption,
  ]
}
```

**Apply NodePool and EC2NodeClass manifests:**
```hcl
resource "kubectl_manifest" "karpenter_nodepool" {
  yaml_body = <<-YAML
    apiVersion: karpenter.sh/v1
    kind: NodePool
    metadata:
      name: default
    spec:
      template:
        metadata:
          # Every node Karpenter provisions gets this label.
          # The per-node DaemonSet targets this label via nodeSelector.
          labels:
            workload: "${var.node_workload_name}"
        spec:
          nodeClassRef:
            group: karpenter.k8s.aws
            kind: EC2NodeClass
            name: default
          requirements:
            - key: karpenter.sh/capacity-type
              operator: In
              values: ["spot", "on-demand"]
            - key: kubernetes.io/arch
              operator: In
              values: ["amd64"]
            - key: karpenter.k8s.aws/instance-category
              operator: In
              values: ${jsonencode(var.node_instance_types)}
            - key: karpenter.k8s.aws/instance-generation
              operator: Gt
              values: ["2"]
      limits:
        cpu: 1000
        memory: 1000Gi
      disruption:
        consolidationPolicy: WhenEmptyOrUnderutilized
        consolidateAfter: 1m
  YAML
  depends_on = [helm_release.karpenter]
}

resource "kubectl_manifest" "karpenter_ec2nodeclass" {
  yaml_body = <<-YAML
    apiVersion: karpenter.k8s.aws/v1
    kind: EC2NodeClass
    metadata:
      name: default
    spec:
      amiSelectorTerms:
        - alias: al2023@latest
      role: "${aws_iam_role.karpenter_node.name}"
      subnetSelectorTerms:
        - tags:
            karpenter.sh/discovery: "${var.cluster_name}"
      securityGroupSelectorTerms:
        - tags:
            karpenter.sh/discovery: "${var.cluster_name}"
      tags:
        Name: karpenter-node
        cluster: "${var.cluster_name}"
        managed-by: karpenter
        # Mirrors the NodePool label so the EC2 instance is also tagged
        # useful for cost allocation and AWS-side filtering.
        workload: "${var.node_workload_name}"
  YAML
  depends_on = [helm_release.karpenter]
}

# DaemonSet - runs one pod on every node Karpenter provisions.
# nodeSelector targets the `workload` label injected by the NodePool above,
# so pods only land on Karpenter-managed nodes and never on static node groups.
# Change `var.node_workload_name` in terraform.tfvars to retarget the DaemonSet
# without touching any manifest by hand.
resource "kubectl_manifest" "karpenter_node_daemonset" {
  yaml_body = <<-YAML
    apiVersion: apps/v1
    kind: DaemonSet
    metadata:
      name: ${var.node_workload_name}-agent
      namespace: kube-system
      labels:
        app: ${var.node_workload_name}-agent
        managed-by: karpenter-terraform
    spec:
      selector:
        matchLabels:
          app: ${var.node_workload_name}-agent
      updateStrategy:
        type: RollingUpdate
        rollingUpdate:
          maxUnavailable: 1
      template:
        metadata:
          labels:
            app: ${var.node_workload_name}-agent
            # Carries the workload name into the pod for log/metric filtering
            workload: ${var.node_workload_name}
        spec:
          # ── Targeting ────────────────────────────────────────────────────
          # Only schedule on nodes that were provisioned by this NodePool.
          # The label `workload: <name>` is stamped onto every node by the
          # NodePool's spec.template.metadata.labels block above.
          nodeSelector:
            workload: ${var.node_workload_name}

          # Tolerate the standard Karpenter not-ready taint so this pod
          # can start as soon as the node boots, before other workloads land.
          tolerations:
            - key: node.kubernetes.io/not-ready
              operator: Exists
              effect: NoExecute
              tolerationSeconds: 300
            - key: node.kubernetes.io/unreachable
              operator: Exists
              effect: NoExecute
              tolerationSeconds: 300

          # ── Scheduling quality ───────────────────────────────────────────
          # Spread the DaemonSet pods evenly across AZs for observability
          # coverage. whenUnsatisfiable: ScheduleAnyway keeps things running
          # even if zone balance is temporarily uneven.
          topologySpreadConstraints:
            - maxSkew: 1
              topologyKey: topology.kubernetes.io/zone
              whenUnsatisfiable: ScheduleAnyway
              labelSelector:
                matchLabels:
                  app: ${var.node_workload_name}-agent

          # ── Container ────────────────────────────────────────────────────
          containers:
            - name: agent
              image: public.ecr.aws/amazonlinux/amazonlinux:2023
              command: ["/bin/sh", "-c"]
              args:
                - |
                  echo "Node agent starting on $(hostname)"
                  echo "NodePool workload label: ${var.node_workload_name}"
                  # Replace this block with your real workload:
                  # e.g. a log shipper, metrics exporter, security scanner, etc.
                  while true; do
                    echo "[$(date -u +%FT%TZ)] agent heartbeat on $(hostname)"
                    sleep 60
                  done
              resources:
                requests:
                  cpu: "50m"
                  memory: "64Mi"
                limits:
                  cpu: "100m"
                  memory: "128Mi"
              # Expose node metadata to the container via the Downward API
              env:
                - name: NODE_NAME
                  valueFrom:
                    fieldRef:
                      fieldPath: spec.nodeName
                - name: POD_NAME
                  valueFrom:
                    fieldRef:
                      fieldPath: metadata.name
                - name: POD_NAMESPACE
                  valueFrom:
                    fieldRef:
                      fieldPath: metadata.namespace
                - name: WORKLOAD_NAME
                  value: "${var.node_workload_name}"
          # Run with minimal privileges - no root needed for a basic agent
          securityContext:
            runAsNonRoot: true
            runAsUser: 1000
            seccompProfile:
              type: RuntimeDefault
  YAML
  depends_on = [
    kubectl_manifest.karpenter_nodepool,
    kubectl_manifest.karpenter_ec2nodeclass,
  ]
}
```

### 5. Outputs — `outputs.tf`

```hcl
output "karpenter_controller_role_arn" {
  description = "IAM Role ARN for the Karpenter Controller"
  value       = aws_iam_role.karpenter_controller.arn
}

output "karpenter_node_role_arn" {
  description = "IAM Role ARN for Karpenter-provisioned nodes"
  value       = aws_iam_role.karpenter_node.arn
}

output "karpenter_interruption_queue_url" {
  description = "SQS Queue URL for Spot interruption handling"
  value       = aws_sqs_queue.karpenter_interruption.url
}

output "karpenter_interruption_queue_arn" {
  description = "SQS Queue ARN for Spot interruption handling"
  value       = aws_sqs_queue.karpenter_interruption.arn
}
```

### 6. Deploy

```bash
terraform init
terraform plan -out=karpenter.tfplan
terraform apply karpenter.tfplan
```

### 7. Verify

```bash
# Check Karpenter controller pods
kubectl get pods -n kube-system -l app.kubernetes.io/name=karpenter

# Confirm NodePool and EC2NodeClass are registered
kubectl get nodepool
kubectl get ec2nodeclass

# Verify the per-node DaemonSet is running on all Karpenter nodes
kubectl get daemonset -n kube-system
kubectl get pods -n kube-system -l workload=karpenter-workload -o wide

# Confirm the workload label is present on every Karpenter node
kubectl get nodes -l workload=karpenter-workload --show-labels

# Tail the controller logs
kubectl logs -n kube-system \
  -l app.kubernetes.io/name=karpenter -f
```

---

## Per-Node DaemonSet - Dynamic Wiring to NodePool and EC2NodeClass

The repo includes a `kubectl_manifest` DaemonSet that runs one pod on every node Karpenter provisions. All three resources like NodePool, EC2NodeClass, and DaemonSet are wired together through a single Terraform variable: `node_workload_name`.

### How the wiring works

```
terraform.tfvars
  node_workload_name = "karpenter-workload"
          │
          ├─► NodePool  spec.template.metadata.labels
          │     workload: karpenter-workload          ← stamped on every node kubelet registers
          │
          ├─► EC2NodeClass  spec.tags
          │     workload: karpenter-workload          ← same value on the EC2 instance (cost allocation)
          │
          └─► DaemonSet  spec.template.spec.nodeSelector
                workload: karpenter-workload          ← pod only schedules where this label exists
```

When Karpenter provisions a new node, the NodePool injects `workload: <n>` as a kubelet node label before the node joins the cluster. The DaemonSet's `nodeSelector` matches that label, therefore Kubernetes schedules exactly one DaemonSet pod per Karpenter node - automatically, with no manual intervention. Static node groups that don't carry the label are left untouched.

Changing `node_workload_name` in `terraform.tfvars` and re-running `terraform apply` updates the label in all three places automically:

```hcl
# terraform.tfvars
node_workload_name = "my-monitoring-agent"   # was "karpenter-workload"
```

```bash
terraform apply   # NodePool, EC2NodeClass, and DaemonSet all updated in one pass
```

### Terraform dependency chain

```
helm_release.karpenter
        │
        ├─► kubectl_manifest.karpenter_nodepool
        │         │
        └─► kubectl_manifest.karpenter_ec2nodeclass
                  │
                  └─► kubectl_manifest.karpenter_node_daemonset
```

The DaemonSet `depends_on` both the NodePool and EC2NodeClass, so it is never applied before Karpenter can honour its `nodeSelector`.

### Customising the agent container

The DaemonSet ships with a minimal Amazon Linux 2023 container that prints a heartbeat log. Replace the `command`/`args` block with your actual workload — a log shipper, metrics exporter, security scanner, or any per-node agent:

```yaml
containers:
  - name: agent
    image: your-ecr-repo/your-agent:latest
    command: ["/usr/bin/your-agent"]
    args: ["--config", "/etc/agent/config.yaml"]
    resources:
      requests:
        cpu: "50m"
        memory: "64Mi"
      limits:
        cpu: "100m"
        memory: "128Mi"
    env:
      - name: NODE_NAME
        valueFrom:
          fieldRef:
            fieldPath: spec.nodeName
      - name: WORKLOAD_NAME
        value: "${var.node_workload_name}"   # injected by Terraform at apply time
```

The `NODE_NAME` and `WORKLOAD_NAME` environment variables are already wired in via the Downward API, so your agent always knows which node it is running on and which NodePool workload it belongs to.

---

## Pod Scheduling: Affinity and Topology Spread

Karpenter provisions nodes based on pod requirements. To get proper HA spread and co-location behaviour from your own workloads, define `podAffinity`/`podAntiAffinity` and `topologySpreadConstraints` directly in your Deployment manifests. Karpenter will read these constraints and provision nodes in the appropriate AZs automatically.

### Spread pods across availability zones

Use `topologySpreadConstraints` to ensure replicas are distributed across AZs. If a zone goes down, your service stays up.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: my-app
  template:
    metadata:
      labels:
        app: my-app
    spec:
      topologySpreadConstraints:
        # Spread evenly across availability zones
        - maxSkew: 1
          topologyKey: topology.kubernetes.io/zone
          whenUnsatisfiable: DoNotSchedule
          labelSelector:
            matchLabels:
              app: my-app
        # Also spread across individual nodes within each zone
        - maxSkew: 1
          topologyKey: kubernetes.io/hostname
          whenUnsatisfiable: ScheduleAnyway
          labelSelector:
            matchLabels:
              app: my-app
      containers:
        - name: my-app
          image: my-app:latest
          resources:
            requests:
              cpu: "250m"
              memory: "256Mi"
```

`maxSkew: 1` means the difference in pod count between any two zones/nodes is at most 1. `DoNotSchedule` makes this a hard constraint. Karpenter will provision a node in the right zone rather than pile pods onto an existing one.

### Prevent replica co-location (podAntiAffinity)

Use `requiredDuringSchedulingIgnoredDuringExecution` to hard-enforce that no two replicas of the same app land on the same node:

```yaml
spec:
  template:
    spec:
      affinity:
        podAntiAffinity:
          # Hard rule: never schedule two replicas on the same node
          requiredDuringSchedulingIgnoredDuringExecution:
            - topologyKey: kubernetes.io/hostname
              labelSelector:
                matchLabels:
                  app: my-app
          # Soft rule: prefer different AZs, but don't block if not possible
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 100
              podAffinityTerm:
                topologyKey: topology.kubernetes.io/zone
                labelSelector:
                  matchLabels:
                    app: my-app
```

### Co-locate pods that communicate frequently (podAffinity)

If two services have heavy inter-pod traffic and you want to keep them on the same node (or in the same AZ) to reduce latency and data transfer costs:

```yaml
spec:
  template:
    spec:
      affinity:
        podAffinity:
          # Prefer the same node as the cache layer
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 80
              podAffinityTerm:
                topologyKey: kubernetes.io/hostname
                labelSelector:
                  matchLabels:
                    app: my-cache
          # Hard rule: must be in the same AZ as the database
          requiredDuringSchedulingIgnoredDuringExecution:
            - topologyKey: topology.kubernetes.io/zone
              labelSelector:
                matchLabels:
                  app: my-database
```

### Combined example (production-ready)

This is the pattern I use for stateless services that need both HA spread and node isolation:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: my-app
  template:
    metadata:
      labels:
        app: my-app
    spec:
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: topology.kubernetes.io/zone
          whenUnsatisfiable: DoNotSchedule
          labelSelector:
            matchLabels:
              app: my-app
        - maxSkew: 1
          topologyKey: kubernetes.io/hostname
          whenUnsatisfiable: ScheduleAnyway
          labelSelector:
            matchLabels:
              app: my-app
      affinity:
        podAntiAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            - topologyKey: kubernetes.io/hostname
              labelSelector:
                matchLabels:
                  app: my-app
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 100
              podAffinityTerm:
                topologyKey: topology.kubernetes.io/zone
                labelSelector:
                  matchLabels:
                    app: my-app
      containers:
        - name: my-app
          image: my-app:latest
          resources:
            requests:
              cpu: "250m"
              memory: "256Mi"
            limits:
              cpu: "500m"
              memory: "512Mi"
```

**Why this works well with Karpenter:** Karpenter sees the `topologySpreadConstraints` on a pending pod and provisions a node in the correct AZ to satisfy them. The `podAntiAffinity` on `kubernetes.io/hostname` then ensures no two replicas share that node. Together, you get automatic multi-AZ placement without pre-creating nodes or node groups.

> **Note:** Always set `resources.requests` on every container. Karpenter uses requests not limits, to size the node. A pod without requests may land on an undersized instance.

---

## Troubleshooting

### Pods stuck in Pending

This is usually the first thing that goes wrong. Here's the exact sequence I follow.

**Check pod events first:**
```bash
kubectl describe pod <pod-name> -n <namespace>
```

Look for `FailedScheduling` — it tells you what the scheduler couldn't satisfy (CPU, memory, node selector, taint, etc.).

**Check Karpenter logs:**
```bash
kubectl logs -n kube-system \
  -l app.kubernetes.io/name=karpenter -c controller -f
```

Common messages and what they mean:

| Message | What's wrong |
|---|---|
| `no instance type found` | NodePool requirements are too restrictive — no EC2 type matches |
| `failed to launch instance` | IAM permission missing or EC2 quota hit |
| `NodePool has no capacity` | You've hit the CPU/memory limit defined in the NodePool |
| `subnets not found` | Subnet tags `karpenter.sh/discovery` are missing or wrong |
| `securityGroups not found` | Security group tags are missing |
| `node not registered` | Node booted but kubelet couldn't register — check the node role |

**Verify NodePool and EC2NodeClass are healthy:**
```bash
kubectl get nodepool
kubectl get ec2nodeclass
kubectl describe nodepool default
kubectl describe ec2nodeclass default
```

Both should show `Ready: True`. If EC2NodeClass is not ready, the subnet or security group discovery failed.

**Check your pod has resource requests defined:**

Karpenter sizes nodes based on pod requests. If requests are missing, it may pick an instance that's too small or behave unexpectedly.

```bash
kubectl get pod <pod-name> -o yaml | grep -A 10 resources
```

Your pod should have something like this:
```yaml
resources:
  requests:
    cpu: "250m"
    memory: "256Mi"
  limits:
    cpu: "500m"
    memory: "512Mi"
```

**Check NodePool limits aren't maxed out:**
```bash
kubectl describe nodepool default | grep -A 5 "Limits\|Usage"
```

If you're at the limit, either bump it or the pending pods will sit there until something scales down.

**Verify subnet and security group tags exist:**
```bash
aws ec2 describe-subnets \
  --filters "Name=tag:karpenter.sh/discovery,Values=${CLUSTER_NAME}" \
  --query 'Subnets[*].SubnetId'

aws ec2 describe-security-groups \
  --filters "Name=tag:karpenter.sh/discovery,Values=${CLUSTER_NAME}" \
  --query 'SecurityGroups[*].GroupId'
```

If either returns empty, the `aws_ec2_tag` resources didn't apply correctly, now check Terraform state.

**Check for EC2 quota limits:**
```bash
aws service-quotas get-service-quota \
  --service-code ec2 \
  --quota-code L-1216C47A
```

If you're near the limit, Karpenter will fail silently on instance launch. Request an increase via the AWS console.

**Quick checklist:**
```
□ kubectl describe pod     → FailedScheduling reason
□ Karpenter controller log → any errors on provisioning
□ NodePool Ready=True
□ EC2NodeClass Ready=True
□ Subnet tags applied
□ Security group tags applied
□ IAM controller role exists and has IRSA annotation
□ NodePool limits not exceeded
□ Pod has resource requests defined
□ EC2 vCPU quotas not exceeded
□ Cluster Autoscaler is disabled
```

---

## Things I Learned Along the Way

**Don't remove all your existing nodes.** Keep at least one or two nodes running so Karpenter itself has somewhere to live. I made the mistake of scaling a node group to zero before verifying Karpenter was fully healthy, it took a while to recover.

**Start with `Audit` before `Enforce` on disruption policies.** If you jump straight to aggressive consolidation in a production environment without understanding your workload patterns first, you'll cause unnecessary pod churn.

**Spot + On-Demand together.** I always define both in the `capacity-type` requirement. Karpenter will try Spot first and fall back to On-Demand automatically. This alone cut EC2 costs significantly without any reliability trade-off.

**Disable Cluster Autoscaler before enabling Karpenter on the same node groups.** Running both at the same time causes them to fight each other. Scale CA to zero first.

```bash
kubectl scale deploy cluster-autoscaler -n kube-system --replicas=0
```

---

## Useful Commands

```bash
# List all nodes provisioned by Karpenter
kubectl get nodes -l karpenter.sh/nodepool

# Check all NodeClaims (one per node Karpenter manages)
kubectl get nodeclaim

# Delete a specific NodeClaim to trigger replacement
kubectl delete nodeclaim <name>

# Force Karpenter to re-evaluate consolidation
kubectl annotate nodepool default karpenter.sh/do-not-disrupt-

# Watch provisioning events in real time
kubectl get events -n kube-system --field-selector reason=ProvisioningSucceeded -w
```

---

## References

- [Karpenter Docs](https://karpenter.sh/docs/)
- [Karpenter GitHub](https://github.com/aws/karpenter-provider-aws)
- [NodePool API](https://karpenter.sh/docs/concepts/nodepools/)
- [EC2NodeClass API](https://karpenter.sh/docs/concepts/nodeclasses/)
- [Karpenter v1.7.0 Release Notes](https://github.com/aws/karpenter-provider-aws/releases/tag/v1.7.0)
