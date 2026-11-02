"""Create a monthly AWS Budget for this project's services, emailing at 50% / 100% actual and 100% forecast.

Usage: python scripts/create_budget.py --email you@example.com [--usd 20]
Scoped to the services this project uses, so other workloads in the same account don't trigger it.
"""
import argparse

import boto3

SERVICES = ["Amazon Location Service", "Amazon API Gateway", "AWS Lambda", "Amazon DynamoDB",
            "AWS Amplify", "Amazon Polly", "Amazon Athena"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", required=True)
    ap.add_argument("--usd", default="20")
    ap.add_argument("--name", default="manhole-pilgrim-monthly")
    a = ap.parse_args()
    account = boto3.client("sts").get_caller_identity()["Account"]
    budgets = boto3.client("budgets", region_name="us-east-1")
    sub = [{"SubscriptionType": "EMAIL", "Address": a.email}]
    notes = [
        ({"NotificationType": "ACTUAL", "ComparisonOperator": "GREATER_THAN", "Threshold": 50, "ThresholdType": "PERCENTAGE"}, sub),
        ({"NotificationType": "ACTUAL", "ComparisonOperator": "GREATER_THAN", "Threshold": 100, "ThresholdType": "PERCENTAGE"}, sub),
        ({"NotificationType": "FORECASTED", "ComparisonOperator": "GREATER_THAN", "Threshold": 100, "ThresholdType": "PERCENTAGE"}, sub),
    ]
    budgets.create_budget(
        AccountId=account,
        Budget={"BudgetName": a.name, "BudgetType": "COST", "TimeUnit": "MONTHLY",
                "BudgetLimit": {"Amount": a.usd, "Unit": "USD"},
                "CostFilters": {"Service": SERVICES}},
        NotificationsWithSubscribers=[{"Notification": n, "Subscribers": s} for n, s in notes],
    )
    b = budgets.describe_budget(AccountId=account, BudgetName=a.name)["Budget"]
    n = budgets.describe_notifications_for_budget(AccountId=account, BudgetName=a.name)["Notifications"]
    print(b["BudgetName"], b["BudgetLimit"], "services:", len(b["CostFilters"]["Service"]), "alerts:", len(n))


if __name__ == "__main__":
    main()
