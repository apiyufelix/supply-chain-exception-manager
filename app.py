

from database import (
    initialize_database,
    ensure_resolved_on_column,
    get_workflow,
    save_workflow,
    get_exception_history,
    get_first_history_timestamp,
    get_resolved_today_count,
    get_all_workflows,
    get_oldest_open_hours,
    reset_exception_history
)

import streamlit as st
import pandas as pd
import plotly.express as px
from exception_engine import validate_columns, detect_exceptions
from ai_advisor import get_ai_advice
from datetime import datetime

SLA_HOURS = {
    "Critical": 4,
    "High": 8,
    "Medium": 24,
    "Low": 48,
}


st.set_page_config(
    page_title="Supply Chain Exception Manager",
    layout="wide"
)

initialize_database()
ensure_resolved_on_column()


def load_workflow_field(order_id, field):
    workflow = get_workflow(str(order_id))
    return workflow[field]

def calculate_resolution_hours(start_time, resolved_time):
    if not start_time or not resolved_time:
        return None

    fmt = "%Y-%m-%d %I:%M %p"

    start = datetime.strptime(start_time, fmt)
    end = datetime.strptime(resolved_time, fmt)

    # History may have been reset.
    # Do not return an invalid negative resolution time.
    if start > end:
        return None

    return round(
        (end - start).total_seconds() / 3600,
        1
    )

def calculate_average_resolution_time():
    workflows = get_all_workflows()

    resolution_times = []

    for row in workflows:

        order_id = row[0]
        resolved_on = row[4]

        if not resolved_on:
            continue

        first_history_time = (
            get_first_history_timestamp(
                order_id
            )
        )

        hours = calculate_resolution_hours(
            first_history_time,
            resolved_on
        )

        if hours is not None:
            resolution_times.append(hours)

    if not resolution_times:
        return None

    return (
        sum(resolution_times)
        / len(resolution_times)
    )

def calculate_sla_performance(df):
    total_evaluated = 0
    sla_met = 0

    for _, row in df.iterrows():

        order_id = str(row["Order ID"])
        severity = str(row["Severity"])

        sla_target = SLA_HOURS.get(
            severity
        )

        if sla_target is None:
            continue

        workflow = get_workflow(order_id)

        resolved_on = workflow.get(
            "resolved_on"
        )

        if not resolved_on:
            continue

        first_history_time = (
            get_first_history_timestamp(
                order_id
            )
        )

        resolution_hours = (
            calculate_resolution_hours(
                first_history_time,
                resolved_on
            )
        )

        if resolution_hours is None:
            continue

        total_evaluated += 1

        if resolution_hours <= sla_target:
            sla_met += 1

    if total_evaluated == 0:
        return None

    return (
        sla_met / total_evaluated
    ) * 100

def build_sla_breakdown(df):
    rows = []

    for _, row in df.iterrows():
        order_id = str(row["Order ID"])
        severity = str(row["Severity"])

        sla_target = SLA_HOURS.get(severity)

        if sla_target is None:
            continue

        workflow = get_workflow(order_id)

        resolved_on = workflow.get("resolved_on")

        if not resolved_on:
            continue

        first_history_time = get_first_history_timestamp(
            order_id
        )

        resolution_hours = calculate_resolution_hours(
            first_history_time,
            resolved_on
        )

        if resolution_hours is None:
            continue

        sla_result = (
            "Met"
            if resolution_hours <= sla_target
            else "Missed"
        )

        rows.append({
            "Order ID": order_id,
            "Severity": severity,
            "Resolution Time": resolution_hours,
            "SLA Target": sla_target,
            "SLA Result": sla_result,
        })

    return pd.DataFrame(rows)


st.markdown("""
<style>

.exception-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
}

.exception-table th {
    background-color: #1f2937;
    color: white;
    padding: 10px;
    text-align: left;
}

.exception-table td {
    padding: 10px;
    border-bottom: 1px solid #ddd;
}

.exception-table tr:hover {
    background-color: #f5f5f5;
}

</style>
""", unsafe_allow_html=True)

