"""
_deploy_webtests.py -- Create App Insights standard webtests + metric alerts.

Called by setup-freshness-alert.sh. Uses the Azure Python SDK because the
az CLI doesn't support --content-match for standard webtests.

Requires: azure-identity, azure-mgmt-applicationinsights, azure-mgmt-monitor
"""

import argparse

from azure.identity import AzureCliCredential
from azure.mgmt.applicationinsights import ApplicationInsightsManagementClient
from azure.mgmt.applicationinsights.models import (
    WebTest,
    WebTestGeolocation,
    WebTestPropertiesRequest,
    WebTestPropertiesValidationRules,
    WebTestPropertiesValidationRulesContentValidation,
)
from azure.mgmt.monitor import MonitorManagementClient
from azure.mgmt.monitor.models import (
    MetricAlertAction,
    MetricAlertResource,
    MetricAlertSingleResourceMultipleMetricCriteria,
    MetricCriteria,
    MetricDimension,
)


def _build_xml(name: str, url: str, content_match: str) -> str:
    """Generate the Visual Studio TeamTest XML the API expects."""
    # Encode quotes for XML attributes
    cm_encoded = content_match.replace('"', "&quot;")
    return (
        f'<WebTest Name="{name}" Id="" Enabled="True" '
        f'CssProjectStructure="" CssIteration="" Timeout="30" '
        f'WorkItemIds="" '
        f'xmlns="http://microsoft.com/schemas/VisualStudio/TeamTest/2010">'
        f"<Items>"
        f'<Request Method="GET" Guid="" Version="1.0" Url="{url}" />'
        f"<ValidationRules>"
        f'<ContentMatch Validation="Content" '
        f'StringToMatch="{cm_encoded}" '
        f'IgnoreCase="False" PassIfTextFound="True" />'
        f"</ValidationRules>"
        f"</Items></WebTest>"
    )


def create_webtest(
    client: ApplicationInsightsManagementClient,
    rg: str,
    ai_id: str,
    name: str,
    url: str,
    content_match: str,
    locations: list[str],
    frequency: int,
    enabled: bool,
    description: str,
    severity_label: str = "warning",
) -> str:
    """Create a standard webtest with content-match. Returns the resource ID."""
    webtest = WebTest(
        location="westus2",
        tags={f"hidden-link:{ai_id}": "Resource", "ct-vuv": name},
        synthetic_monitor_id=name,
        web_test_name=name,
        description=description,
        enabled=enabled,
        frequency=frequency,
        timeout=30,
        kind="standard",
        web_test_kind="standard",
        retry_enabled=True,
        locations=[WebTestGeolocation(location=loc) for loc in locations],
        request=WebTestPropertiesRequest(
            request_url=url,
            http_verb="GET",
            follow_redirects=True,
            parse_dependent_requests=False,
        ),
        validation_rules=WebTestPropertiesValidationRules(
            content_validation=WebTestPropertiesValidationRulesContentValidation(
                content_match=content_match,
                ignore_case=False,
                pass_if_text_found=True,
            ),
            ssl_check=True,
            ssl_cert_remaining_lifetime_check=7,
            expected_http_status_code=200,
        ),
        configuration={"WebTest": _build_xml(name, url, content_match)},
    )
    result = client.web_tests.create_or_update(
        resource_group_name=rg,
        web_test_name=name,
        web_test_definition=webtest,
    )
    status = "ENABLED" if result.enabled else "DISABLED"
    cm = ""
    if result.validation_rules and result.validation_rules.content_validation:
        cm = f" content-match='{result.validation_rules.content_validation.content_match}'"
    print(f"  Webtest: {result.name}  kind={result.kind}  {status}{cm}")
    print(f"    ID: {result.id}")
    return result.id


