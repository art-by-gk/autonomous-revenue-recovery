import time
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse

from models import PaymentEvent, LedgerRecord, RecoveryStatus, ActionType
from policy import resolve_bounded_intervention
from simulator import simulate_gateway_callback
from ledger import (
    init_db, save_ledger_record, get_ledger_metrics, get_transaction_history,
    save_llm_review
)
from llm_review import review_transaction

# ---------------------------------------------------------
# Application setup
# ---------------------------------------------------------

app = FastAPI(title="AI Revenue Recovery Engine")
init_db()

# ---------------------------------------------------------
# Closed-loop recovery workflow
# ---------------------------------------------------------

def execute_closed_loop_recovery(
    payment: PaymentEvent,
    max_attempts: int = 3,
):
    """Executes multi-cycle state transitions for webhook-ingested failures."""
    while payment.previous_attempts < max_attempts:
        current_cycle = payment.previous_attempts + 1
        attempt_id = f"{payment.id}_att{current_cycle}_{int(time.time()*1000)}"

        # Ask the deterministic policy for the allowed intervention.
        decision = resolve_bounded_intervention(payment)

        print(
            f"\n⚡ [CYCLE {current_cycle}] Tx: {payment.id} "
            f"(₹{payment.amount:,.2f}) - "
            f"Reason: {payment.failure_reason.value}"
        )
        print(f"   [Policy] Deterministic bounded decision")
        print(
            f"   [Intervention] Action: {decision.action.value} "
            f"(Cost: ₹{decision.cost:.2f})"
        )

        # 1. Escalation Route
        if decision.action == ActionType.HUMAN_ESCALATION:
            save_ledger_record(LedgerRecord(
                attempt_id=attempt_id,
                transaction_id=payment.id,
                customer_name=payment.customer_name,
                principal_amount=payment.amount,
                failure_reason=payment.failure_reason.value,
                attempt_number=current_cycle,
                simulated_success_prob=0.0,
                action_taken=decision.action,
                cost=decision.cost,
                status=RecoveryStatus.ESCALATED,
                recovered_amount=0.0
            ))
            return

        # 2. Stopping Rule Route
        if decision.action == ActionType.STOP_TERMINATE:
            save_ledger_record(LedgerRecord(
                attempt_id=attempt_id,
                transaction_id=payment.id,
                customer_name=payment.customer_name,
                principal_amount=payment.amount,
                failure_reason=payment.failure_reason.value,
                attempt_number=current_cycle,
                simulated_success_prob=0.0,
                action_taken=decision.action,
                cost=0.0,
                status=RecoveryStatus.STOPPED,
                recovered_amount=0.0
            ))
            return

        # 3. Autonomous Execution & Verification
        success, simulated_prob = simulate_gateway_callback(decision.action)

        if success:
            save_ledger_record(LedgerRecord(
                attempt_id=attempt_id,
                transaction_id=payment.id,
                customer_name=payment.customer_name,
                principal_amount=payment.amount,
                failure_reason=payment.failure_reason.value,
                attempt_number=current_cycle,
                simulated_success_prob=simulated_prob,
                action_taken=decision.action,
                cost=decision.cost,
                status=RecoveryStatus.RECOVERED,
                recovered_amount=payment.amount
            ))
            return
        else:
            save_ledger_record(LedgerRecord(
                attempt_id=attempt_id,
                transaction_id=payment.id,
                customer_name=payment.customer_name,
                principal_amount=payment.amount,
                failure_reason=payment.failure_reason.value,
                attempt_number=current_cycle,
                simulated_success_prob=simulated_prob,
                action_taken=decision.action,
                cost=decision.cost,
                status=RecoveryStatus.PENDING_RETRY,
                recovered_amount=0.0
            ))
            payment.previous_attempts += 1
            payment.minutes_since_last_attempt += 720

    # -----------------------------------------------------
    # Exhausted attempts -> Stop
    # -----------------------------------------------------
    final_id = f"{payment.id}_att{max_attempts+1}_{int(time.time()*1000)}"
    save_ledger_record(LedgerRecord(
        attempt_id=final_id,
        transaction_id=payment.id,
        customer_name=payment.customer_name,
        principal_amount=payment.amount,
        failure_reason=payment.failure_reason.value,
        attempt_number=max_attempts,
        simulated_success_prob=0.0,
        action_taken=ActionType.STOP_TERMINATE,
        cost=0.0,
        status=RecoveryStatus.STOPPED,
        recovered_amount=0.0
    ))


# ---------------------------------------------------------
# API endpoints
# ---------------------------------------------------------

