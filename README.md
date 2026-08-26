# Autonomous Revenue Recovery Engine

A bounded closed-loop revenue recovery prototype that handles payment
failures through deterministic recovery policies, controlled
interventions, audit logging, batch benchmarking, and an on-demand
human-review copilot.

> **Prototype benchmark · Synthetic payment events and gateway outcomes
> · No real payments executed**

## Overview

Payment failures can represent revenue at risk, but recovery actions
should remain bounded and explainable.

``` text
Payment Failure Event
        ↓
   PaymentEvent
        ↓
 Deterministic Policy
        ↓
 Bounded Intervention
        ↓
 Synthetic Gateway
        ↓
 Success / Failure
      ↙       ↘
 Recovered   Retry
                ↓
          Maximum 3 Attempts
                ↓
              Stop
                ↓
       Recovery Audit Ledger
                ↓
       Financial Recovery Metrics
```

A separate review path provides an LLM-assisted analysis of recorded
transaction history:

``` text
Recovery Ledger
      ↓
Transaction History
      ↓
LLM Review Copilot
      ↓
Human Reviewer
```

The copilot is advisory only. It does not control the recovery engine or
execute payment actions.

## Core Components

### `models.py`

Defines the core data contracts and enums:

-   `PaymentEvent`
-   `FailureReason`
-   `ActionType`
-   `RecoveryStatus`
-   `InterventionResult`
-   `LedgerRecord`

The ledger records also identify the decision source and outcome source.
fileciteturn3file3L49-L63

### `policy.py`

Contains the deterministic recovery policy and acts as the authority for
automated financial actions.

Current policy boundaries include:

-   stop autonomous outreach at 3 previous attempts
-   escalate suspicious transactions
-   escalate transactions at or above ₹15,000
-   use smart retry for timeout failures
-   use a localized recovery link for insufficient funds
-   provide an update flow for expired instruments
-   use a generic reminder as the fallback for other non-risk declines

These rules are implemented directly in the bounded intervention policy.
fileciteturn3file4L4-L15 fileciteturn3file4L18-L30
fileciteturn3file4L33-L72

### `main.py`

Orchestrates the closed-loop recovery flow.

It:

1.  receives a payment event
2.  asks the deterministic policy for an intervention
3.  handles human escalation and stopping rules
4.  executes autonomous actions through the synthetic gateway simulator
5.  records outcomes in the recovery ledger
6.  retries failed autonomous attempts within the configured boundary
7.  exposes the API and dashboard

The webhook endpoint accepts a `PaymentEvent` and starts the recovery
workflow as a background task. fileciteturn3file2L17-L23
fileciteturn3file2L114-L120

### `simulator.py`

Provides synthetic gateway outcomes for benchmarking.

The simulator uses fixed benchmark probabilities for recovery actions.
These are synthetic assumptions, not learned ML predictions.
fileciteturn3file7L5-L22

  Action                         Synthetic success probability
  ---------------------------- -------------------------------
  Smart retry                                              70%
  Localized recovery message                               62%
  Token update link                                        78%
  Generic email                                            45%

### `ledger.py`

Maintains the SQLite recovery audit ledger and calculates:

-   total principal at risk
-   total money recovered
-   financial recovery rate
-   total execution cost
-   recovered transaction count
-   human escalation count
-   stopped transaction count
-   processed transaction count
-   transaction history

The ledger records each attempt and calculates financial metrics using
the transaction history. fileciteturn3file0L49-L72
fileciteturn3file0L78-L121

### `llm_review.py`

Provides an on-demand review assistant for human operators.

The review is constrained to the supplied transaction history and is
instructed to:

-   summarize confirmed evidence
-   identify a root cause only when supported by the history
-   distinguish inference from observed evidence
-   recommend a human next step
-   generate a reviewer note
-   identify relevant automation boundaries
-   provide a confidence level

The LLM is explicitly not allowed to approve, reject, retry, refund,
cancel, escalate, or execute payment actions.
fileciteturn3file1L12-L31 fileciteturn3file1L62-L96

## Benchmark

The benchmark uses a reproducible synthetic dataset:

``` text
7 deterministic edge cases
+
193 generated transactions
=
200 transactions
```

The edge cases exercise important policy boundaries, including timeout,
insufficient funds, expired instruments, the ₹15,000 high-value
boundary, suspicious transactions, the maximum-attempt boundary, and the
₹14,999 below-threshold boundary. fileciteturn3file6L16-L27

The generated dataset uses a fixed seed for reproducibility, and the
benchmark explicitly identifies its gateway outcomes as synthetic rather
than ML predictions. fileciteturn3file6L29-L43
fileciteturn3file6L62-L73

