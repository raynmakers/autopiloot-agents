# Supply Chain Security Review

Address the reality that 70-90% of modern applications are third-party code.

## Dependency Risk Assessment

### Risk Factors to Evaluate

- **Age Analysis**: Flag packages not updated in >2 years
- **Maintainer Analysis**: Check for single-maintainer packages
- **Download Statistics**: Verify legitimate package popularity
- **Typosquatting Detection**: Check for suspicious package names

## Language-Specific Security Commands

### Node.js Ecosystem

```bash
npm audit --audit-level=moderate
npm outdated --depth=0
npx lockfile-lint --path package-lock.json --validate-https
```

### Python Ecosystem

```bash
pip-audit --requirement requirements.txt
safety check --json
python -m pip list --outdated
```

### Java Ecosystem

```bash
mvn org.owasp:dependency-check-maven:check
mvn versions:display-dependency-updates
```

### Go Ecosystem

```bash
go list -u -m -json all | nancy sleuth
govulncheck ./...
```

## Supply Chain Security Policies

### Dependency Management Rules

- Pre-approve dependency additions through security review
- Pin exact versions, avoid ranges (^1.2.3 → 1.2.3)
- Monitor for suspicious package updates
- Maintain internal package mirrors for critical dependencies
- Implement software bill of materials (SBOM) generation

### Automated Monitoring

- Set up dependency update notifications
- Monitor for new vulnerabilities in existing dependencies
- Track license compliance changes
- Alert on unusual package behavior

## Risk Assessment Workflow

1. **New Dependency Review**

   - Verify package authenticity
   - Check maintainer reputation
   - Review package permissions/scope
   - Assess alternatives if high-risk

2. **Existing Dependency Audit**

   - Regular vulnerability scans
   - Update impact assessment
   - License compliance verification
   - Usage analysis and removal of unused packages

3. **Incident Response**
   - Rapid response for zero-day vulnerabilities
   - Rollback procedures for compromised packages
   - Alternative package evaluation
   - Emergency patching workflows

Generate comprehensive supply chain risk report with prioritized remediation steps and risk scores for each dependency.
