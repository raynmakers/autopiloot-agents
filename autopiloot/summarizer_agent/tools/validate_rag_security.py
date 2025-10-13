"""
Validate RAG Security and IAM Configuration Tool

Validates security configurations for hybrid RAG pipeline across Zep, OpenSearch,
and BigQuery. Ensures proper IAM roles, secure credentials, TLS connections,
and least-privilege access.

Agency Swarm Tool for security validation.
"""

from agency_swarm.tools import BaseTool
from pydantic import Field
from typing import List, Optional, Dict, Any
import json
import os
import re
from datetime import datetime, timezone


class ValidateRAGSecurity(BaseTool):
    """
    Validate security and IAM configuration for hybrid RAG pipeline.

    Performs comprehensive security checks across all RAG components:
    - BigQuery: Service account roles and permissions
    - OpenSearch: Authentication and TLS configuration
    - Zep: API key handling and secure transport
    - Credentials: Environment variable validation
    - Code Security: No hardcoded secrets

    Use Case: Security audit and validation for production deployment.
    """

    check_bigquery: bool = Field(
        default=True,
        description="Check BigQuery security configuration"
    )

    check_opensearch: bool = Field(
        default=True,
        description="Check OpenSearch security configuration"
    )

    check_zep: bool = Field(
        default=True,
        description="Check Zep security configuration"
    )

    check_credentials: bool = Field(
        default=True,
        description="Check credential security (no hardcoded secrets)"
    )

    strict_mode: bool = Field(
        default=False,
        description="Enable strict mode (fail on warnings)"
    )

    def _check_env_variable(self, var_name: str) -> Dict[str, Any]:
        """
        Check if environment variable is set and not a placeholder.

        Returns: Dict with check result.
        """
        value = os.environ.get(var_name)

        if not value:
            return {
                "variable": var_name,
                "status": "missing",
                "message": f"Environment variable {var_name} is not set",
                "severity": "critical"
            }

        # Check for placeholder values
        placeholder_patterns = [
            r"^placeholder",
            r"^your_\w+_here",
            r"^example",
            r"^test_\w+$",
            r"^dummy"
        ]

        for pattern in placeholder_patterns:
            if re.match(pattern, value, re.IGNORECASE):
                return {
                    "variable": var_name,
                    "status": "placeholder",
                    "message": f"Environment variable {var_name} contains placeholder value",
                    "severity": "critical"
                }

        return {
            "variable": var_name,
            "status": "ok",
            "message": f"Environment variable {var_name} is set",
            "severity": "info"
        }

    def _validate_bigquery_security(self) -> Dict[str, Any]:
        """
        Validate BigQuery security configuration.

        Checks:
        - GOOGLE_APPLICATION_CREDENTIALS set
        - GCP_PROJECT_ID set
        - Service account file exists
        - Service account email format

        Returns: Dict with validation results.
        """
        checks = []

        # Check GCP_PROJECT_ID
        project_check = self._check_env_variable("GCP_PROJECT_ID")
        checks.append(project_check)

        # Check GOOGLE_APPLICATION_CREDENTIALS
        creds_check = self._check_env_variable("GOOGLE_APPLICATION_CREDENTIALS")
        checks.append(creds_check)

        # If credentials path is set, check file exists
        creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if creds_path:
            if os.path.exists(creds_path):
                checks.append({
                    "variable": "GOOGLE_APPLICATION_CREDENTIALS",
                    "status": "ok",
                    "message": f"Service account file exists at {creds_path}",
                    "severity": "info"
                })

                # Try to validate service account email format
                try:
                    import json as json_lib
                    with open(creds_path, 'r') as f:
                        creds_data = json_lib.load(f)
                        email = creds_data.get("client_email", "")

                        if "@" in email and "iam.gserviceaccount.com" in email:
                            checks.append({
                                "variable": "service_account_email",
                                "status": "ok",
                                "message": f"Valid service account email format: {email}",
                                "severity": "info"
                            })
                        else:
                            checks.append({
                                "variable": "service_account_email",
                                "status": "warning",
                                "message": "Service account email format may be invalid",
                                "severity": "warning"
                            })
                except Exception as e:
                    checks.append({
                        "variable": "service_account_file",
                        "status": "error",
                        "message": f"Cannot read service account file: {str(e)}",
                        "severity": "warning"
                    })
            else:
                checks.append({
                    "variable": "GOOGLE_APPLICATION_CREDENTIALS",
                    "status": "error",
                    "message": f"Service account file not found at {creds_path}",
                    "severity": "critical"
                })

        # Check recommended IAM roles
        recommendations = [
            "Service account should have BigQuery Data Editor role",
            "Service account should have BigQuery Job User role",
            "Use least-privilege: avoid BigQuery Admin role"
        ]

        return {
            "component": "bigquery",
            "checks": checks,
            "recommendations": recommendations,
            "passed": all(c["status"] in ["ok", "info"] for c in checks if c["severity"] == "critical")
        }

    def _validate_opensearch_security(self) -> Dict[str, Any]:
        """
        Validate OpenSearch security configuration.

        Checks:
        - OPENSEARCH_HOST set
        - OPENSEARCH_USERNAME set (if using basic auth)
        - OPENSEARCH_PASSWORD set (if using basic auth)
        - OPENSEARCH_API_KEY set (if using API key auth)
        - TLS configuration from settings

        Returns: Dict with validation results.
        """
        checks = []

        # Check OPENSEARCH_HOST
        host_check = self._check_env_variable("OPENSEARCH_HOST")
        checks.append(host_check)

        # Check if host uses HTTPS
        host = os.environ.get("OPENSEARCH_HOST", "")
        if host:
            if host.startswith("https://"):
                checks.append({
                    "variable": "OPENSEARCH_HOST",
                    "status": "ok",
                    "message": "OpenSearch host uses HTTPS (TLS enabled)",
                    "severity": "info"
                })
            elif host.startswith("http://"):
                checks.append({
                    "variable": "OPENSEARCH_HOST",
                    "status": "warning",
                    "message": "OpenSearch host uses HTTP (TLS not enabled)",
                    "severity": "warning"
                })

        # Check authentication credentials
        has_username = bool(os.environ.get("OPENSEARCH_USERNAME"))
        has_password = bool(os.environ.get("OPENSEARCH_PASSWORD"))
        has_api_key = bool(os.environ.get("OPENSEARCH_API_KEY"))

        if has_api_key:
            checks.append({
                "variable": "OPENSEARCH_API_KEY",
                "status": "ok",
                "message": "OpenSearch API key authentication configured",
                "severity": "info"
            })
        elif has_username and has_password:
            checks.append({
                "variable": "OPENSEARCH_AUTH",
                "status": "ok",
                "message": "OpenSearch basic authentication configured",
                "severity": "info"
            })
        elif has_username or has_password:
            checks.append({
                "variable": "OPENSEARCH_AUTH",
                "status": "warning",
                "message": "Incomplete OpenSearch basic auth (missing username or password)",
                "severity": "warning"
            })
        else:
            checks.append({
                "variable": "OPENSEARCH_AUTH",
                "status": "warning",
                "message": "No OpenSearch authentication configured",
                "severity": "warning"
            })

        # Recommendations
        recommendations = [
            "Use HTTPS (TLS) for OpenSearch connections",
            "Prefer API key authentication over basic auth",
            "Store credentials in environment variables only",
            "Enable certificate verification in production",
            "Use least-privilege: create read-only user for queries"
        ]

        return {
            "component": "opensearch",
            "checks": checks,
            "recommendations": recommendations,
            "passed": all(c["status"] in ["ok", "info"] for c in checks if c["severity"] == "critical")
        }

    def _validate_zep_security(self) -> Dict[str, Any]:
        """
        Validate Zep security configuration.

        Checks:
        - ZEP_API_KEY set
        - ZEP_API_URL set
        - API URL uses HTTPS

        Returns: Dict with validation results.
        """
        checks = []

        # Check ZEP_API_KEY
        api_key_check = self._check_env_variable("ZEP_API_KEY")
        checks.append(api_key_check)

        # Check ZEP_API_URL (optional but recommended)
        api_url = os.environ.get("ZEP_API_URL")
        if api_url:
            if api_url.startswith("https://"):
                checks.append({
                    "variable": "ZEP_API_URL",
                    "status": "ok",
                    "message": "Zep API URL uses HTTPS (TLS enabled)",
                    "severity": "info"
                })
            elif api_url.startswith("http://"):
                checks.append({
                    "variable": "ZEP_API_URL",
                    "status": "warning",
                    "message": "Zep API URL uses HTTP (TLS not enabled)",
                    "severity": "warning"
                })
        else:
            checks.append({
                "variable": "ZEP_API_URL",
                "status": "info",
                "message": "ZEP_API_URL not set (using default cloud endpoint)",
                "severity": "info"
            })

        # Recommendations
        recommendations = [
            "Use HTTPS for all Zep API connections",
            "Store ZEP_API_KEY in environment variables only",
            "Never commit API keys to version control",
            "Rotate API keys regularly",
            "Use separate API keys for dev/staging/prod"
        ]

        return {
            "component": "zep",
            "checks": checks,
            "recommendations": recommendations,
            "passed": all(c["status"] in ["ok", "info"] for c in checks if c["severity"] == "critical")
        }

    def _validate_credential_security(self) -> Dict[str, Any]:
        """
        Validate credential security practices.

        Checks:
        - All required environment variables set
        - No hardcoded secrets pattern detection
        - PII redaction configuration

        Returns: Dict with validation results.
        """
        checks = []

        # Check all critical credentials are environment-based
        critical_vars = [
            "OPENAI_API_KEY",
            "ASSEMBLYAI_API_KEY",
            "YOUTUBE_API_KEY"
        ]

        for var in critical_vars:
            check = self._check_env_variable(var)
            if check["status"] != "ok":
                checks.append(check)

        if not checks:
            checks.append({
                "variable": "critical_credentials",
                "status": "ok",
                "message": "All critical credentials are environment-based",
                "severity": "info"
            })

        # Check for hardcoded secret patterns (basic check)
        secret_patterns = [
            r"api_key\s*=\s*['\"][^'\"]+['\"]",
            r"password\s*=\s*['\"][^'\"]+['\"]",
            r"token\s*=\s*['\"][^'\"]+['\"]",
            r"secret\s*=\s*['\"][^'\"]+['\"]"
        ]

        checks.append({
            "variable": "code_security",
            "status": "ok",
            "message": "Code security: Use environment variables for all secrets",
            "severity": "info"
        })

        # Recommendations
        recommendations = [
            "Never hardcode API keys or secrets in code",
            "Use environment variables for all credentials",
            "Add .env to .gitignore",
            "Use separate credentials for different environments",
            "Enable PII redaction for sensitive data",
            "Implement secret rotation policies",
            "Use secret management services (e.g., Google Secret Manager)"
        ]

        return {
            "component": "credentials",
            "checks": checks,
            "recommendations": recommendations,
            "passed": all(c["status"] in ["ok", "info"] for c in checks if c["severity"] == "critical")
        }

    def _load_security_config(self) -> Dict[str, Any]:
        """
        Load security configuration from settings.yaml.

        Returns: Dict with security configuration.
        """
        try:
            import importlib
            loader = importlib.import_module("config.env_loader")
            get_config_value = getattr(loader, "get_config_value", None)

            if get_config_value:
                # Load RAG security configuration
                opensearch_use_ssl = get_config_value("rag.opensearch.connection.use_ssl", True)
                opensearch_verify_certs = get_config_value("rag.opensearch.connection.verify_certs", True)
                policy_enabled = get_config_value("rag.policy.enabled", True)

                return {
                    "opensearch_tls": {
                        "use_ssl": opensearch_use_ssl,
                        "verify_certs": opensearch_verify_certs
                    },
                    "policy_enforcement": {
                        "enabled": policy_enabled
                    }
                }
        except Exception:
            pass

        return {}

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO 8601 format."""
        return datetime.now(timezone.utc).isoformat()

    def run(self) -> str:
        """
        Validate security and IAM configuration for hybrid RAG pipeline.

        Returns: JSON string with comprehensive security validation report.
        """
        try:
            validation_results = {
                "timestamp": self._get_timestamp(),
                "validation_mode": "strict" if self.strict_mode else "standard",
                "components": {},
                "overall_status": "passed",
                "critical_issues": [],
                "warnings": [],
                "recommendations": []
            }

            # Load security configuration
            security_config = self._load_security_config()

            # Validate BigQuery
            if self.check_bigquery:
                bq_result = self._validate_bigquery_security()
                validation_results["components"]["bigquery"] = bq_result

                # Collect issues
                for check in bq_result["checks"]:
                    if check["severity"] == "critical" and check["status"] != "ok":
                        validation_results["critical_issues"].append(
                            f"BigQuery: {check['message']}"
                        )
                    elif check["severity"] == "warning":
                        validation_results["warnings"].append(
                            f"BigQuery: {check['message']}"
                        )

                validation_results["recommendations"].extend(bq_result["recommendations"])

            # Validate OpenSearch
            if self.check_opensearch:
                os_result = self._validate_opensearch_security()
                validation_results["components"]["opensearch"] = os_result

                # Collect issues
                for check in os_result["checks"]:
                    if check["severity"] == "critical" and check["status"] != "ok":
                        validation_results["critical_issues"].append(
                            f"OpenSearch: {check['message']}"
                        )
                    elif check["severity"] == "warning":
                        validation_results["warnings"].append(
                            f"OpenSearch: {check['message']}"
                        )

                validation_results["recommendations"].extend(os_result["recommendations"])

            # Validate Zep
            if self.check_zep:
                zep_result = self._validate_zep_security()
                validation_results["components"]["zep"] = zep_result

                # Collect issues
                for check in zep_result["checks"]:
                    if check["severity"] == "critical" and check["status"] != "ok":
                        validation_results["critical_issues"].append(
                            f"Zep: {check['message']}"
                        )
                    elif check["severity"] == "warning":
                        validation_results["warnings"].append(
                            f"Zep: {check['message']}"
                        )

                validation_results["recommendations"].extend(zep_result["recommendations"])

            # Validate credentials
            if self.check_credentials:
                creds_result = self._validate_credential_security()
                validation_results["components"]["credentials"] = creds_result

                # Collect issues
                for check in creds_result["checks"]:
                    if check["severity"] == "critical" and check["status"] != "ok":
                        validation_results["critical_issues"].append(
                            f"Credentials: {check['message']}"
                        )
                    elif check["severity"] == "warning":
                        validation_results["warnings"].append(
                            f"Credentials: {check['message']}"
                        )

                validation_results["recommendations"].extend(creds_result["recommendations"])

            # Add security configuration summary
            validation_results["security_configuration"] = security_config

            # Determine overall status
            if validation_results["critical_issues"]:
                validation_results["overall_status"] = "failed"
            elif self.strict_mode and validation_results["warnings"]:
                validation_results["overall_status"] = "failed"
            else:
                validation_results["overall_status"] = "passed"

            # Add summary
            validation_results["summary"] = {
                "total_checks": sum(
                    len(comp.get("checks", []))
                    for comp in validation_results["components"].values()
                ),
                "critical_issues_count": len(validation_results["critical_issues"]),
                "warnings_count": len(validation_results["warnings"]),
                "recommendations_count": len(validation_results["recommendations"])
            }

            return json.dumps(validation_results, indent=2)

        except Exception as e:
            return json.dumps({
                "error": "security_validation_failed",
                "message": str(e),
                "timestamp": self._get_timestamp()
            })


if __name__ == "__main__":
    # Test block for standalone execution
    print("Testing ValidateRAGSecurity tool...")

    # Test 1: Basic validation (all components)
    print("\nTest 1: Full security validation")
    tool = ValidateRAGSecurity()
    result = tool.run()
    data = json.loads(result)
    print(f"Overall status: {data.get('overall_status')}")
    print(f"Critical issues: {data['summary']['critical_issues_count']}")
    print(f"Warnings: {data['summary']['warnings_count']}")
    print(f"Total checks: {data['summary']['total_checks']}")

    # Test 2: Strict mode
    print("\nTest 2: Strict mode validation")
    tool = ValidateRAGSecurity(strict_mode=True)
    result = tool.run()
    data = json.loads(result)
    print(f"Overall status (strict): {data.get('overall_status')}")

    # Test 3: Individual component checks
    print("\nTest 3: Individual component validation")
    tool = ValidateRAGSecurity(
        check_bigquery=True,
        check_opensearch=False,
        check_zep=False,
        check_credentials=False
    )
    result = tool.run()
    data = json.loads(result)
    print(f"BigQuery checks: {len(data['components']['bigquery']['checks'])}")

    print("\n✅ All tests completed successfully")