if "resolution_status" not in st.session_state:
    st.session_state.resolution_status = {}
if "assigned_owner" not in st.session_state:
    st.session_state.assigned_owner = {}

if "last_updated" not in st.session_state:
    st.session_state.last_updated = {}

st.title("Supply Chain Exception Manager")
st.caption("Upload order and inventory data, detect exceptions, rank severity, and get recommended actions.")
st.title("Supply Chain Exception Manager")

st.caption(
    "Detect supply chain exceptions, prioritize risk, "
    "assign owners, and track resolution."
)

st.info("""
Upload order and inventory data to automatically identify:

• Late orders
• Low inventory
• Stockout risk
• Unshipped orders
• Partial shipments
• Supplier delays
• Aging orders

The app ranks exceptions by severity, estimates value at risk,
assigns ownership, tracks resolution, and measures SLA performance.
""")


st.subheader("Get Started")

mode = st.radio(
    "Choose how you want to use the app:",
    ["Try Demo Data", "Upload My Data"],
    horizontal=True
)

if mode == "Try Demo Data":
    raw = pd.read_csv("sample_orders_inventory.csv")
    st.success("Demo data loaded successfully.")

else:
    uploaded = st.file_uploader(
        "Upload CSV or Excel",
        type=["csv", "xlsx", "xls"]
    )

    if uploaded is None:
        st.info(
            "Upload an order and inventory file to begin."
        )
        st.stop()

    try:
        raw = (
            pd.read_csv(uploaded)
            if uploaded.name.lower().endswith(".csv")
            else pd.read_excel(uploaded)
        )

    except Exception as e:
        st.error(f"Could not read file: {e}")
        st.stop()

missing = validate_columns(raw)
if missing:
    st.error("Missing required columns: " + ", ".join(missing))
    st.stop()

result = detect_exceptions(raw)

exceptions = result[result["Exception Count"] > 0].copy()

c1,c2,c3,c4,c5 = st.columns(5)
c1.metric("Orders Analyzed", f"{len(result):,}")
c2.metric("Orders With Exceptions", f"{len(exceptions):,}")
c3.metric("Critical Exceptions", f"{(exceptions['Severity']=='Critical').sum():,}")
c4.metric("Late Orders", f"{exceptions['Late Order'].sum():,}")
c5.metric("Order Value at Risk", f"${exceptions['Order Value'].sum():,.0f}")

st.divider()

severity_order = ["Critical","High","Medium","Low"]
f1,f2,f3 = st.columns(3)
sev = f1.multiselect("Severity", severity_order, default=severity_order)
suppliers = sorted(exceptions["Supplier"].dropna().astype(str).unique().tolist())
customers = sorted(exceptions["Customer"].dropna().astype(str).unique().tolist())
sup = f2.multiselect("Supplier", suppliers, default=suppliers)
cust = f3.multiselect("Customer", customers, default=customers)

filtered = exceptions[
    exceptions["Severity"].isin(sev) &
    exceptions["Supplier"].astype(str).isin(sup) &
    exceptions["Customer"].astype(str).isin(cust)
].copy()

filtered = filtered.copy()

filtered["Resolution Status"] = filtered["Order ID"].astype(str).apply(
    lambda order_id: load_workflow_field(
        order_id,
        "resolution_status"
    )
)

filtered["Assigned Owner"] = filtered["Order ID"].astype(str).apply(
    lambda order_id: load_workflow_field(
        order_id,
        "assigned_owner"
    )
)

filtered["Last Updated"] = filtered["Order ID"].astype(str).apply(
    lambda order_id: (
        load_workflow_field(
            order_id,
            "last_updated"
        )
        or "-"
    )
)



status_options = ["Open", "In Progress", "Resolved"]

