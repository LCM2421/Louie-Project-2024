# Dynamic Terratest Pipeline - GitLab CI + Terragrunt + AWS OIDC

> **Automated infrastructure testing that only runs what changed.**  
> Drop a new Terraform module into `infra/dev/`, open an MR - the pipeline finds it, deploys it, validates it, and tears it down. No manual config. No orphaned resources.

---

## What This Project Solves

Most CI pipelines for Terraform either test *everything* on every commit (slow, expensive) or test *nothing* automatically (risky). This pipeline it uses `git diff` to detect exactly which modules changed in a merge request and tests *only those*, in parallel, against real AWS infrastructure.

---

## Architecture Overview

```
Merge Request Opened
        │
        ▼
┌───────────────────┐
│     git-diff      │  Scans changed *.tf / *.hcl paths
│                   │  Extracts module names from file paths
│  TF_CHANGED=true  │  Exports: CHANGED_MODULES="aws_ec2 aws_secretsmanager"
└────────┬──────────┘
         │ (dotenv artifact - passed to ALL downstream jobs)
         ▼
┌───────────────────┐
│     validate      │  terragrunt run-all validate
│                   │  Loops over each module in CHANGED_MODULES
│  No AWS cost      │  Fast syntax + provider schema check
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│    terratest      │  OIDC auth → short-lived AWS creds
│                   │  go test -run TestChangedModules -parallel 4
│  Real resources   │  Per-module assertions (EC2, Secrets Manager…)
└────────┬──────────┘
         │  (when: always - runs even if terratest fails)
         ▼
┌───────────────────┐
│     destroy       │  go test -run TestCleanup
│                   │  Guaranteed cleanup, 5× retry with backoff
│  Zero orphans     │  Same CHANGED_MODULES + CI_PIPELINE_ID prefix
└───────────────────┘
```

If no Terraform files changed → `TF_CHANGED=false` → all downstream jobs are **skipped automatically**.

---

## Key Design Decisions

### 1. Dynamic Module Discovery via `git diff`

The `git-diff` job parses changed file paths to extract module names:

```bash
# Input:  modules/aws_ec2/main.tf
#         infra/dev/aws_secretsmanager/terragrunt.hcl
# Output: CHANGED_MODULES="aws_ec2 aws_secretsmanager"

MODULES=$(echo "$CHANGED_FILES" \
  | grep -oE '(modules|infra/[^/]+)/([^/]+)' \
  | awk -F'/' '{print $NF}' \
  | sort -u \
  | tr '\n' ' ')
```

The result is exported as a GitLab dotenv artifact, making `CHANGED_MODULES` available to every downstream job without any extra wiring.

**Why this matters:** Adding a new module (e.g. `aws_rds`) requires zero changes to the pipeline. The git-diff regex picks it up automatically.

---

### 2. `discoverChangedModules()` — Runtime Module Resolution in Go

```go
// test/terragrunt_test.go

func discoverChangedModules() []string {
    raw := os.Getenv("CHANGED_MODULES")  // "aws_ec2 aws_secretsmanager"
    var dirs []string
    for _, mod := range strings.Fields(raw) {
        dirs = append(dirs, filepath.Join("..", "infra", "dev", mod))
    }
    return dirs  // ["../infra/dev/aws_ec2", "../infra/dev/aws_secretsmanager"]
}
```

The Go test binary reads `CHANGED_MODULES` at runtime, so the same test binary handles any combination of modules without recompilation.

---

### 3. Parallel Test Execution with Isolation

Each module runs as a sub-test with `t.Parallel()`:

```go
func TestChangedModules(t *testing.T) {
    t.Parallel()
    for _, dir := range discoverChangedModules() {
        dir := dir  // capture loop variable
        t.Run(filepath.Base(dir), func(t *testing.T) {
            t.Parallel()
            opts := moduleOpts(t, dir)
            defer terragrunt.TgDestroyAll(t, opts)  // cleanup on any exit
            terragrunt.TgApplyAll(t, opts)
            assertModule(t, filepath.Base(dir), opts)
        })
    }
}
```

