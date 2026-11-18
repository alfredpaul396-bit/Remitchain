"""
RemitChain - Send money home for cents, not percent.
NEOMA MSc Fintech & DeFi - Final Group Project

The problem: sending money abroad through a bank can cost 10-15% in fees
and hidden exchange-rate margins, and takes days.

Our app does three simple things:
    1. Compare  - see how much your family really receives
    2. Send     - send money using a stablecoin (a digital euro on a blockchain)
    3. Check    - every transfer is saved on a ledger that nobody can secretly change

How to run:
    pip install streamlit pandas
    streamlit run remitchain_app.py

This is a demo: no real money moves. Rates and fees are sample values.
"""

import hashlib
from datetime import datetime

import pandas as pd
import streamlit as st

st.set_page_config(page_title="RemitChain", page_icon="💸")

# ---------------------------------------------------------------------------
# 1. Sample data (simple, fixed values for the demo)
# ---------------------------------------------------------------------------
# How many units of local currency you get for 1 euro (sample rates)
RATES = {"India (INR)": 98.0, "Philippines (PHP)": 65.0, "Morocco (MAD)": 10.8}

# Cost of each way to send money:
#   fee    = fixed fee in euros
#   margin = % hidden in the exchange rate
OPTIONS = {
    "Bank": {"fee": 40.0, "margin": 3.0, "time": "1-5 days"},
    "Money transfer company": {"fee": 4.0, "margin": 1.5, "time": "Up to 1 day"},
    "RemitChain": {"fee": 0.05, "margin": 0.5, "time": "Under 1 minute"},
}
REMITCHAIN_FEE = 0.003  # our 0.3% service fee


def amount_received(amount, option, rate):
    """How much local currency the family receives with this option."""
    cost = OPTIONS[option]
    fees = cost["fee"]
    if option == "RemitChain":
        fees += amount * REMITCHAIN_FEE
    rate_after_margin = rate * (1 - cost["margin"] / 100)
    return max(amount - fees, 0) * rate_after_margin


def fingerprint(record, previous_fingerprint):
    """A unique code for a transfer, linked to the transfer before it."""
    text = f"{record['From']}{record['To']}{record['Amount (EUR)']}{previous_fingerprint}"
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def ledger_is_intact(ledger):
    """Recalculate every fingerprint. If one record was changed, they stop matching."""
    previous = "start"
    for record in ledger:
        if record["Fingerprint"] != fingerprint(record, previous):
            return False
        previous = record["Fingerprint"]
    return True


# ---------------------------------------------------------------------------
# 2. Memory of the app (kept while the browser tab is open)
# ---------------------------------------------------------------------------
if "balance" not in st.session_state:
    st.session_state.balance = 1000.0
    st.session_state.ledger = []

# ---------------------------------------------------------------------------
# 3. The app
# ---------------------------------------------------------------------------
st.title("💸 RemitChain")
st.write("**Send money home for cents, not percent.**")

tab1, tab2, tab3 = st.tabs(["1. Compare", "2. Send", "3. Check"])

# ---------------- Tab 1: Compare ----------------
with tab1:
    st.header("How much will your family receive?")
    amount = st.number_input("Amount to send (€)", min_value=10, value=300, step=10)
    country = st.selectbox("Country", list(RATES.keys()))
    currency = country[-4:-1]
    rate = RATES[country]

    results = []
    for option in OPTIONS:
        received = amount_received(amount, option, rate)
        cost_pct = (1 - received / (amount * rate)) * 100
        results.append({"Option": option,
                        f"Family receives ({currency})": round(received),
                        "Total cost": f"{cost_pct:.1f}%",
                        "Time": OPTIONS[option]["time"]})

    table = pd.DataFrame(results)
    st.dataframe(table, hide_index=True, use_container_width=True)
    st.bar_chart(table.set_index("Option")[f"Family receives ({currency})"])

    extra = results[2][f"Family receives ({currency})"] - results[0][f"Family receives ({currency})"]
    st.success(f"With RemitChain, your family gets **{extra:,} {currency} more** than with a bank.")

# ---------------- Tab 2: Send ----------------
with tab2:
    st.header("Send money")
    st.metric("Your balance", f"€{st.session_state.balance:,.2f}")

    name = st.text_input("Recipient name", "Priya")
    send_amount = st.number_input("Amount (€)", min_value=1, value=200, step=10)
    send_country = st.selectbox("Country", list(RATES.keys()), key="send_country")

    if st.button("Send now", type="primary"):
        if send_amount > st.session_state.balance:
            st.error("Not enough money in your balance.")
        else:
            ledger = st.session_state.ledger
            received = amount_received(send_amount, "RemitChain", RATES[send_country])
            record = {
                "Time": datetime.now().strftime("%d/%m %H:%M"),
                "From": "You",
                "To": name,
                "Amount (EUR)": send_amount,
                "Received": f"{received:,.0f} {send_country[-4:-1]}",
            }
            previous = ledger[-1]["Fingerprint"] if ledger else "start"
            record["Fingerprint"] = fingerprint(record, previous)
            ledger.append(record)
            st.session_state.balance -= send_amount
            st.balloons()
            st.success(f"Done! {name} receives {record['Received']} in under a minute.")

# ---------------- Tab 3: Check ----------------
with tab3:
    st.header("Check every transfer")
    st.write("Each transfer gets a fingerprint that is linked to the one before it. "
             "If anyone changes an old transfer, the fingerprints stop matching.")

    ledger = st.session_state.ledger
    if not ledger:
        st.info("No transfers yet. Send one in tab 2.")
    else:
        st.dataframe(pd.DataFrame(ledger), hide_index=True, use_container_width=True)

        if ledger_is_intact(ledger):
            st.success("✅ All transfers are genuine. Nothing has been changed.")
        else:
            st.error("❌ Warning: an old transfer was changed!")

        col1, col2 = st.columns(2)
        if col1.button("Try to cheat: change the first transfer to €9,999"):
            ledger[0]["Amount (EUR)"] = 9999
            st.rerun()
        if col2.button("Reset the demo"):
            st.session_state.clear()
            st.rerun()

st.caption("Demo only: no real money is sent. Rates and fees are sample values.")