owner_options = [
    "Unassigned",
    "Supply Chain",
    "Inventory Control",
    "Fulfillment",
    "Purchasing",
    "Customer Service",
    "Operations Manager"
]

f4, f5 = st.columns(2)

selected_status = f4.multiselect(
    "Resolution Status",
    status_options,
    default=status_options
)

selected_owner = f5.multiselect(
    "Assigned Owner",
    owner_options,
    default=owner_options
)

filtered = filtered[
    filtered["Resolution Status"].isin(selected_status) &
    filtered["Assigned Owner"].isin(selected_owner)
]

left,right = st.columns(2)
if not filtered.empty:
    exploded = filtered[["Order ID","Exception List"]].explode("Exception List")
    exc_counts = exploded["Exception List"].value_counts().reset_index()
    exc_counts.columns = ["Exception Type","Count"]
    left.plotly_chart(px.bar(exc_counts, x="Exception Type", y="Count", title="Exceptions by Type"), use_container_width=True)

    sev_counts = filtered["Severity"].value_counts().reindex(severity_order, fill_value=0).reset_index()
    sev_counts.columns = ["Severity","Count"]
    right.plotly_chart(px.bar(sev_counts, x="Severity", y="Count", title="Exceptions by Severity"), use_container_width=True)

resolved_today = (
    get_resolved_today_count()
)

avg_resolution_time = (
    calculate_average_resolution_time()
)

oldest_open_hours = (
    get_oldest_open_hours()
)

sla_percentage = (
    calculate_sla_performance(result)
)

st.subheader("Resolution Performance")

r1, r2, r3, r4 = st.columns(4)

r1.metric(
    "Resolved Today",
    f"{resolved_today:,}"
)

r2.metric(
    "Avg Resolution Time",
    (
        f"{avg_resolution_time:.1f} hrs"
        if avg_resolution_time is not None
        else "N/A"
    )
)

r3.metric(
    "Oldest Open Exception",
    (
        f"{oldest_open_hours:.1f} hrs"
        if oldest_open_hours is not None
        else "N/A"
    )
)

r4.metric(
    "SLA Compliance",
    (
        f"{sla_percentage:.1f}%"
        if sla_percentage is not None
        else "N/A"
    )
)

st.markdown("### SLA Breakdown")

sla_df = build_sla_breakdown(result)

if sla_df.empty:
    st.info(
        "No resolved exceptions are available for SLA evaluation."
    )

else:
    display_sla = sla_df.copy()

    display_sla["Resolution Time"] = (
        display_sla["Resolution Time"]
        .apply(lambda x: f"{x:.1f} hrs")
    )

    display_sla["SLA Target"] = (
        display_sla["SLA Target"]
        .apply(lambda x: f"{x:.0f} hrs")
    )

    sla_df["SLA Variance"] = (
        sla_df["Resolution Time"] - sla_df["SLA Target"]
    )
    
    display_sla["SLA Result"] = display_sla["SLA Result"].replace({
    "Met": "✅ Met",
    "Missed": "❌ Missed"
    })

    
    display_sla["SLA Variance"] = sla_df["SLA Variance"].apply(
    lambda x: (
        f"{x:.1f} hrs late"
        if x > 0
        else f"{abs(x):.1f} hrs early"
    )
    )

    met_count = (sla_df["SLA Result"] == "Met").sum()
    total_count = len(sla_df)

    st.caption(
        f"{met_count} of {total_count} resolved exceptions met SLA."
    )

    st.markdown(
        display_sla.to_html(
            index=False,
            classes="exception-table",
            border=0
        ),
        unsafe_allow_html=True
    )

st.subheader("Exception Queue")

# Make a copy first
filtered = filtered.copy()

open_count = (
    filtered["Resolution Status"] == "Open"
).sum()

in_progress_count = (
    filtered["Resolution Status"] == "In Progress"
).sum()

resolved_count = (
    filtered["Resolution Status"] == "Resolved"
).sum()

