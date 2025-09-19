# AI-Assisted Security Review (Human-Verified)

⚠️ **CRITICAL**: Research shows 39.33% of AI-generated code contains vulnerabilities.
All AI findings MUST be verified by security-trained humans.

## AI Analysis Phase

1. Use Claude for initial vulnerability detection
2. Apply chain-of-thought prompting for 18% better accuracy:
   - "Think step by step about potential attack vectors"
   - "Consider both obvious and subtle security implications"
   - "Validate each finding against OWASP/CWE classifications"

## Human Verification Phase

Review each AI finding for:

- **False Positives**: Is this actually exploitable?
- **Context Accuracy**: Does AI understand business logic?
- **Completeness**: What did AI miss?
- **Remediation Quality**: Are suggested fixes adequate?

## AI Blind Spots (Require Manual Review)

- Business logic flaws and authorization bypasses
- Race conditions and timing attacks
- Complex authentication edge cases
- Application-specific threat model violations
- Supply chain and dependency risks

Generate hybrid report: AI efficiency + human judgment accuracy.
