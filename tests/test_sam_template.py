"""Tests for the SAM infrastructure template.

Validates that infra/approval-portal/template.yaml is syntactically
correct and contains all required resources, parameters, and outputs.
"""

from pathlib import Path

import yaml

TEMPLATE_PATH = (
    Path(__file__).resolve().parent.parent / "infra" / "approval-portal" / "template.yaml"
)

# ---------------------------------------------------------------------------
# CloudFormation-aware YAML loader
# ---------------------------------------------------------------------------
_CFN_TAGS = [
    "!Sub", "!Ref", "!GetAtt", "!Select", "!Split",
    "!Join", "!If", "!Not", "!Equals", "!ImportValue",
]


class _CfnLoader(yaml.SafeLoader):
    """YAML loader that accepts CloudFormation intrinsic function tags."""


def _cfn_scalar(loader: yaml.SafeLoader, node: yaml.ScalarNode) -> str:
    return loader.construct_scalar(node)


def _cfn_sequence(loader: yaml.SafeLoader, node: yaml.SequenceNode) -> list:
    return loader.construct_sequence(node)


for _tag in _CFN_TAGS:
    _CfnLoader.add_constructor(_tag, _cfn_scalar)
    _CfnLoader.add_multi_constructor(_tag, lambda loader, suffix, node: _cfn_scalar(loader, node))


# Also handle sequence forms like !Sub [template, {key: val}]
for _tag in _CFN_TAGS:
    _CfnLoader.add_constructor(
        _tag,
        lambda loader, node: (
            _cfn_scalar(loader, node)
            if isinstance(node, yaml.ScalarNode)
            else _cfn_sequence(loader, node)
        ),
    )


def _load_template() -> dict:
    """Load and parse the SAM template with CloudFormation tag support."""
    return yaml.load(TEMPLATE_PATH.read_text(), Loader=_CfnLoader)  # noqa: S506


# ---------------------------------------------------------------------------
# 1. YAML syntax validation
# ---------------------------------------------------------------------------
class TestYamlSyntax:
    """Verify the template is valid YAML."""

    def test_template_file_exists(self):
        assert TEMPLATE_PATH.exists(), f"Template not found: {TEMPLATE_PATH}"

    def test_yaml_parses_successfully(self):
        template = _load_template()
        assert isinstance(template, dict)

    def test_has_aws_template_format_version(self):
        template = _load_template()
        assert template.get("AWSTemplateFormatVersion") == "2010-09-09"

    def test_has_transform(self):
        template = _load_template()
        assert template.get("Transform") == "AWS::Serverless-2016-10-31"


# ---------------------------------------------------------------------------
# 2. Lambda functions
# ---------------------------------------------------------------------------
class TestLambdaFunctions:
    """Verify all 3 Lambda functions are defined."""

    def test_approval_processor_function_exists(self):
        template = _load_template()
        resources = template["Resources"]
        assert "ApprovalProcessorFunction" in resources

    def test_approval_processor_handler(self):
        template = _load_template()
        props = template["Resources"]["ApprovalProcessorFunction"]["Properties"]
        assert props["Handler"] == "lambdas/approval_processor/handler.process_webhook"

    def test_approval_processor_memory(self):
        template = _load_template()
        props = template["Resources"]["ApprovalProcessorFunction"]["Properties"]
        assert props["MemorySize"] == 512

    def test_approval_processor_timeout(self):
        template = _load_template()
        props = template["Resources"]["ApprovalProcessorFunction"]["Properties"]
        assert props["Timeout"] == 300

    def test_portal_api_function_exists(self):
        template = _load_template()
        resources = template["Resources"]
        assert "PortalApiFunction" in resources

    def test_portal_api_handler(self):
        template = _load_template()
        props = template["Resources"]["PortalApiFunction"]["Properties"]
        assert props["Handler"] == "lambdas/portal_api/handler.api_handler"

    def test_portal_api_memory(self):
        template = _load_template()
        props = template["Resources"]["PortalApiFunction"]["Properties"]
        assert props["MemorySize"] == 256

    def test_portal_api_timeout(self):
        template = _load_template()
        props = template["Resources"]["PortalApiFunction"]["Properties"]
        assert props["Timeout"] == 30

    def test_approval_reminder_function_exists(self):
        template = _load_template()
        resources = template["Resources"]
        assert "ApprovalReminderFunction" in resources

    def test_approval_reminder_handler(self):
        template = _load_template()
        props = template["Resources"]["ApprovalReminderFunction"]["Properties"]
        assert props["Handler"] == "lambdas/approval_reminder/handler.check_reminders"

    def test_approval_reminder_memory(self):
        template = _load_template()
        props = template["Resources"]["ApprovalReminderFunction"]["Properties"]
        assert props["MemorySize"] == 256

    def test_approval_reminder_timeout(self):
        template = _load_template()
        props = template["Resources"]["ApprovalReminderFunction"]["Properties"]
        assert props["Timeout"] == 60

    def test_all_functions_use_python313(self):
        template = _load_template()
        global_runtime = template.get("Globals", {}).get("Function", {}).get("Runtime")
        assert global_runtime == "python3.13"

    def test_global_vpc_config_exists(self):
        template = _load_template()
        vpc_config = template.get("Globals", {}).get("Function", {}).get("VpcConfig")
        assert vpc_config is not None, "Globals.Function.VpcConfig is required for RDS access"
        assert "SecurityGroupIds" in vpc_config
        assert "SubnetIds" in vpc_config

    def test_all_lambda_functions_present(self):
        template = _load_template()
        resources = template["Resources"]
        lambda_functions = [
            name
            for name, res in resources.items()
            if res.get("Type") == "AWS::Serverless::Function"
        ]
        assert len(lambda_functions) == 4
        assert set(lambda_functions) == {
            "ApprovalProcessorFunction",
            "PortalApiFunction",
            "ApprovalReminderFunction",
            "ReportGeneratorFunction",
        }


