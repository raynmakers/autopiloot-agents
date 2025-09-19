# Comprehensive Security Pipeline

Run complete security tool chain with proper sequencing:

## Phase 1: Static Analysis (Parallel)

### SonarQube Analysis

```bash
sonar-scanner -Dsonar.projectKey=$PROJECT_KEY
```

### Semgrep High-Confidence Rules

```bash
semgrep --config=auto --severity=ERROR --no-rewrite-rule-ids
semgrep --config=.semgrep/security-rules.yml
```

### Custom Security Pattern Detection

Review code for:

- SQL injection patterns
- XSS vulnerabilities
- Hardcoded secrets
- Weak cryptographic implementations

## Phase 2: Dependency Analysis

### Vulnerability Scanning

```bash
# Snyk vulnerability scan
snyk test --severity-threshold=high

# OWASP Dependency Check
dependency-check --project "$PROJECT_NAME" --scan . --format JSON

# License compliance check
licensee detect --confidence 90
```

### Results Analysis

- Prioritize vulnerabilities by CVSS score
- Check for known exploits in the wild
- Assess upgrade path complexity

## Phase 3: Infrastructure as Code Security

### Terraform Security Scanning

```bash
tfsec . --format json
```

### Multi-Framework Security Check

```bash
checkov -d . --framework terraform,cloudformation,kubernetes
```

### Cloud Configuration Audit

```bash
prowler aws --services s3,iam,ec2,rds
```

## Phase 4: Container Security

### Container Image Scanning

```bash
# Trivy container scan
trivy image --severity HIGH,CRITICAL $IMAGE_NAME

# Dockerfile best practices
hadolint Dockerfile

# Base image vulnerabilities
docker scout cves $IMAGE_NAME
```

## Results Aggregation

Generate consolidated security report:

1. Aggregate results from all tools
2. Deduplicate findings across tools
3. Prioritize by CVSS score + business impact
4. Create executive summary with risk levels
5. Provide specific remediation steps for each finding

Track pipeline execution time and optimize for <10 minute total runtime.