def create_metric_alert(
    client: MonitorManagementClient,
    rg: str,
    ai_id: str,
    ag_id: str,
    test_name: str,
    severity: int,
    description: str,
) -> None:
    """Create a metric alert scoped to App Insights, filtered to a webtest."""
    alert = MetricAlertResource(
        location="global",
        description=description,
        severity=severity,
        enabled=True,
        scopes=[ai_id],
        evaluation_frequency="PT5M",
        window_size="PT10M",
        criteria=MetricAlertSingleResourceMultipleMetricCriteria(
            all_of=[
                MetricCriteria(
                    name=f"{test_name}-fail",
                    metric_name="availabilityResults/availabilityPercentage",
                    metric_namespace="microsoft.insights/components",
                    time_aggregation="Average",
                    operator="LessThan",
                    threshold=90.0,
                    dimensions=[
                        MetricDimension(
                            name="availabilityResult/name",
                            operator="Include",
                            values=[test_name],
                        ),
                    ],
                ),
            ],
        ),
        actions=[MetricAlertAction(action_group_id=ag_id)],
    )
    result = client.metric_alerts.create_or_update(
        resource_group_name=rg,
        rule_name=f"{test_name}-webtest",
        parameters=alert,
    )
    print(f"  Alert: {result.name}  sev={result.severity}  window={result.window_size}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy App Insights webtests")
    parser.add_argument("--subscription-id", required=True)
    parser.add_argument("--resource-group", required=True)
    parser.add_argument("--app-insights-id", required=True)
    parser.add_argument("--action-group-id", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--locations", required=True, help="Comma-separated")
    parser.add_argument("--frequency", type=int, default=300)
    parser.add_argument("--enable-scheduler", type=str, default="false")
    args = parser.parse_args()

    locations = [l.strip() for l in args.locations.split(",")]
    enable_scheduler = args.enable_scheduler.lower() in ("true", "1", "yes")

    credential = AzureCliCredential()
    ai_client = ApplicationInsightsManagementClient(credential, args.subscription_id)
    mon_client = MonitorManagementClient(credential, args.subscription_id)

    # 1. Data-freshness webtest (severity 1 = error-level)
    print(f"\n  [1/2] data-freshness  ({args.base_url}/healthz/data)")
    create_webtest(
        ai_client,
        args.resource_group,
        args.app_insights_id,
        name="data-freshness",
        url=f"{args.base_url}/healthz/data",
        content_match='"any_stale":false',
        locations=locations,
        frequency=args.frequency,
        enabled=True,
        description=(
            "ct-vuv: /healthz/data must contain any_stale:false -- "
            "pages ops when core tenants go stale"
        ),
    )
    create_metric_alert(
        mon_client,
        args.resource_group,
        args.app_insights_id,
        args.action_group_id,
        test_name="data-freshness",
        severity=1,
        description=(
            "ct-vuv: data-freshness webtest failed -- "
            "/healthz/data content-match not found (stale data)"
        ),
    )

    # 2. Scheduler-liveness webtest (severity 2 = warning-level, disabled until PR #102)
    sched_label = "ENABLED" if enable_scheduler else "DISABLED (until PR #102 deploys)"
    print(f"\n  [2/2] scheduler-live  ({args.base_url}/healthz/scheduler)  [{sched_label}]")
    create_webtest(
        ai_client,
        args.resource_group,
        args.app_insights_id,
        name="scheduler-live",
        url=f"{args.base_url}/healthz/scheduler",
        content_match='"running":true',
        locations=locations,
        frequency=args.frequency,
        enabled=enable_scheduler,
        description=(
            "ct-vuv: /healthz/scheduler must contain running:true. "
            "DISABLED until PR #102 is deployed."
        ),
    )
    if enable_scheduler:
        create_metric_alert(
            mon_client,
            args.resource_group,
            args.app_insights_id,
            args.action_group_id,
            test_name="scheduler-live",
            severity=2,
            description=(
                "ct-vuv: scheduler-live webtest failed -- "
                "/healthz/scheduler content-match not found (stalled scheduler)"
            ),
        )
    else:
        print("  Alert: skipped (scheduler test disabled; re-run with ENABLE_SCHEDULER_TEST=true)")


if __name__ == "__main__":
    main()