# ---------------------------------------------------------------------------
# 3. S3 Buckets
# ---------------------------------------------------------------------------
class TestS3Buckets:
    """Verify S3 buckets exist with correct configurations."""

    def test_media_bucket_exists(self):
        template = _load_template()
        assert "MediaBucket" in template["Resources"]

    def test_media_bucket_type(self):
        template = _load_template()
        assert template["Resources"]["MediaBucket"]["Type"] == "AWS::S3::Bucket"

    def test_media_bucket_versioning_enabled(self):
        template = _load_template()
        props = template["Resources"]["MediaBucket"]["Properties"]
        assert props["VersioningConfiguration"]["Status"] == "Enabled"

    def test_media_bucket_lifecycle_ia_90_days(self):
        template = _load_template()
        props = template["Resources"]["MediaBucket"]["Properties"]
        rules = props["LifecycleConfiguration"]["Rules"]
        assert any(
            t["StorageClass"] == "STANDARD_IA" and t["TransitionInDays"] == 90
            for rule in rules
            for t in rule.get("Transitions", [])
        )

    def test_media_bucket_private(self):
        template = _load_template()
        props = template["Resources"]["MediaBucket"]["Properties"]
        block = props["PublicAccessBlockConfiguration"]
        assert block["BlockPublicAcls"] is True
        assert block["BlockPublicPolicy"] is True
        assert block["IgnorePublicAcls"] is True
        assert block["RestrictPublicBuckets"] is True

    def test_portal_bucket_exists(self):
        template = _load_template()
        assert "PortalBucket" in template["Resources"]

    def test_portal_bucket_website_hosting(self):
        template = _load_template()
        props = template["Resources"]["PortalBucket"]["Properties"]
        website_config = props["WebsiteConfiguration"]
        assert website_config["IndexDocument"] == "index.html"


# ---------------------------------------------------------------------------
# 4. EventBridge rules
# ---------------------------------------------------------------------------
class TestEventBridge:
    """Verify EventBridge event bus and rules."""

    def test_approval_event_bus_exists(self):
        template = _load_template()
        assert "ApprovalEventBus" in template["Resources"]

    def test_event_bus_type(self):
        template = _load_template()
        assert template["Resources"]["ApprovalEventBus"]["Type"] == "AWS::Events::EventBus"

    def test_processor_rule_exists(self):
        template = _load_template()
        assert "ProcessorRule" in template["Resources"]

    def test_processor_rule_has_event_pattern(self):
        """ProcessorRule should have an EventPattern with a status filter."""
        template = _load_template()
        props = template["Resources"]["ProcessorRule"]["Properties"]
        pattern = props["EventPattern"]
        # The pattern must filter on detail.status (exact value may change)
        assert "status" in pattern["detail"]

    def test_reminder_schedule_rule_exists(self):
        template = _load_template()
        assert "ReminderScheduleRule" in template["Resources"]

    def test_reminder_schedule_is_daily_cron(self):
        template = _load_template()
        props = template["Resources"]["ReminderScheduleRule"]["Properties"]
        expr = props["ScheduleExpression"]
        assert "cron(" in expr
        # 12:00 UTC = 9:00 BRT
        assert expr.startswith("cron(0 12")

    def test_processor_rule_permission_exists(self):
        template = _load_template()
        assert "ProcessorRulePermission" in template["Resources"]

    def test_reminder_rule_permission_exists(self):
        template = _load_template()
        assert "ReminderRulePermission" in template["Resources"]