@app.post("/api/v1/webhook")
async def handle_payment_webhook(
    event: PaymentEvent,
    background_tasks: BackgroundTasks,
):
    background_tasks.add_task(execute_closed_loop_recovery, event)
    return {
        "status": "ACCEPTED",
        "event_id": event.id,
        "pipeline": "CLOSED_LOOP_RECOVERY_ACTIVE"
    }

@app.get("/api/v1/review/{transaction_id}")
async def review_transaction_endpoint(
    transaction_id: str,
):
    history = get_transaction_history(transaction_id)
    if not history:
        return {"error": f"Transaction {transaction_id} not found"}

    try:
        review = review_transaction(transaction_id, history)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM review failed: {exc}") from exc
    save_llm_review(transaction_id, review)
    return {
        "transaction_id": transaction_id,
        "review": review,
        "history": history,
        "mode": "ON_DEMAND_HUMAN_REVIEW_ASSIST",
    }

@app.get("/api/v1/analytics")
async def get_analytics():
    return get_ledger_metrics()


# ---------------------------------------------------------
# Dashboard
# ---------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
  return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Revenue Recovery Dashboard</title>
    <style>
        :root {
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            color: #202124;
            background: #f7f6f2;
            font-synthesis: none;
            text-rendering: optimizeLegibility;
        }
        * {
            box-sizing: border-box;
        }
        body {
            margin: 0;
            min-width: 320px;
            background: #f7f6f2;
        }
        button, input {
            font: inherit;
        }
        .page {
            min-height: 100vh;
            padding: 48px 24px;
        }
        .container {
            width: min(1180px, 100%);
            margin: 0 auto;
        }
        .prototype-note {
            margin-top: 8px;
            font-size: 10px;
            color: #6b7280;
            letter-spacing: 0.1px;
        }
        

        /* HEADER */
        .header {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 32px;
            padding-bottom: 32px;
            border-bottom: 1px solid #deddd8;
        }
        .eyebrow, .section-label {
            margin: 0 0 8px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            color: #6b6b67;
        }
        h1 {
            margin: 0;
            font-size: clamp(28px, 4vw, 36px);
            line-height: 1.1;
            letter-spacing: -0.035em;
            font-weight: 650;
            color: #202124;
        }
        .subtitle {
            max-width: 620px;
            margin: 10px 0 0;
            color: #686864;
            font-size: 14px;
            line-height: 1.5;
        }
        .refresh-button {
            border: 1px solid #d2d1cc;
            border-radius: 7px;
            background: #fff;
            color: #30302e;
            padding: 9px 15px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 600;
            transition: background 0.15s ease;
        }
        .refresh-button:hover {
            background: #f0efeb;
        }

        /* METRICS */
        .metrics {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            border-top: 1px solid #deddd8;
            border-bottom: 1px solid #deddd8;
            margin-top: 32px;
            background: #fff;
        }
        .metric {
            min-height: 120px;
            padding: 22px 20px;
            border-right: 1px solid #deddd8;
        }
        .metric:last-child {
            border-right: none;
        }
        .metric p {
            margin: 0 0 12px;
            color: #777771;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }
        .metric strong {
            display: block;
            font-size: 24px;
            line-height: 1.1;
            letter-spacing: -0.025em;
            color: #202124;
        }
        .metric strong.emphasis {
            color: #176b45;
        }
        .metric strong.secondary {
            color: #1a56db;
        }
        .metric span {
            display: block;
            margin-top: 6px;
            color: #777771;
            font-size: 12px;
            font-weight: 500;
        }

        /* SECTION HEADINGS */
        .section {
            margin-top: 48px;
        }
        .section-heading {
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
            gap: 30px;
            margin-bottom: 16px;
        }
        .section-heading h2 {
            margin: 0;
            font-size: 20px;
            letter-spacing: -0.02em;
            font-weight: 650;
        }
        .section-heading > p, .section-heading > span {
            margin: 0;
            color: #777771;
            font-size: 13px;
        }

        /* INSPECT PANEL */
        .inspect-card {
            padding: 24px;
            background: #faf9f6;
            border: 1px solid #deddd8;
            border-radius: 8px;
        }
        .inspect-input-group {
            display: flex;
            gap: 8px;
            margin-top: 14px;
        }
        .inspect-input {
            flex: 1;
            background: #fff;
            border: 1px solid #d2d1cc;
            border-radius: 6px;
            padding: 9px 12px;
            font-size: 13px;
            font-family: monospace;
            color: #202124;
            outline: none;
        }
        .inspect-input:focus {
            border-color: #202124;
        }
        .inspect-button {
            padding: 9px 16px;
            background: #202124;
            color: #fff;
            border: 1px solid #202124;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: opacity 0.15s;
        }
        .inspect-button:hover {
            opacity: 0.9;
        }
        #reviewStatus {
            margin-top: 12px;
            font-size: 12px;
            color: #686864;
        }
        #reviewResult {
            margin-top: 14px;
            padding: 16px;
            background: #fff;
            border: 1px solid #d2d1cc;
            border-radius: 6px;
            font-size: 13px;
            line-height: 1.6;
            color: #30302e;
            white-space: pre-wrap;
            font-family: monospace;
        }
        .hidden {
            display: none !important;
        }

        /* TABLE */
        .table-wrapper {
            overflow-x: auto;
            border-top: 1px solid #deddd8;
            border-bottom: 1px solid #deddd8;
            background: #fff;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            min-width: 900px;
        }
        th {
            padding: 12px 14px;
            background: #eeede8;
            color: #666660;
            font-size: 11px;
            font-weight: 700;
            text-align: right;
            white-space: nowrap;
            letter-spacing: 0.05em;
        }
        th:first-child, th:nth-child(2), th:nth-child(5), th:nth-child(6), th:nth-child(7), th:nth-child(9) {
            text-align: left;
        }
        td {
            padding: 14px;
            border-top: 1px solid #e4e3de;
            font-size: 13px;
            text-align: right;
            color: #30302e;
        }
        td:first-child, td:nth-child(2), td:nth-child(5), td:nth-child(6), td:nth-child(7), td:nth-child(9) {
            text-align: left;
        }
        td.font-mono {
            font-family: monospace;
        }
        td.recovered {
            color: #176b45;
            font-weight: 650;
        }
        .table-btn {
            border: 1px solid #d2d1cc;
            background: #faf9f6;
            color: #202124;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            cursor: pointer;
        }
        .table-btn:hover {
            background: #eeede8;
        }

        /* BADGES */
        .badge {
            display: inline-block;
            padding: 2px 7px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 0.04em;
        }
        .badge-recovered {
            background: #e8f5e9;
            color: #176b45;
            border: 1px solid #c8e6c9;
        }
        .badge-escalated {
            background: #fff8e1;
            color: #996b18;
            border: 1px solid #ffecb3;
        }
        .badge-stopped {
            background: #ffebee;
            color: #9a3c35;
            border: 1px solid #ffcdd2;
        }
        .badge-neutral {
            background: #f0efeb;
            color: #686864;
            border: 1px solid #d2d1cc;
        }

        /* RESPONSIVE */
        @media (max-width: 850px) {
            .metrics {
                grid-template-columns: repeat(2, 1fr);
            }
            .metric:nth-child(2) {
                border-right: none;
            }
            .section-heading {
                align-items: flex-start;
                flex-direction: column;
                gap: 8px;
            }
        }
        @media (max-width: 600px) {
            .page {
                padding: 24px 16px;
            }
            .header {
                flex-direction: column;
                gap: 16px;
            }
            .metrics {
                grid-template-columns: 1fr;
            }
            .metric {
                border-right: none;
                border-bottom: 1px solid #deddd8;
            }
            .metric:last-child {
                border-bottom: none;
            }
            
    </style>
</head>
<body>
    <div class="page">
        <div class="container">
            <!-- HEADER -->
            <div class="header">
    <div>
        <p class="eyebrow">Autonomous Governance & Recovery Engine</p>

        <h1>Revenue Recovery Ledger</h1>

        <p class="subtitle">
            Closed-Loop Recovery Sequencer, Stopping Rules & Audit Trail
        </p>

        <p class="prototype-note">
            Prototype benchmark · Synthetic payment events and gateway outcomes · No real payments executed
        </p>
    </div>

    <button onclick="fetchData()" class="refresh-button">
        Refresh Ledger
    </button>
</div>

            <!-- METRICS -->
            <div class="metrics">
                <div class="metric">
                    <p>Total Principal At Risk</p>
                    <strong id="totalAtRisk">₹0.00</strong>
                </div>
                <div class="metric">
                    <p>Total Money Recovered</p>
                    <strong id="totalRecovered" class="emphasis">₹0.00</strong>
                </div>
                <div class="metric">
                    <p>Financial Recovery Rate</p>
                    <strong id="financialRecoveryRate" class="secondary">0%</strong>
                </div>
                <div class="metric">
                    <p>Terminal State Distribution</p>
                    <strong id="outcomes" style="font-size: 16px; margin-top: 6px;">0 Rec | 0 Esc | 0 Stop</strong>
                </div>
            </div>

            <!-- HUMAN REVIEW SECTION -->
            <div class="section">
                <div class="inspect-card">
                    <p class="section-label">On-Demand Copilot</p>
                    <h2 style="margin: 0; font-size: 18px; font-weight: 650;">Human Review & Risk Assessment</h2>
                    <p style="margin: 6px 0 0; font-size: 13px; color: #686864;">
                        Inspect an escalated or flagged transaction. The copilot synthesizes evidence strictly from ledger logs without executing payment actions.
                    </p>
                    <div class="inspect-input-group">
                        <input id="reviewTid" class="inspect-input" placeholder="Transaction ID e.g. TX_SYN_0001, TX_EDGE_005" />
                        <button onclick="reviewTid()" class="inspect-button">Inspect</button>
                    </div>
                    <div id="reviewStatus" class="hidden"></div>
                    <pre id="reviewResult" class="hidden"></pre>
                </div>
            </div>

            <!-- AUDIT TABLE SECTION -->
            <div class="section">
                <div class="section-heading">
                    <div>
                        <p class="section-label">Audit Trail</p>
                        <h2>Recovery Execution Attempts</h2>
                    </div>
                    <span id="totalCost" style="font-family: monospace; font-size: 12px;">Total Execution Cost: ₹0.00</span>
                </div>

                <div class="table-wrapper">
                    <table>
                        <thead>
                            <tr>
                                <th>Tx ID</th>
                                <th>Customer</th>
                                <th>Principal</th>
                                <th>Att #</th>
                                <th>Failure Reason</th>
                                <th>Action Taken</th>
                                <th>Status</th>
                                <th>Recovered</th>
                                <th>Decision</th>
                                <th>Review</th>
                            </tr>
                        </thead>
                        <tbody id="ledgerBody"></tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <script>
        function reviewById(tid) {
            document.getElementById('reviewTid').value = tid;
            reviewTid();
        }

        async function reviewTid() {
            const tid = document.getElementById('reviewTid').value.trim();
            const status = document.getElementById('reviewStatus');
            const result = document.getElementById('reviewResult');
            if (!tid) return;
            status.classList.remove('hidden');
            result.classList.add('hidden');
            status.innerText = 'Analyzing transaction history from audit logs…';
            try {
                const res = await fetch('/api/v1/review/' + encodeURIComponent(tid));
                const data = await res.json();
                if (!res.ok || data.error) throw new Error(data.error || 'Review failed');
                result.innerText = data.review;
                result.classList.remove('hidden');
                status.innerText = 'AI review synthesized from ledger. Human decision remains authoritative.';
            } catch (err) {
                status.innerText = 'Review unavailable: ' + err.message;
            }
        }

        async function fetchData() {
            const res = await fetch('/api/v1/analytics');
            const data = await res.json();
            
            document.getElementById('totalAtRisk').innerText = '₹' + data.total_at_risk.toLocaleString('en-IN', {minimumFractionDigits: 2});
            document.getElementById('totalRecovered').innerText = '₹' + data.total_recovered.toLocaleString('en-IN', {minimumFractionDigits: 2});
            document.getElementById('financialRecoveryRate').innerText = data.financial_recovery_rate + '%';
            document.getElementById('outcomes').innerText = `${data.recovered_count} Rec | ${data.escalated_count} Esc | ${data.stopped_count} Stop`;
            document.getElementById('totalCost').innerText = 'Total Execution Cost: ₹' + data.total_cost.toFixed(2);

            const tbody = document.getElementById('ledgerBody');
            tbody.innerHTML = '';
            data.recent_events.forEach(ev => {
                let badge = '<span class="badge badge-neutral">' + ev.status + '</span>';
                if(ev.status === 'RECOVERED') badge = '<span class="badge badge-recovered">RECOVERED</span>';
                if(ev.status === 'ESCALATED_HUMAN_REVIEW') badge = '<span class="badge badge-escalated">ESCALATED</span>';
                if(ev.status === 'STOPPED_MAX_ATTEMPTS') badge = '<span class="badge badge-stopped">STOPPED</span>';
                
                tbody.innerHTML += `
                    <tr>
                        <td class="font-mono" style="font-weight: 600; color: #1a56db;">${ev.transaction_id}</td>
                        <td style="font-weight: 500;">${ev.customer_name}</td>
                        <td class="font-mono">₹${ev.principal_amount.toLocaleString('en-IN')}</td>
                        <td class="font-mono" style="color: #777771;">${ev.attempt_number}</td>
                        <td style="color: #686864;">${ev.failure_reason}</td>
                        <td class="font-mono" style="font-size: 11px; color: #996b18;">${ev.action_taken}</td>
                        <td>${badge}</td>
                        <td class="font-mono recovered">₹${ev.recovered_amount.toLocaleString('en-IN')}</td>
                        <td class="font-mono" style="font-size: 10px; color: #777771;">${ev.decision_source}</td>
                        <td><button onclick="reviewById('${ev.transaction_id}')" class="table-btn">Inspect</button></td>
                    </tr>
                `;
            });
        }
        fetchData();
        setInterval(fetchData, 3000);
    </script>
</body>
</html>
  """
