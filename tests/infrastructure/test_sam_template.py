"""Tests for SAM template validation.

These tests validate the SAM template structure before deployment,
catching configuration errors early in the development cycle.
"""

import yaml
import pytest
from pathlib import Path


# Custom YAML loader that handles CloudFormation intrinsic functions
class CloudFormationLoader(yaml.SafeLoader):
    """YAML loader that understands CloudFormation intrinsic functions."""


def _cfn_constructor(loader, node):
    """Convert CloudFormation intrinsic functions to dicts."""
    tag = node.tag[1:]  # Remove the leading '!'
    if isinstance(node, yaml.ScalarNode):
        return {tag: loader.construct_scalar(node)}
    elif isinstance(node, yaml.SequenceNode):
        return {tag: loader.construct_sequence(node)}
    elif isinstance(node, yaml.MappingNode):
        return {tag: loader.construct_mapping(node)}


# Register CloudFormation tags
for tag in ["Ref", "Sub", "GetAtt", "If", "Equals", "And", "Or", "Not"]:
    CloudFormationLoader.add_constructor(f"!{tag}", _cfn_constructor)


@pytest.fixture
def sam_template():
    """Load and parse the SAM template."""
    template_path = Path(__file__).parent.parent.parent / "template.yaml"
    with open(template_path) as f:
        return yaml.load(f, Loader=CloudFormationLoader)


class TestSAMTemplateStructure:
    """Tests for basic SAM template structure."""

    def test_template_has_aws_version(self, sam_template):
        """SAM template must have AWSTemplateFormatVersion."""
        assert "AWSTemplateFormatVersion" in sam_template
        assert sam_template["AWSTemplateFormatVersion"] == "2010-09-09"

    def test_template_has_sam_transform(self, sam_template):
        """SAM template must have the SAM transform."""
        assert "Transform" in sam_template
        assert sam_template["Transform"] == "AWS::Serverless-2016-10-31"

    def test_template_has_resources(self, sam_template):
        """SAM template must have Resources section."""
        assert "Resources" in sam_template

    def test_lambda_function_exists(self, sam_template):
        """Template must define the Guardian Lambda function."""
        resources = sam_template["Resources"]
        assert "GuardianStreamFunction" in resources
        func = resources["GuardianStreamFunction"]
        assert func["Type"] == "AWS::Serverless::Function"


class TestLambdaConfiguration:
    """Tests for Lambda function configuration."""

    def test_runtime_is_python313(self, sam_template):
        """Lambda must use Python 3.13 runtime."""
        func = sam_template["Resources"]["GuardianStreamFunction"]
        props = func["Properties"]
        assert props["Runtime"] == "python3.13"

    def test_handler_path_correct(self, sam_template):
        """Handler must point to correct entry point."""
        func = sam_template["Resources"]["GuardianStreamFunction"]
        props = func["Properties"]
        assert props["Handler"] == "guardian_stream.handler.handler"

    def test_timeout_is_reasonable(self, sam_template):
        """Timeout should be 30 seconds for API calls."""
        func = sam_template["Resources"]["GuardianStreamFunction"]
        props = func["Properties"]
        assert props["Timeout"] == 30

    def test_memory_is_adequate(self, sam_template):
        """Memory should be 256MB (sufficient for httpx + pydantic)."""
        func = sam_template["Resources"]["GuardianStreamFunction"]
        props = func["Properties"]
        assert props["MemorySize"] == 256

    def test_code_uri_points_to_src(self, sam_template):
        """CodeUri should point to src/ directory."""
        func = sam_template["Resources"]["GuardianStreamFunction"]
        props = func["Properties"]
        assert props["CodeUri"] == "src/"


class TestEnvironmentVariables:
    """Tests for required environment variables."""

    def test_guardian_secret_name_configured(self, sam_template):
        """GUARDIAN_API_KEY_SECRET_NAME must be configured."""
        func = sam_template["Resources"]["GuardianStreamFunction"]
        env_vars = func["Properties"]["Environment"]["Variables"]
        assert "GUARDIAN_API_KEY_SECRET_NAME" in env_vars

    def test_kinesis_stream_name_configured(self, sam_template):
        """KINESIS_STREAM_NAME must be configured."""
        func = sam_template["Resources"]["GuardianStreamFunction"]
        env_vars = func["Properties"]["Environment"]["Variables"]
        assert "KINESIS_STREAM_NAME" in env_vars