Resources are isolated by `TF_VAR_prefix: "ci-${CI_PIPELINE_ID}"` - multiple open MRs can run simultaneously without collision.

---

### 4. Module-Specific Assertions with an Extensible Dispatch Pattern

```go
func assertModule(t *testing.T, modName string, opts *terragrunt.Options) {
    switch modName {
    case "aws_ec2":
        assertEC2(t, opts)
    case "aws_secretsmanager":
        assertSecretsManager(t, opts)
    default:
        // Smoke test: verify apply produced at least one output
        outputs := terragrunt.OutputAll(t, opts)
        assert.NotEmpty(t, outputs, "module %q produced no outputs", modName)
    }
}
```

The `default` case means any new module gets a free smoke test. Richer assertions are added by appending a new `case` - no pipeline changes required.

**EC2 assertions example:**
```go
func assertEC2(t *testing.T, opts *terragrunt.Options) {
    instanceID    := terragrunt.Output(t, opts, "instance_id")
    publicIP      := terragrunt.Output(t, opts, "public_ip")
    instanceState := terragrunt.Output(t, opts, "instance_state")

    assert.NotEmpty(t, instanceID)
    assert.NotEmpty(t, publicIP)
    assert.Equal(t, "running", instanceState)
}
```

**Secrets Manager assertions example:**
```go
func assertSecretsManager(t *testing.T, opts *terragrunt.Options) {
    secretARN  := terragrunt.Output(t, opts, "secret_arn")
    secretName := terragrunt.Output(t, opts, "secret_name")

    assert.Contains(t, secretARN, "arn:aws:secretsmanager")
    assert.NotEmpty(t, secretName)
}
```

---

### 5. Keyless AWS Auth via GitLab OIDC

No long-lived IAM keys. GitLab exchanges a short-lived OIDC token for temporary AWS credentials scoped to this pipeline:

```yaml
id_tokens:
  AWS_OIDC_TOKEN:
    aud: https://gitlab.com

script:
  - eval $(aws sts assume-role-with-web-identity \
      --role-arn "${AWS_ROLE_ARN}" \
      --role-session-name "gitlab-terratest-${CI_PIPELINE_ID}" \
      --web-identity-token "${AWS_OIDC_TOKEN}" \
      --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' \
      --output text \
      | awk '{
          print "export AWS_ACCESS_KEY_ID="$1
          print "export AWS_SECRET_ACCESS_KEY="$2
          print "export AWS_SESSION_TOKEN="$3
        }')
```

IAM trust policy restricts access to this repository only:
```json
"Condition": {
  "StringLike": {
    "gitlab.com:sub": "project_path:<your-group>/<your-repo>:ref_type:branch:ref:*"
  }
}
```

---

### 6. Guaranteed Cleanup - `when: always`

```yaml
destroy:
  when: always   # runs even if the terratest job fails
  needs:
    - job: git-diff
      artifacts: true
    - job: terratest
```

The destroy job uses `TestCleanup` which re-derives the same module list and resource prefix, then retries destroy up to 5 times with 10-second backoff. This guarantees no AWS resources survive a failed test run.

---

## Repository Structure

```
.
├── .gitlab-ci.yml              # Full 4-stage pipeline definition
├── infra/
│   └── dev/
│       ├── aws_ec2/            # Terragrunt config for EC2 module
│       │   └── terragrunt.hcl
│       └── aws_secretsmanager/ # Terragrunt config for Secrets Manager
│           └── terragrunt.hcl
├── modules/
│   ├── aws_ec2/                # Reusable Terraform EC2 module
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   └── aws_secretsmanager/     # Reusable Terraform Secrets Manager module
│       ├── main.tf
│       ├── variables.tf
│       └── outputs.tf
└── test/
    ├── go.mod
    ├── terragrunt_test.go      # TestChangedModules - deploy + assert
    └── cleanup_test.go         # TestCleanup - destroy only
```