# ---------------------------------------------------------------------------
# 5. API Gateway
# ---------------------------------------------------------------------------
class TestApiGateway:
    """Verify API Gateway is defined with CORS."""

    def test_portal_api_exists(self):
        template = _load_template()
        assert "PortalApi" in template["Resources"]

    def test_portal_api_type(self):
        template = _load_template()
        assert template["Resources"]["PortalApi"]["Type"] == "AWS::Serverless::Api"

    def test_portal_api_has_cors(self):
        template = _load_template()
        props = template["Resources"]["PortalApi"]["Properties"]
        assert "Cors" in props

    def test_portal_api_cors_allows_post_and_get(self):
        template = _load_template()
        cors = template["Resources"]["PortalApi"]["Properties"]["Cors"]
        methods = cors["AllowMethods"]
        assert "GET" in methods
        assert "POST" in methods

    def test_portal_api_function_has_api_events(self):
        template = _load_template()
        events = template["Resources"]["PortalApiFunction"]["Properties"]["Events"]
        # Must have at least the required routes
        event_paths = [
            ev["Properties"]["Path"]
            for ev in events.values()
            if ev.get("Type") == "Api"
        ]
        assert "/api/auth/validate" in event_paths
        assert "/api/health" in event_paths
        assert "/api/assets/{assetId}" in event_paths
        assert "/api/assets/{assetId}/approve" in event_paths
        assert "/api/assets/{assetId}/request-changes" in event_paths
        assert "/api/assets/{assetId}/comments" in event_paths


# ---------------------------------------------------------------------------
# 6. CloudFront distribution
# ---------------------------------------------------------------------------
class TestCloudFront:
    """Verify CloudFront distribution exists."""

    def test_distribution_exists(self):
        template = _load_template()
        assert "PortalDistribution" in template["Resources"]

    def test_distribution_type(self):
        template = _load_template()
        assert (
            template["Resources"]["PortalDistribution"]["Type"]
            == "AWS::CloudFront::Distribution"
        )

    def test_distribution_has_s3_origin(self):
        template = _load_template()
        origins = (
            template["Resources"]["PortalDistribution"]["Properties"]
            ["DistributionConfig"]["Origins"]
        )
        origin_ids = [o["Id"] for o in origins]
        assert "S3Origin" in origin_ids

    def test_distribution_has_api_origin(self):
        template = _load_template()
        origins = (
            template["Resources"]["PortalDistribution"]["Properties"]
            ["DistributionConfig"]["Origins"]
        )
        origin_ids = [o["Id"] for o in origins]
        assert "ApiOrigin" in origin_ids

    def test_distribution_api_cache_behavior(self):
        template = _load_template()
        behaviors = (
            template["Resources"]["PortalDistribution"]["Properties"]
            ["DistributionConfig"]["CacheBehaviors"]
        )
        api_paths = [b["PathPattern"] for b in behaviors]
        assert "/api/*" in api_paths

    def test_oai_exists(self):
        template = _load_template()
        assert "PortalCloudFrontOAI" in template["Resources"]


# ---------------------------------------------------------------------------
# 7. Parameters
# ---------------------------------------------------------------------------
class TestParameters:
    """Verify all required parameters exist."""

    REQUIRED_PARAMS = [
        "Environment",
        "DatabaseUrl",
        "ClickupApiToken",
        "JwtSecret",
        "SesFromEmail",
        "PortalDomain",
        "ApiDomain",
        "AcmCertificateArn",
        "VpcSubnetIds",
        "VpcSecurityGroupId",
    ]

    def test_all_required_parameters_exist(self):
        template = _load_template()
        params = template.get("Parameters", {})
        for param_name in self.REQUIRED_PARAMS:
            assert param_name in params, f"Missing parameter: {param_name}"

    def test_environment_default_staging(self):
        template = _load_template()
        assert template["Parameters"]["Environment"]["Default"] == "staging"

    def test_database_url_no_echo(self):
        template = _load_template()
        assert template["Parameters"]["DatabaseUrl"].get("NoEcho") is True

    def test_clickup_api_token_no_echo(self):
        template = _load_template()
        assert template["Parameters"]["ClickupApiToken"].get("NoEcho") is True

    def test_jwt_secret_no_echo(self):
        template = _load_template()
        assert template["Parameters"]["JwtSecret"].get("NoEcho") is True

    def test_portal_domain_default(self):
        template = _load_template()
        assert template["Parameters"]["PortalDomain"]["Default"] == "approvals.example.com"

    def test_api_domain_default(self):
        template = _load_template()
        assert template["Parameters"]["ApiDomain"]["Default"] == "api-approvals.example.com"


# ---------------------------------------------------------------------------
# 8. Outputs
# ---------------------------------------------------------------------------
class TestOutputs:
    """Verify outputs are defined."""

    REQUIRED_OUTPUTS = [
        "ApiEndpoint",
        "PortalUrl",
        "MediaBucketName",
        "CloudFrontDistributionId",
    ]

    def test_all_required_outputs_exist(self):
        template = _load_template()
        outputs = template.get("Outputs", {})
        for output_name in self.REQUIRED_OUTPUTS:
            assert output_name in outputs, f"Missing output: {output_name}"

    def test_outputs_have_values(self):
        template = _load_template()
        outputs = template.get("Outputs", {})
        for output_name in self.REQUIRED_OUTPUTS:
            assert "Value" in outputs[output_name], f"Output {output_name} missing Value"

    def test_api_endpoint_output_has_description(self):
        template = _load_template()
        assert "Description" in template["Outputs"]["ApiEndpoint"]

    def test_portal_url_output_has_description(self):
        template = _load_template()
        assert "Description" in template["Outputs"]["PortalUrl"]
