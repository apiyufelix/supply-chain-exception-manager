
import os, json
from dotenv import load_dotenv
load_dotenv()

def build_prompt(row):
    return f'''
You are a supply chain operations analyst.
Return ONLY valid JSON with these keys:
likely_cause, business_impact, recommended_action, priority_reason.

Order ID: {row.get("Order ID")}
SKU: {row.get("SKU")}
Customer: {row.get("Customer")}
Exceptions: {row.get("Exception")}
Days Late: {row.get("Days Late")}
Ordered Quantity: {row.get("Ordered Quantity")}
Shipped Quantity: {row.get("Shipped Quantity")}
Inventory On Hand: {row.get("Inventory On Hand")}
Reorder Point: {row.get("Reorder Point")}
Safety Stock: {row.get("Safety Stock")}
Supplier: {row.get("Supplier")}
Order Value: {row.get("Order Value")}
Severity: {row.get("Severity")}
Severity Score: {row.get("Severity Score")}
'''.strip()

def get_ai_advice(row):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {
            "likely_cause": "AI disabled because OPENAI_API_KEY is not configured.",
            "business_impact": "Use the rule-based severity and recommendation fields.",
            "recommended_action": row.get("Recommended Action",""),
            "priority_reason": f'Severity {row.get("Severity")} ({row.get("Severity Score")})'
        }
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        response = client.responses.create(
            model="gpt-5.6-mini",
            input=build_prompt(row)
        )
        return json.loads(response.output_text.strip())
    except Exception as e:
        return {
            "likely_cause": "AI analysis unavailable.",
            "business_impact": "Review exception details manually.",
            "recommended_action": row.get("Recommended Action",""),
            "priority_reason": f"Fallback used: {str(e)[:100]}"
        }
