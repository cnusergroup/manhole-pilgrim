"""Print Amazon Location Service unit prices (USD) for the operations this app uses, from the AWS Price List API.

Usage: python scripts/location_prices.py [region]
"""
import json
import sys

import boto3

REGION = sys.argv[1] if len(sys.argv) > 1 else "ap-northeast-1"
pricing = boto3.client("pricing", region_name="us-east-1")
rows = []
for page in pricing.get_paginator("get_products").paginate(
        ServiceCode="AmazonLocationService",
        Filters=[{"Type": "TERM_MATCH", "Field": "regionCode", "Value": REGION}]):
    for raw in page["PriceList"]:
        p = json.loads(raw)
        attrs = p["product"]["attributes"]
        for term in p.get("terms", {}).get("OnDemand", {}).values():
            for dim in term["priceDimensions"].values():
                usd = float(dim["pricePerUnit"].get("USD", 0))
                if usd > 0:
                    rows.append((attrs.get("usagetype", ""), dim.get("unit", ""), usd, dim.get("description", "")))
for usage, unit, usd, desc in sorted(set(rows)):
    print(f"{usd:12.6f} per {unit:10s} {usage:55s} {desc[:70]}")
