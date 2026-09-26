
# Supply Chain Exception Manager MVP

## What it does
- Upload CSV or Excel
- Detect late orders, low inventory, stockout risk, partial shipments, supplier delays, and aging orders
- Rank exceptions by severity
- Recommend actions
- Display KPI cards and charts
- Export exception queue
- Optionally generate AI explanations

## Files
- `app.py` — Streamlit dashboard
- `exception_engine.py` — rules and severity scoring
- `ai_advisor.py` — optional AI explanation
- `sample_orders_inventory.csv` — sample data
- `.env.example` — API key template
- `requirements.txt` — dependencies

## Run in VS Code

### Windows
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

### Mac/Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Then open the local Streamlit URL, usually `http://localhost:8501`.

## Optional AI setup
Copy `.env.example` to `.env` and put your API key inside:
```text
OPENAI_API_KEY=your_api_key_here
```

The dashboard works without the AI key.

## Best next upgrades
1. Add PostgreSQL
2. Save exception history
3. Add user login
4. Add owner/status workflow
5. Add email/Slack alerts
6. Add supplier scorecards
7. Add demand forecasting
8. Add SAP/NetSuite/WMS integrations