class TestIAMPolicies:
    """Tests for IAM policy configuration (least-privilege)."""

    def test_has_policies_defined(self, sam_template):
        """Lambda must have IAM policies defined."""
        func = sam_template["Resources"]["GuardianStreamFunction"]
        assert "Policies" in func["Properties"]
        assert len(func["Properties"]["Policies"]) > 0

    def test_secrets_manager_policy_exists(self, sam_template):
        """Lambda must have Secrets Manager read permission."""
        func = sam_template["Resources"]["GuardianStreamFunction"]
        policies = func["Properties"]["Policies"]

        # Check for secretsmanager:GetSecretValue in any policy
        policies_str = str(policies)
        assert "secretsmanager:GetSecretValue" in policies_str

    def test_kinesis_write_policy_exists(self, sam_template):
        """Lambda must have Kinesis write permission."""
        func = sam_template["Resources"]["GuardianStreamFunction"]
        policies = func["Properties"]["Policies"]

        # Check for kinesis:PutRecord in any policy
        policies_str = str(policies)
        assert "kinesis:PutRecord" in policies_str

    def test_no_wildcard_actions(self, sam_template):
        """IAM policies must not use wildcard actions."""
        func = sam_template["Resources"]["GuardianStreamFunction"]
        policies = func["Properties"]["Policies"]

        for policy in policies:
            if isinstance(policy, dict) and "Statement" in policy:
                for statement in policy["Statement"]:
                    actions = statement.get("Action", [])
                    if isinstance(actions, str):
                        actions = [actions]
                    for action in actions:
                        assert action != "*", "Wildcard action not allowed"
                        assert not action.endswith(":*"), f"Overly broad action: {action}"

    def test_no_admin_policies(self, sam_template):
        """Lambda must NOT have admin permissions."""
        func = sam_template["Resources"]["GuardianStreamFunction"]
        policies = func["Properties"]["Policies"]

        dangerous_policies = ["AdministratorAccess", "PowerUserAccess"]
        policies_str = str(policies)
        for dangerous in dangerous_policies:
            assert dangerous not in policies_str, f"Dangerous policy found: {dangerous}"


class TestSecurityBestPractices:
    """Tests for security best practices."""

    def test_no_hardcoded_secrets(self, sam_template):
        """Template must not contain hardcoded secrets."""
        template_str = yaml.dump(sam_template).lower()

        # Check for common secret patterns (excluding parameter references)
        secret_patterns = ["api-key=", "password=", "secret="]
        for pattern in secret_patterns:
            assert pattern not in template_str, f"Possible hardcoded secret: {pattern}"

    def test_resources_are_scoped(self, sam_template):
        """IAM resources should be scoped, not wildcard."""
        func = sam_template["Resources"]["GuardianStreamFunction"]
        policies = func["Properties"]["Policies"]

        for policy in policies:
            if isinstance(policy, dict) and "Statement" in policy:
                for statement in policy["Statement"]:
                    resource = statement.get("Resource", "")
                    # Allow !Sub references (they appear as dicts in parsed YAML)
                    if isinstance(resource, str):
                        assert resource != "*", "Wildcard resource not allowed"


class TestParameters:
    """Tests for SAM template parameters."""

    def test_has_parameters_section(self, sam_template):
        """Template should have Parameters for configuration."""
        assert "Parameters" in sam_template

    def test_environment_parameter_exists(self, sam_template):
        """Environment parameter should exist for dev/staging/prod."""
        params = sam_template["Parameters"]
        assert "Environment" in params

    def test_environment_has_allowed_values(self, sam_template):
        """Environment parameter should restrict to valid values."""
        env_param = sam_template["Parameters"]["Environment"]
        assert "AllowedValues" in env_param
        allowed = env_param["AllowedValues"]
        assert "dev" in allowed
        assert "prod" in allowed