---

## Setup Guide

### Step 1 - GitLab CI/CD Variables

| Variable | Value | Masked | Protected |
|---|---|---|---|
| `AWS_ROLE_ARN` | `arn:aws:iam::<account-id>:role/GitLabTerratestRole` | ✅ | ✅ |
| `AWS_REGION` | `us-east-1` | ❌ | ❌ |
| `TF_VERSION` | `1.14.8` | ❌ | ❌ |
| `TG_VERSION` | `1.0.0` | ❌ | ❌ |

### Step 2 - AWS OIDC Provider

```bash
# Create the GitLab OIDC identity provider
aws iam create-open-id-connect-provider \
  --url https://gitlab.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list <gitlab-thumbprint>

# Create the IAM role trust policy
cat > trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::${AWS_ACCOUNT_ID}:oidc-provider/gitlab.com"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringLike": {
        "gitlab.com:sub": "project_path:<your-group>/<your-repo>:ref_type:branch:ref:*"
      }
    }
  }]
}
EOF

aws iam create-role \
  --role-name GitLabTerratestRole \
  --assume-role-policy-document file://trust-policy.json

aws iam attach-role-policy \
  --role-name GitLabTerratestRole \
  --policy-arn arn:aws:iam::aws:policy/PowerUserAccess
```

### Step 3 - Initialize Go Module

```bash
cd test
go mod init github.com/<your-org>/<your-repo>
go get github.com/gruntwork-io/terratest@v0.56.0
go get github.com/stretchr/testify@v1.10.0
```

### Step 4 - Deploy

```bash
git add .gitlab-ci.yml test/ modules/ infra/
git commit -m "feat: dynamic terratest pipeline with module auto-discovery"
git push origin feature/your-branch
# Open a Merge Request — the pipeline starts automatically
```

---

## Extending the Pipeline

### Adding a New Module (e.g. `aws_rds`)

1. Create `modules/aws_rds/` with your Terraform code and an `outputs.tf` that exposes testable values.
2. Create `infra/dev/aws_rds/terragrunt.hcl` pointing at the module.
3. *(Optional)* Add assertions in `test/terragrunt_test.go`:

```go
case "aws_rds":
    assertRDS(t, opts)

// ...

func assertRDS(t *testing.T, opts *terragrunt.Options) {
    endpoint := terragrunt.Output(t, opts, "db_endpoint")
    assert.NotEmpty(t, endpoint)
    assert.Contains(t, endpoint, ".rds.amazonaws.com")
}
```

That's it. The git-diff regex picks up any file change under `modules/aws_rds/` or `infra/dev/aws_rds/` on the next MR — no pipeline edits needed.

---

## Tech Stack

| Tool | Version | Role |
|---|---|---|
| [Terratest](https://terratest.gruntwork.io/) | v0.56.0 | Go testing framework for real AWS infra |
| [Terragrunt](https://terragrunt.gruntwork.io/) | v1.0.0 | DRY Terraform wrapper, `run-all` orchestration |
| [Terraform](https://www.terraform.io/) | v1.14.8 | Infrastructure provisioning |
| [GitLab CI](https://docs.gitlab.com/ee/ci/) | — | Pipeline orchestration, OIDC token issuance |
| [AWS OIDC](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html) | — | Keyless, short-lived credential federation |
| Go | 1.24 | Test runner language |

---

## Author

Built as a demonstration of production-grade infrastructure testing practices:
- Zero standing IAM credentials
- Parallel test isolation with unique resource prefixes
- Self-healing cleanup regardless of test outcome
- Fully dynamic - new modules require zero pipeline changes

## You can see on this directory the .gitlab-ci.yaml for reference.