## Safety Boundaries

The prototype intentionally keeps financial authority in the
deterministic policy layer.

``` text
                 ┌─────────────────────┐
Payment Event →  │ Deterministic Policy │ → Financial Action
                 └─────────────────────┘

Recovery Ledger → LLM Review → Human Reviewer
```

The LLM does not override policy, modify the recovery ledger, or execute
payments. The review endpoint is explicitly exposed as an on-demand
human-review assist mode. fileciteturn3file2L123-L140

Autonomous recovery is bounded by a maximum of three attempts, while
suspicious or high-value transactions are routed to human review.
fileciteturn3file4L7-L29

## Metrics

The dashboard exposes:

-   Total Principal At Risk
-   Total Money Recovered
-   Financial Recovery Rate
-   Terminal State Distribution
-   Total Execution Cost
-   recovery execution attempts
-   transaction history
-   decision source
-   recovery status

The financial summary is derived from the recovery ledger.
fileciteturn3file0L106-L121

These are benchmark results from synthetic events and should not be
interpreted as real-world payment performance.

## Project Structure

``` text
autonomous-revenue-recovery/
│
├── README.md
├── requirements.txt
│
├── app/
│   ├── main.py
│   ├── models.py
│   ├── policy.py
│   ├── ledger.py
│   ├── simulator.py
│   └── llm_review.py
│
├── benchmark/
│   └── run_batch.py
│
└── docs/
    ├── architecture.md
    └── demo-flow.md
```

## Setup

### 1. Clone

``` bash
git clone <https://github.com/art-by-gk/autonomous-revenue-recovery>
cd autonomous-revenue-recovery
```

### 2. Create a virtual environment

Windows:

``` bash
python -m venv .venv
.venv\Scripts\activate
```

Linux/macOS:

``` bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

``` bash
pip install -r requirements.txt
```

The current dependency list includes FastAPI, Uvicorn, Pydantic, Pandas,
`python-dotenv`, and Groq. fileciteturn3file5L1-L6

### 4. Configure the review copilot

Create a local `.env` file:

``` env
GROQ_API_KEY=your_api_key
GROQ_MODEL=openai/gpt-oss-20b
```

## Run the Synthetic Benchmark

From the project root:

``` bash
python benchmark/run_batch.py
```

The benchmark initializes the recovery ledger, resets previous synthetic
benchmark data, generates the 200-transaction dataset, executes the
closed-loop workflow, and prints the financial audit summary.
fileciteturn3file6L62-L82

## Run the Application

From the project root:

``` bash
uvicorn app.main:app --reload
```

The application exposes:

``` text
POST /api/v1/webhook
GET  /api/v1/analytics
GET  /api/v1/review/{transaction_id}
GET  /
```

The dashboard provides recovery metrics, audit history, transaction
inspection, and the on-demand review copilot.
fileciteturn3file2L114-L145

## Example Policy Flow

``` text
Failure Reason
      │
      ├── Suspicious / Amount ≥ ₹15,000
      │          ↓
      │     Human Escalation
      │
      ├── Timeout
      │          ↓
      │      Smart Retry
      │
      ├── Insufficient Funds
      │          ↓
      │   Localized Recovery Link
      │
      ├── Expired Instrument
      │          ↓
      │    Token Update Link
      │
      └── Other Non-Risk Decline
                 ↓
          Generic Reminder
```

## Prototype vs. Real-World Extension

This repository is intentionally a prototype and uses synthetic payment
events and gateway outcomes.

A real deployment could replace the synthetic components with:

``` text
Real Payment Webhook
        ↓
Validation + Idempotency
        ↓
Durable Queue
        ↓
Recovery Worker
        ↓
Recovery Policy
        ↓
Payment Provider
        ↓
Gateway Callback
        ↓
Persistent Audit Ledger
```

With sufficient real historical payment outcomes, a recovery model could
later provide a probability or ranking signal to the policy layer.

The model would provide a decision input; the deterministic policy would
remain responsible for enforcing bounded financial actions.

## What This Prototype Demonstrates

-   bounded closed-loop recovery
-   deterministic financial decision authority
-   failure-specific interventions
-   human escalation boundaries
-   maximum-attempt stopping rules
-   synthetic gateway outcome simulation
-   measurable recovery outcomes
-   audit logging
-   human-in-the-loop LLM review
-   reproducible batch benchmarking

## Scope

This project does **not** process real payments.

It does not claim:

-   production-grade payment infrastructure
-   real gateway success rates
-   real-world recovery performance
-   ML-trained recovery probabilities
-   live payment execution

The benchmark is designed to demonstrate the recovery workflow and
decision boundaries in a controlled synthetic environment.