filtered["Order Value"] = pd.to_numeric(
    filtered["Order Value"],
    errors="coerce"
).fillna(0)

open_value = filtered.loc[
    filtered["Resolution Status"].isin(
        ["Open", "In Progress"]
    ),
    "Order Value"
].sum()

resolved_value = filtered.loc[
    filtered["Resolution Status"] == "Resolved",
    "Order Value"
].sum()

k1, k2, k3, k4, k5 = st.columns(5)

k1.metric(
    "Open Exceptions",
    f"{open_count:,}"
)

k2.metric(
    "In Progress",
    f"{in_progress_count:,}"
)

k3.metric(
    "Resolved",
    f"{resolved_count:,}"
)

k4.metric(
    "Open Value at Risk",
    f"${open_value:,.2f}"
)

k5.metric(
    "Risk Value Resolved",
    f"${resolved_value:,.2f}"
)


filtered["Assigned Owner"] = filtered["Order ID"].astype(str).apply(
    lambda order_id: st.session_state.assigned_owner.get(
        order_id,
        "Unassigned"
    )
)

filtered["Last Updated"] = filtered["Order ID"].astype(str).apply(
    lambda order_id: st.session_state.last_updated.get(
        order_id,
        "-"
    )
)

filtered["Resolution Status"] = filtered["Order ID"].apply(
    lambda x: load_workflow_field(
        x,
        "resolution_status"
    )
)

filtered["Assigned Owner"] = filtered["Order ID"].apply(
    lambda x: load_workflow_field(
        x,
        "assigned_owner"
    )
)

filtered["Last Updated"] = filtered["Order ID"].apply(
    lambda x: (
        load_workflow_field(
            x,
            "last_updated"
        )
        or "-"
    )
)

display_columns = [
    "Order ID",
    "Customer",
    "Supplier",
    "Exception",
    "Severity",
    "Severity Score",
    "Resolution Status",
    "Assigned Owner",
    "Last Updated",
    "Order Value"
]

available_columns = [
    col for col in display_columns
    if col in filtered.columns
]

display_df = filtered[available_columns].copy()

# Make Order Value numeric
display_df["Order Value"] = pd.to_numeric(
    display_df["Order Value"],
    errors="coerce"
)

# Rename only for display
display_df = display_df.rename(
    columns={
        "Order Value": "Value at Risk"
    }
)

if display_df.empty:
    st.info("No exceptions match the selected filters.")

else:
    html_table = display_df.to_html(
        index=False,
        classes="exception-table",
        border=0,
        formatters={
            "Value at Risk": lambda x: (
                f"${x:,.2f}"
                if pd.notna(x)
                else "$0.00"
            )
        }
    )

    st.markdown(
        html_table,
        unsafe_allow_html=True
    )



st.download_button(
    "Export Exception Queue",
    data=display_df.to_csv(index=False).encode("utf-8"),
    file_name="exception_queue.csv",
    mime="text/csv"
)

st.divider()
st.subheader("AI Exception Advisor")

if not filtered.empty:

    order_ids = filtered["Order ID"].astype(str).tolist()

    selected_order = st.selectbox(
        "Choose an Order ID",
        order_ids
    )

    selected = filtered[
        filtered["Order ID"].astype(str) == selected_order
    ].iloc[0]

    # Summary cards
    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Order ID",
        str(selected["Order ID"])
    )

    c2.metric(
        "Customer",
        str(selected["Customer"])
    )

    c3.metric(
        "Supplier",
        str(selected["Supplier"])
    )

    c4.metric(
        "Value at Risk",
        f"${float(selected['Order Value']):,.2f}"
    )

    order_id = str(selected["Order ID"])

    workflow = get_workflow(order_id)

    current_status = workflow["resolution_status"]
    current_owner = workflow["assigned_owner"]
    current_notes = workflow["manager_notes"]
    last_updated = workflow["last_updated"]
    resolved_on = workflow.get("resolved_on")


    # Last Updated
    if last_updated:
        st.caption(
            f"Last Updated: {last_updated}"
        )


    # Resolved On
    if resolved_on:
        st.caption(
            f"Resolved On: {resolved_on}"
        )

    first_history_time = get_first_history_timestamp(
    order_id
)
    # Resolution Time
    resolution_hours = calculate_resolution_hours(
    first_history_time,
    resolved_on
)

