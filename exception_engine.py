
import pandas as pd
from datetime import datetime

REQUIRED_COLUMNS = [
    "Order ID","SKU","Customer","Order Date","Required Ship Date","Order Status",
    "Ordered Quantity","Shipped Quantity","Inventory On Hand","Reorder Point",
    "Safety Stock","Supplier","Expected Receipt Date","Actual Receipt Date","Unit Cost"
]

def validate_columns(df):
    return [c for c in REQUIRED_COLUMNS if c not in df.columns]

def prepare_data(df):
    df = df.copy()
    for col in ["Order Date","Required Ship Date","Expected Receipt Date","Actual Receipt Date"]:
        df[col] = pd.to_datetime(df[col], errors="coerce")
    for col in ["Ordered Quantity","Shipped Quantity","Inventory On Hand","Reorder Point","Safety Stock","Unit Cost"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df

def classify_severity(score):
    if score >= 80: return "Critical"
    if score >= 60: return "High"
    if score >= 40: return "Medium"
    return "Low"

def calculate_severity(row):
    score = 0
    if row["Late Order"]:
        score += min(int(row["Days Late"]) * 5, 30)
    if row["Stockout Risk"]:
        score += 25
    elif row["Low Inventory"]:
        score += 15
    if row["Supplier Delay"]:
        score += 15
    if row["Partial Shipment"]:
        unfilled = max(row["Ordered Quantity"] - row["Shipped Quantity"], 0)
        ratio = unfilled / row["Ordered Quantity"] if row["Ordered Quantity"] else 0
        score += min(int(ratio * 20), 20)
    if row["Aging Order"]:
        score += 10
    if row["Order Value"] >= 10000:
        score += 15
    elif row["Order Value"] >= 5000:
        score += 10
    elif row["Order Value"] >= 1000:
        score += 5
    return min(score, 100)

def recommend_action(row):
    actions = []
    if row["Late Order"]:
        actions.append("Escalate order and confirm revised ship commitment")
    if row["Stockout Risk"]:
        actions.append("Check alternate inventory and expedite replenishment")
    elif row["Low Inventory"]:
        actions.append("Review replenishment quantity and PO timing")
    if row["Supplier Delay"]:
        actions.append("Contact supplier for updated ETA or expedite")
    if row["Partial Shipment"]:
        actions.append("Review remaining quantity and prioritize allocation")
    if row["Aging Order"]:
        actions.append("Investigate blocking issue and assign owner")
    if row["Unshipped Order"]:
        actions.append("Escalate fulfillment, confirm inventory availability, and establish a revised ship commitment")
    return "; ".join(actions) if actions else "No action required"

def detect_exceptions(df, as_of_date=None):
    df = prepare_data(df)
    today = pd.Timestamp(as_of_date or datetime.now().date())

    df["Days Late"] = (today - df["Required Ship Date"]).dt.days.fillna(0).clip(lower=0)
    df["Open Days"] = (today - df["Order Date"]).dt.days.fillna(0).clip(lower=0)

    status = df["Order Status"].astype(str).str.lower()
    not_shipped = ~status.isin(["shipped","complete","completed","closed"])

    df["Late Order"] = (df["Required Ship Date"] < today) & not_shipped
    df["Low Inventory"] = df["Inventory On Hand"] < df["Reorder Point"]
    df["Stockout Risk"] = df["Inventory On Hand"] < df["Safety Stock"]
    df["Partial Shipment"] = (
        (df["Shipped Quantity"] > 0) &
        (df["Shipped Quantity"] < df["Ordered Quantity"])
        ).astype(int)
    df["Unshipped Order"] = (
        (df["Shipped Quantity"] == 0) &
        (df["Ordered Quantity"] > 0)
        ).astype(int)
    df["Supplier Delay"] = (
        (df["Actual Receipt Date"].notna() & df["Expected Receipt Date"].notna() &
         (df["Actual Receipt Date"] > df["Expected Receipt Date"]))
        |
        (df["Actual Receipt Date"].isna() & df["Expected Receipt Date"].notna() &
         (df["Expected Receipt Date"] < today))
    )
    df["Aging Order"] = (df["Open Days"] > 14) & not_shipped
    df["Order Value"] = df["Ordered Quantity"] * df["Unit Cost"]

    exception_cols = exception_cols = [
        "Late Order",
        "Low Inventory",
        "Stockout Risk",
        "Unshipped Order",
        "Partial Shipment",
        "Supplier Delay",
        "Aging Order",
        ]
    df["Exception List"] = df.apply(lambda r: [c for c in exception_cols if bool(r[c])], axis=1)
    df["Exception Count"] = df["Exception List"].apply(len)
    df["Exception"] = df["Exception List"].apply(lambda x: ", ".join(x) if x else "None")

    df["Severity Score"] = df.apply(calculate_severity, axis=1)
    df["Severity"] = df["Severity Score"].apply(classify_severity)
    df["Recommended Action"] = df.apply(recommend_action, axis=1)
    
    return df
