# Comprehensive Security Audit

Perform a complete security assessment of this codebase:

## Phase 1: Static Analysis

1. Run `/security-review` on all modified files
2. Check for hardcoded secrets: `git grep -i "password\|secret\|key\|token"`
3. Find potential SQL injection: Search for string concatenation in database queries
4. Identify XSS vulnerabilities: Look for unescaped user input in templates

## Phase 2: Dependency Analysis

1. Check for vulnerable npm packages: `npm audit`
2. Check for outdated packages: `npm outdated`
3. For Python: `safety check` or `pip-audit`
4. For Ruby: `bundle audit`

## Phase 3: Configuration Review

1. Check for exposed debug/development settings
2. Verify HTTPS enforcement
3. Review CORS configurations
4. Check authentication/session settings

## Phase 4: Business Logic Review

1. Analyze authorization flows for bypass opportunities
2. Check for race conditions in critical operations
3. Review privilege escalation paths
4. Verify input validation completeness

Generate a security report with prioritized findings and remediation steps.