if resolved_on:
    st.caption(
        f"Resolved On: {resolved_on}"
    )

if resolution_hours is not None:
    st.metric(
        "Resolution Time",
        f"{resolution_hours:.1f} hrs"
    )

elif resolved_on:
    st.metric(
        "Resolution Time",
        "N/A"
    )

    st.caption(
        "Resolution time is unavailable because the "
        "earlier exception history was reset."
    )
st.markdown("### Exception Management")

m1, m2 = st.columns(2)

current_status = st.session_state.resolution_status.get(
    order_id,
    "Open"
)

status_options = [
"Open",
"In Progress",
"Resolved"
]

current_status = workflow.get(
    "resolution_status",
    "Open"
)

status = m1.selectbox(
    "Resolution Status",
    status_options,
    index=status_options.index(current_status),
    key=f"db_status_{order_id}"
)

current_owner = st.session_state.assigned_owner.get(
    order_id,
    "Unassigned"
)

owner_options = [
"Unassigned",
"Supply Chain",
"Inventory Control",
"Fulfillment",
"Purchasing",
"Customer Service",
"Operations Manager"
]

owner = m2.selectbox(
"Assigned Owner",
owner_options,
index=(
    owner_options.index(current_owner)
    if current_owner in owner_options
    else 0
),
key=f"db_owner_{order_id}"
)

manager_notes = st.text_area(
"Manager Notes",
value=current_notes,
placeholder=(
    "Add notes about root cause, supplier communication, "
    "customer impact, or next steps..."
),
key=f"notes_{order_id}"
)

if st.button(
    "Save Exception Update",
    key=f"save_{order_id}"
):
    updated_at = save_workflow(
        order_id=order_id,
        resolution_status=status,
        assigned_owner=owner,
        manager_notes=manager_notes
    )

    st.success(
        f"Exception update saved successfully. "
        f"Last updated: {updated_at}"
    )

    # Reload latest database values
    workflow = get_workflow(order_id)


# ---------------------------------
# RESET ALL EXCEPTION HISTORY
# ---------------------------------

with st.expander("Advanced History Settings"):

    confirm_reset = st.checkbox(
        "I understand this will permanently delete all exception "
        "history and may make historical resolution-time calculations unavailable.",
        key="confirm_reset_history"
    )

    if st.button(
        "Reset All Exception History",
        disabled=not confirm_reset,
        key="reset_all_history"
    ):
        reset_exception_history()

        st.success(
            "All exception history has been reset."
        )

        st.rerun()

    # Reload the latest database values
    workflow = get_workflow(order_id)

    resolved_on = workflow.get("resolved_on")

    first_history_time = get_first_history_timestamp(
        order_id
    )

    if resolved_on:
        st.caption(
            f"Resolved On: {resolved_on}"
        )

    resolution_hours = calculate_resolution_hours(
        first_history_time,
        resolved_on
    )

    if resolution_hours is not None:
        st.metric(
            "Resolution Time",
            f"{resolution_hours:.1f} hrs"
        )

st.markdown("### Exception History")

history = get_exception_history(order_id)

