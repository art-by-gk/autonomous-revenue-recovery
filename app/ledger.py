import sqlite3
import pandas as pd
from models import LedgerRecord

DB_FILE = "recovery_audit.db"


def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recovery_ledger (
            attempt_id TEXT PRIMARY KEY,
            transaction_id TEXT,
            customer_name TEXT,
            principal_amount REAL,
            failure_reason TEXT,
            attempt_number INTEGER,
            simulated_success_prob REAL,
            action_taken TEXT,
            cost REAL,
            status TEXT,
            recovered_amount REAL,
            decision_source TEXT,
            outcome_source TEXT,
            timestamp DATETIME
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS llm_review_audit (
            review_id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id TEXT NOT NULL,
            review TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def reset_recovery_ledger():
    """Reset synthetic benchmark data before a fresh batch run."""
    conn = sqlite3.connect(DB_FILE)
    conn.execute("DELETE FROM recovery_ledger")
    conn.commit()
    conn.close()


def save_ledger_record(record: LedgerRecord):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO recovery_ledger
        (attempt_id, transaction_id, customer_name, principal_amount,
         failure_reason, attempt_number, simulated_success_prob, action_taken,
         cost, status, recovered_amount, decision_source, outcome_source, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        record.attempt_id,
        record.transaction_id,
        record.customer_name,
        record.principal_amount,
        record.failure_reason,
        record.attempt_number,
        round(record.simulated_success_prob, 4),
        record.action_taken.value,
        record.cost,
        record.status.value,
        record.recovered_amount,
        record.decision_source,
        record.outcome_source,
        record.timestamp.isoformat(),
    ))
    conn.commit()
    conn.close()


def get_ledger_metrics():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql("SELECT * FROM recovery_ledger ORDER BY timestamp DESC", conn)
    conn.close()

    if df.empty:
        return {
            "total_at_risk": 0.0,
            "total_recovered": 0.0,
            "financial_recovery_rate": 0.0,
            "total_cost": 0.0,
            "recovered_count": 0,
            "escalated_count": 0,
            "stopped_count": 0,
            "processed_count": 0,
            "recent_events": [],
        }

    # One terminal record per transaction for financial accounting.
    unique_txns = (
        df.sort_values(
            by=["transaction_id", "attempt_number", "timestamp"],
            ascending=True,
        )
        .groupby("transaction_id", as_index=False)
        .last()
    )

    total_at_risk = float(unique_txns["principal_amount"].sum())
    total_recovered = float(unique_txns["recovered_amount"].sum())
    total_cost = float(df["cost"].sum())
    financial_recovery_rate = (
        total_recovered / total_at_risk * 100 if total_at_risk > 0 else 0.0
    )

    return {
        "total_at_risk": round(total_at_risk, 2),
        "total_recovered": round(total_recovered, 2),
        "financial_recovery_rate": round(financial_recovery_rate, 1),
        "total_cost": round(total_cost, 2),
        "recovered_count": int((unique_txns["status"] == "RECOVERED").sum()),
        "escalated_count": int((unique_txns["status"] == "ESCALATED_HUMAN_REVIEW").sum()),
        "stopped_count": int((unique_txns["status"] == "STOPPED_MAX_ATTEMPTS").sum()),
        "processed_count": int(len(unique_txns)),
        "recent_events": df.head(20).to_dict(orient="records"),
    }


def print_financial_audit_summary():
    metrics = get_ledger_metrics()
    print("\n" + "=" * 72)
    print("                 RECOVERY AUDIT LEDGER SUMMARY")
    print("=" * 72)
    print(f" Transactions Processed      : {metrics['processed_count']}")
    print(f" Total Principal At Risk     : ₹{metrics['total_at_risk']:,.2f}")
    print(f" Total Money Recovered       : ₹{metrics['total_recovered']:,.2f}")
    print(f" Financial Recovery Rate     : {metrics['financial_recovery_rate']:.1f}%")
    print(f" Total Execution Cost        : ₹{metrics['total_cost']:,.2f}")
    print(
        " Terminal State Distribution : "
        f"{metrics['recovered_count']} Recovered | "
        f"{metrics['escalated_count']} Escalated | "
        f"{metrics['stopped_count']} Stopped"
    )
    print("=" * 72 + "\n")


def get_transaction_history(transaction_id: str):
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql(
        "SELECT transaction_id, customer_name, principal_amount, failure_reason, "
        "attempt_number, simulated_success_prob, action_taken, cost, status, "
        "recovered_amount, decision_source, outcome_source, timestamp "
        "FROM recovery_ledger WHERE transaction_id = ? "
        "ORDER BY attempt_number ASC, timestamp ASC",
        conn,
        params=(transaction_id,),
    )
    conn.close()
    return df.to_dict(orient="records")


def save_llm_review(transaction_id: str, review: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO llm_review_audit (transaction_id, review) VALUES (?, ?)",
        (transaction_id, review),
    )
    conn.commit()
    conn.close()
