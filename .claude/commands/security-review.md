# Custom Security Review Command

Review this code focusing ONLY on:

## Critical Security Areas (OWASP Top 10 + CWE Top 25)

1. **Injection vulnerabilities** (SQL, XSS, Command Injection)
2. **Broken Authentication & Session Management**
3. **Broken Access Control** - verify authorization at every endpoint
4. **Cryptographic Failures** - check for weak algorithms, hardcoded secrets
5. **Security Misconfigurations** - default configs, exposed debug info
6. **Vulnerable Components** - outdated dependencies, known CVEs
7. **Business Logic Flaws** - authorization bypass, race conditions

## Code Patterns to Flag

- String concatenation in SQL contexts without parameterization
- Missing input validation on external data
- Hardcoded credentials, API keys, or secrets
- Missing authentication/authorization checks
- Weak cryptographic implementations (MD5, SHA1, DES)
- Insecure random number generation
- Path traversal vulnerabilities
- Missing CSRF protection

## Output Format

- **CRITICAL**: Immediate security risk requiring fix before merge
- **HIGH**: Significant vulnerability, fix within 24 hours
- **MEDIUM**: Potential security issue, fix within 1 week
- **INFO**: Security improvement suggestion

Be concise. Focus on exploitable vulnerabilities, not theoretical issues.
Provide specific remediation steps for each finding.