if history:

    for row in history:

        old_status = row[0] or "New"
        new_status = row[1]
        old_owner = row[2] or "Unassigned"
        new_owner = row[3]
        notes = row[4]
        changed_at = row[5]

        with st.expander(
            f"{changed_at} — {new_status} - {new_owner}"
        ):
            

            display_old_status = old_status or "Not Started"
            display_old_owner = old_owner or "Unassigned"
            
            if old_status != new_status:
                st.write(
                    f"**Status:** {old_status or 'Not Started'} → {new_status}"
                )

            if old_owner != new_owner:
                st.write(
                    f"**Owner:** {old_owner or 'Unassigned'} → {new_owner}"
                )

            if notes:
                st.write(
                    f"**Notes:** {notes}"
                )

else:
    st.info(
        "No history is available for this exception yet."
    )

    previous_status = st.session_state.resolution_status.get(
    order_id,
    "Open"
    )

    previous_owner = st.session_state.assigned_owner.get(
        order_id,
        "Unassigned"
    )

    if status != previous_status or owner != previous_owner:

        st.session_state.resolution_status[order_id] = status

        st.session_state.assigned_owner[order_id] = owner

        st.session_state.last_updated[order_id] = (
            datetime.now().strftime("%Y-%m-%d %I:%M %p")
        )

    last_updated = st.session_state.last_updated.get(
        order_id,
        "Not updated yet"
    )

    st.caption(
        f"Last Updated: {last_updated}"
    )

    current_status = st.session_state.resolution_status.get(
    order_id,
    "Open"
    )

    st.session_state.resolution_status[order_id] = status

    if status == "Open":
        st.error("🔴 Open")

    elif status == "In Progress":
        st.warning("🟠 In Progress")

    else:
        st.success("🟢 Resolved")
    st.markdown("---")

    # Severity
    severity = str(selected["Severity"])
    score = int(selected["Severity Score"])

    if severity == "Critical":
        st.error(
            f"🔴 CRITICAL — Risk Score: {score}/100"
        )

    elif severity == "High":
        st.warning(
            f"🟠 HIGH — Risk Score: {score}/100"
        )

    elif severity == "Medium":
        st.info(
            f"🟡 MEDIUM — Risk Score: {score}/100"
        )

    else:
        st.success(
            f"🟢 LOW — Risk Score: {score}/100"
        )
        
    # Detected exceptions
    
    initialize_database()
    

def load_workflow_field(order_id, field):
    workflow = get_workflow(str(order_id))
    return workflow[field]


# Primary-risk priority used throughout the app
priority_order = [
    "Stockout Risk",
    "Late Order",
    "Supplier Delay",
    "Unshipped Order",
    "Partial Shipment",
    "Low Inventory",
    "Aging Order"
]



exception_text = str(
    selected.get("Exception", "")
)

exception_list = [
    item.strip()
    for item in exception_text.split(",")
    if item.strip()
]

primary_exception = None

for priority in priority_order:
    if priority in exception_list:
        primary_exception = priority
        break

if primary_exception:
    st.markdown("### Primary Risk")
    st.warning(f"⚠️ **{primary_exception}**")
    
    st.markdown("### Detected Exceptions")
    exception_text = str(
            selected.get("Exception", "")
        )
    
    exception_list = [
        item.strip()
        for item in exception_text.split(",")
        if item.strip()
    ]

    if exception_list:
        for item in exception_list:
            st.markdown(f"- **{item}**")
    else:
        st.write("No exception details available.")

        # Financial impact

    st.markdown("### Financial Impact")
    
    order_value = float(selected.get("Order Value", 0))
    ordered_qty = float(selected.get("Ordered Quantity", 0))
    shipped_qty = float(selected.get("Shipped Quantity", 0))
    unit_cost = float(selected.get("Unit Cost", 0))

    remaining_qty = max(ordered_qty - shipped_qty, 0)

    remaining_value = 0
    if ordered_qty > 0:
        remaining_value = (
            remaining_qty / ordered_qty
        ) * order_value

    inventory_value = (
        float(selected.get("Inventory On Hand", 0))
        * unit_cost
    )

    f1, f2, f3 = st.columns(3)

    f1.metric(
        "Order Value",
        f"${order_value:,.2f}"
    )

    f2.metric(
        "Unshipped Value",
        f"${remaining_value:,.2f}"
    )

    f3.metric(
        "Value at Risk",
        f"${inventory_value:,.2f}"
    )

    risk_percent = 0

    if order_value > 0:
        risk_percent = (remaining_value / order_value) * 100
    st.caption(
        f"{risk_percent:.1f}% of this order's value is currently at risk."
    )

# Operational impact

    st.markdown("### Operational Impact")

    o1, o2, o3 = st.columns(3)

    o1.metric(
        "Days Late",
        int(selected.get("Days Late", 0))
    )

    o2.metric(
        "Open Days",
        int(selected.get("Open Days", 0))
    )

    remaining_qty = max(
        float(selected.get("Ordered Quantity", 0))
        - float(selected.get("Shipped Quantity", 0)),
        0
    )

    o3.metric(
        "Units Remaining",
        int(remaining_qty)
    )

    ordered_qty = float(selected.get("Ordered Quantity", 0))
    shipped_qty = float(selected.get("Shipped Quantity", 0))

    fill_rate = 0

    if ordered_qty > 0:
        fill_rate = (shipped_qty / ordered_qty) * 100

    q1, q2, q3 = st.columns(3)

    q1.metric(
        "Ordered Quantity",
        f"{ordered_qty:,.0f}"
    )

    q2.metric(
        "Shipped Quantity",
        f"{shipped_qty:,.0f}"
    )

    q3.metric(
        "Fill Rate",
        f"{fill_rate:.1f}%"
    )

    remaining_qty = max(
    ordered_qty - shipped_qty,
    0
    )

    unit_order_value = 0

    if ordered_qty > 0:
        unit_order_value = order_value / ordered_qty

    value_at_risk = (
        remaining_qty * unit_order_value
    )

    f1, f2, f3 = st.columns(3)

    f1.metric(
        "Order Value",
        f"${order_value:,.2f}"
    )

    f2.metric(
        "Value at Risk",
        f"${value_at_risk:,.2f}"
    )

    f3.metric(
        "Inventory Value",
        f"${inventory_value:,.2f}"
    )   
    # Why this needs attention
    st.markdown("### Risk Explanation")

    reasons = []

    if selected.get("Late Order", 0) == 1:
        reasons.append(
            f"The order is {int(selected['Days Late'])} day(s) late."
        )

    if selected.get("Low Inventory", 0) == 1:
        reasons.append(
            "Inventory on hand is below the reorder point."
        )

    if selected.get("Stockout Risk", 0) == 1:
        reasons.append(
            "Available inventory is below the level needed to protect customer demand."
        )

    if selected.get("Partial Shipment", 0) == 1:
        reasons.append(
            "The full ordered quantity has not yet been shipped."
        )

    if selected.get("Supplier Delay", 0) == 1:
        reasons.append(
            "The supplier receipt is delayed beyond the expected receipt date."
        )

    if selected.get("Aging Order", 0) == 1:
        reasons.append(
            f"The order has remained open for {int(selected['Open Days'])} day(s)."
        )

    if reasons:
        for reason in reasons:
            st.markdown(f"- {reason}")
    else:
        st.write(
            "This order requires monitoring based on current supply chain conditions."
        )

    # Recommended actions
    st.markdown("### Recommended Actions")

    action_text = str(
        selected.get("Recommended Action", "")
    )

    actions = [
        item.strip()
        for item in action_text.split(";")
        if item.strip()
    ]

    if actions:

        st.markdown("#### Immediate Action")

        st.success(
        f"✅ **{actions[0]}**"
    )

        if len(actions) > 1:

            st.markdown("#### Additional Recommended Actions")

            for number, action in enumerate(
                actions[1:],
                start=2
        ):
                st.markdown(
                f"**{number}.** {action}"
                )

else:
    st.info(
        "No exceptions are available for the selected filters."
    )
    