"""
Xtra - Use Xtra, save extra.
NEOMA MSc Fintech & DeFi - Final Group Project

Send money from any country, in any currency, to any country, in any currency.

Tabs:
    1. Compare  - what your family receives vs banks and other providers, plus
                  local times, stock exchanges and the forex market
    2. Send     - full transfer form with the bank details each country needs
    3. Check    - every transfer recorded on a tamper-evident ledger, with your
                  total savings
    4. FX risk  - volatility and risk of the currency pair you are sending

Live data (no API key needed):
    - Today's exchange rates: ExchangeRate-API open access (166 currencies)
      https://www.exchangerate-api.com - updated once a day
    - Rate history for the risk tab: fawazahmed0 currency-api (daily rates)
      https://github.com/fawazahmed0/exchange-api

How to run (keep world_data.py in the same folder):
    pip install -r requirements.txt
    streamlit run remitchain_app.py

This is a demo: no real money moves. Xtra's own fee levels are sample values.
"""

import hashlib
import json
import math
import random
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import altair as alt
import pandas as pd
import streamlit as st

from world_data import (BANK_FORMATS, COUNTRIES, CURRENCY_NAMES, DEFAULT_FORMAT, EXCHANGES,
                        IBAN_FORMAT, IBAN_LENGTHS, SANCTIONED)

st.set_page_config(page_title="Xtra · Use Xtra, save extra", page_icon="💚", layout="wide")

# ---------------------------------------------------------------------------
# 1. Costs
# ---------------------------------------------------------------------------
# Average total cost (fees + exchange-rate margin) of sending money, from the
# World Bank's Remittance Prices Worldwide (cost of sending $200).
COMPETITORS = {
    "Bank": {"cost": 14.99, "time": "1-5 days", "days": 3},
    "Money transfer company": {"cost": 5.91, "time": "Up to 1 day", "days": 1},
    "Digital-only app": {"cost": 3.54, "time": "Hours to 1 day", "days": 1},
}
WORLD_AVERAGE = 6.36  # global average cost, all providers (Q3 2025)

# Xtra's own costs (sample values for the demo)
XTRA_SERVICE_FEE = 0.003   # 0.3% service fee
XTRA_FX_MARGIN = 0.005     # 0.5% exchange-rate margin
XTRA_NETWORK_FEE_USD = 0.05  # blockchain network fee

PURPOSES = ["Family support", "Education", "Medical expenses", "Savings",
            "Gift", "Rent or bills", "Business payment", "Other"]


# ---------------------------------------------------------------------------
# 2. Live exchange rates
# ---------------------------------------------------------------------------
def get_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Xtra-student-app"})
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode())


@st.cache_data(ttl=900)  # ask again at most every 15 minutes
def live_rates():
    """All live rates against the US dollar: 1 USD = X currency."""
    data = get_json("https://open.er-api.com/v6/latest/USD")
    if data.get("result") != "success":
        raise RuntimeError("Rate service error")
    return data["rates"], data["time_last_update_utc"], data["time_next_update_utc"]


def cross_rate(rates, from_cur, to_cur):
    """How many units of to_cur you get for 1 unit of from_cur."""
    return rates[to_cur] / rates[from_cur]


def _one_day(day, base, quote):
    urls = [f"https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@{day}/v1/currencies/{base}.json",
            f"https://{day}.currency-api.pages.dev/v1/currencies/{base}.json"]
    for url in urls:
        try:
            return day, get_json(url)[base][quote]
        except Exception:
            continue
    return day, None


@st.cache_data(ttl=6 * 3600)
def rate_history(from_cur, to_cur, days=90):
    """Daily rates for the last N days (fetched in parallel)."""
    base, quote = from_cur.lower(), to_cur.lower()
    day_list = [(date.today() - timedelta(days=i)).isoformat() for i in range(days, 0, -1)]
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(lambda d: _one_day(d, base, quote), day_list))
    history = pd.Series({pd.Timestamp(d): v for d, v in results if v}, name=to_cur)
    if len(history) < 20:
        raise RuntimeError("Not enough history")
    return history.sort_index()


def risk_report(history):
    """Volatility and risk figures from a series of daily rates."""
    returns = history.pct_change().dropna()
    daily_vol = returns.std()
    annual_vol = daily_vol * math.sqrt(252) * 100
    level = "Low" if annual_vol < 5 else "Medium" if annual_vol < 10 else "High"
    return {
        "daily_vol": daily_vol,
        "annual_vol": annual_vol,
        "recent_annual_vol": returns.tail(30).std() * math.sqrt(252) * 100,
        "worst_day": returns.min() * 100,
        "best_day": returns.max() * 100,
        "var95": -returns.quantile(0.05) * 100,
        "change_period": (history.iloc[-1] / history.iloc[0] - 1) * 100,
        "level": level,
    }


# ---------------------------------------------------------------------------
# 3. Cost calculations
# ---------------------------------------------------------------------------
def xtra_quote(amount, mid, usd_to_from):
    """Fee (in sender currency) and amount received with Xtra."""
    fee = amount * XTRA_SERVICE_FEE + XTRA_NETWORK_FEE_USD * usd_to_from
    received = max(amount - fee, 0) * mid * (1 - XTRA_FX_MARGIN)
    return fee, received


def competitor_received(amount, mid, cost_pct):
    return amount * (1 - cost_pct / 100) * mid


def money(x, cur):
    return f"{x:,.2f} {cur}"


# ---------------------------------------------------------------------------
# 4. Time zones and markets
# ---------------------------------------------------------------------------
def local_time(code):
    return datetime.now(ZoneInfo(COUNTRIES[code]["tz"]))


def utc_offset(dt):
    offset = dt.utcoffset()
    minutes = int(offset.total_seconds() // 60)
    sign = "+" if minutes >= 0 else "-"
    return f"UTC{sign}{abs(minutes) // 60:02d}:{abs(minutes) % 60:02d}"


def exchange_status(code):
    if code not in EXCHANGES:
        return None
    name, opens, closes, days = EXCHANGES[code]
    now = local_time(code)
    hhmm = now.strftime("%H:%M")
    is_open = now.weekday() in days and opens <= hhmm < closes
    day_names = "Sun–Thu" if 6 in days else "Mon–Fri"
    return name, is_open, f"{opens}–{closes} local time, {day_names}"


def forex_market_open():
    """The global forex market trades 24 hours, from Sunday ~22:00 to Friday ~22:00 UTC."""
    now = datetime.now(timezone.utc)
    wd, hour = now.weekday(), now.hour
    if wd == 5 or (wd == 4 and hour >= 22) or (wd == 6 and hour < 22):
        return False
    return True


# ---------------------------------------------------------------------------
# 5. Bank details: formats, checks and sample values
# ---------------------------------------------------------------------------
def bank_fields(code):
    if code in BANK_FORMATS:
        return BANK_FORMATS[code]
    if code in IBAN_LENGTHS:
        return IBAN_FORMAT
    return DEFAULT_FORMAT


def digits(value):
    return re.sub(r"[\s-]", "", value)


def iban_ok(value, country):
    iban = re.sub(r"\s", "", value).upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]+", iban):
        return "IBAN must start with 2 letters and 2 digits."
    if iban[:2] != country:
        return f"IBAN must start with {country} for {COUNTRIES[country]['name']}."
    if country in IBAN_LENGTHS and len(iban) != IBAN_LENGTHS[country]:
        return f"An IBAN for {COUNTRIES[country]['name']} has {IBAN_LENGTHS[country]} characters."
    numeric = "".join(str(int(ch, 36)) for ch in iban[4:] + iban[:4])
    if int(numeric) % 97 != 1:
        return "IBAN check digits are wrong (please check for typos)."
    return None


def aba_ok(value):
    d = digits(value)
    if not re.fullmatch(r"\d{9}", d):
        return "ABA routing number must have 9 digits."
    weights = [3, 7, 1] * 3
    if sum(int(x) * w for x, w in zip(d, weights)) % 10:
        return "ABA routing number check digit is wrong."
    return None


def clabe_ok(value):
    d = digits(value)
    if not re.fullmatch(r"\d{18}", d):
        return "CLABE must have 18 digits."
    weights = [3, 7, 1] * 6
    total = sum((int(x) * w) % 10 for x, w in zip(d[:17], weights))
    if (10 - total % 10) % 10 != int(d[17]):
        return "CLABE check digit is wrong."
    return None


def check_field(field, value, country):
    """Return an error message, or None if the value looks valid."""
    v = value.strip()
    if not v:
        return f"{field} is required."
    d = digits(v)
    rules = {
        "IFSC code": (r"[A-Z]{4}0[A-Z0-9]{6}", "IFSC code: 4 letters, a zero, then 6 letters or digits (e.g. ABCD0123456)."),
        "SWIFT/BIC code": (r"[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?", "SWIFT/BIC code has 8 or 11 characters (e.g. DEUTDEFFXXX)."),
        "Sort code": (r"\d{6}", "Sort code has 6 digits (e.g. 12-34-56)."),
        "Institution number": (r"\d{3}", "Institution number has 3 digits."),
        "Transit number": (r"\d{5}", "Transit number has 5 digits."),
        "BSB code": (r"\d{6}", "BSB code has 6 digits."),
        "NUBAN account number": (r"\d{10}", "NUBAN account number has 10 digits."),
        "Bank code": (r"\d{3}", "Bank code has 3 digits."),
        "Branch number": (r"\d{4}", "Branch number has 4 digits."),
        "Branch code": (r"\d{3,6}", "Branch code has 3 to 6 digits."),
        "CPF/CNPJ (tax ID)": (r"\d{11}|\d{14}", "CPF has 11 digits, CNPJ has 14 digits."),
        "Mobile number": (r"\+?\d{7,15}", "Mobile number: 7 to 15 digits, with country code."),
    }
    if field == "IBAN":
        return iban_ok(v, country)
    if field == "ABA routing number":
        return aba_ok(v)
    if field == "CLABE":
        return clabe_ok(v)
    if field == "SWIFT/BIC code":
        code = v.upper().replace(" ", "")
        if not re.fullmatch(rules[field][0], code):
            return rules[field][1]
        if code[4:6] != country:
            return f"SWIFT/BIC code letters 5-6 should be {country} for {COUNTRIES[country]['name']}."
        return None
    if field == "IFSC code":
        return None if re.fullmatch(rules[field][0], v.upper()) else rules[field][1]
    if field in rules:
        return None if re.fullmatch(rules[field][0], d) else rules[field][1]
    if field == "Account number":
        limits = {"GB": (8, 8), "AU": (5, 9), "CA": (7, 12), "US": (4, 17), "IN": (9, 18), "NZ": (15, 16)}
        low, high = limits.get(country, (5, 34))
        if country in limits:
            ok = re.fullmatch(rf"\d{{{low},{high}}}", d)
        else:
            ok = re.fullmatch(rf"[A-Za-z0-9]{{{low},{high}}}", d)
        return None if ok else f"Account number should have {low} to {high} characters."
    if field in ("Bank name", "Wallet provider"):
        return None if len(v) >= 2 else f"{field} is too short."
    return None


def sample_value(field, country):
    """Fictional but correctly formatted details, for the demo."""
    def nums(n):
        return "".join(random.choice("0123456789") for _ in range(n))
    if field == "IBAN":
        length = IBAN_LENGTHS.get(country, 22)
        bban = nums(length - 4)
        numeric = "".join(str(int(ch, 36)) for ch in bban + country + "00")
        return f"{country}{98 - int(numeric) % 97:02d}{bban}"
    if field == "ABA routing number":
        first = nums(8)
        total = sum(int(x) * w for x, w in zip(first, [3, 7, 1, 3, 7, 1, 3, 7]))
        return first + str((10 - total % 10) % 10)
    if field == "CLABE":
        first = nums(17)
        total = sum((int(x) * w) % 10 for x, w in zip(first, [3, 7, 1] * 6))
        return first + str((10 - total % 10) % 10)
    samples = {
        "IFSC code": "DEMO0" + nums(6), "SWIFT/BIC code": f"DEMO{country}22",
        "Sort code": nums(6), "Institution number": nums(3), "Transit number": nums(5),
        "BSB code": nums(6), "NUBAN account number": nums(10), "Bank code": nums(3),
        "Branch number": nums(4), "Branch code": nums(3 if country == "JP" else 6),
        "CPF/CNPJ (tax ID)": nums(11), "Bank name": "Demo Bank",
        "Mobile number": "+" + nums(11), "Wallet provider": "Demo Wallet",
    }
    if field == "Account number":
        lengths = {"GB": 8, "AU": 8, "CA": 9, "US": 10, "IN": 12, "NZ": 15}
        return nums(lengths.get(country, 12))
    return samples.get(field, "")


def mask(value):
    v = re.sub(r"\s", "", value)
    return "•••• " + v[-4:] if len(v) > 4 else v


# ---------------------------------------------------------------------------
# 6. Ledger
# ---------------------------------------------------------------------------
def fingerprint(record):
    content = {k: v for k, v in record.items() if k != "Fingerprint"}
    return hashlib.sha256(json.dumps(content, sort_keys=True, default=str).encode()).hexdigest()[:16]


def ledger_is_intact(ledger):
    previous = "start"
    for record in ledger:
        if record["Previous fingerprint"] != previous or record["Fingerprint"] != fingerprint(record):
            return False
        previous = record["Fingerprint"]
    return True


# ---------------------------------------------------------------------------
# 7. Load live rates - the app only works with real data
# ---------------------------------------------------------------------------
st.title("💚 Xtra")
st.write("**Use Xtra, save extra.** Send money from any country, in any currency, "
         "to any country, in any currency, and your family gets extra every time.")

try:
    RATES, UPDATED, NEXT_UPDATE = live_rates()
except Exception:
    st.error("Could not load live exchange rates right now. Please check your internet "
             "connection and refresh the page in a minute.")
    st.stop()

if "balance_eur" not in st.session_state:
    st.session_state.balance_eur = 5000.0
    st.session_state.ledger = []

CURRENCIES = sorted(RATES)
CODES = list(COUNTRIES.keys())  # already sorted by country name


def country_label(code):
    return f"{COUNTRIES[code]['flag']} {COUNTRIES[code]['name']}"


def currency_label(cur):
    return f"{cur} – {CURRENCY_NAMES.get(cur, cur)}"


def currency_picker(label, country, key):
    default = next((c for c in COUNTRIES[country]["currencies"] if c in CURRENCIES), "USD")
    return st.selectbox(label, CURRENCIES, index=CURRENCIES.index(default),
                        format_func=currency_label, key=f"{key}_{country}")


# ---------------- Transfer route (shared by all tabs) ----------------
st.subheader("Your transfer route")
r1, r2, r3, r4 = st.columns(4)
FROM = r1.selectbox("Sending from", CODES, index=CODES.index("FR"), format_func=country_label)
with r2:
    FROM_CUR = currency_picker("Sending currency", FROM, "from_cur")
TO = r3.selectbox("Sending to", CODES, index=CODES.index("IN"), format_func=country_label)
with r4:
    TO_CUR = currency_picker("Receiving currency", TO, "to_cur")

MID = cross_rate(RATES, FROM_CUR, TO_CUR)
USD_TO_FROM = cross_rate(RATES, "USD", FROM_CUR)
st.caption(f"🟢 Live rate: **1 {FROM_CUR} = {MID:,.4f} {TO_CUR}** · last updated {UPDATED} · "
           f"next update {NEXT_UPDATE} · Rates by "
           "[Exchange Rate API](https://www.exchangerate-api.com)")

tab1, tab2, tab3, tab4 = st.tabs(["1. Compare", "2. Send", "3. Check", "4. FX risk"])

# ---------------------------------------------------------------------------
# Tab 1: Compare
# ---------------------------------------------------------------------------
with tab1:
    st.header("How much will your family receive?")
    amount = st.number_input(f"Amount to send ({FROM_CUR})", min_value=1.0, value=300.0, step=10.0)

    fee, xtra_received = xtra_quote(amount, MID, USD_TO_FROM)
    xtra_cost = (1 - xtra_received / (amount * MID)) * 100
    avg_received = competitor_received(amount, MID, WORLD_AVERAGE)

    rows = []
    for name, c in COMPETITORS.items():
        received = competitor_received(amount, MID, c["cost"])
        rows.append({"Option": f"{name} (average)", "Total cost": f"{c['cost']:.2f}%",
                     f"Family receives ({TO_CUR})": round(received, 2),
                     f"Your Xtra ({TO_CUR})": round(xtra_received - received, 2),
                     "Delivery time": c["time"]})
    rows.append({"Option": "Xtra", "Total cost": f"{xtra_cost:.2f}%",
                 f"Family receives ({TO_CUR})": round(xtra_received, 2),
                 f"Your Xtra ({TO_CUR})": 0.0,
                 "Delivery time": "Under 1 minute"})
    table = pd.DataFrame(rows)

    extra = xtra_received - avg_received
    st.success(f"💚 With Xtra your family gets **{money(extra, TO_CUR)} extra** compared with "
               f"the average provider ({WORLD_AVERAGE}% cost). That is "
               f"**{money(extra / MID, FROM_CUR)} saved** on this one transfer.")

    st.dataframe(table, hide_index=True, use_container_width=True)
    st.bar_chart(table.set_index("Option")[f"Family receives ({TO_CUR})"], horizontal=True)

    st.subheader("🕒 Time and markets right now")
    left, right = st.columns(2)
    for col, code, who in ((left, FROM, "Sender"), (right, TO, "Recipient")):
        with col:
            now = local_time(code)
            st.markdown(f"**{who}: {country_label(code)}**")
            st.metric("Local time", now.strftime("%H:%M"))
            st.caption(f"{now.strftime('%A %d %B')} · {utc_offset(now)}")
            ex = exchange_status(code)
            if ex:
                name, is_open, hours = ex
                st.write(f"{'🟢 Open' if is_open else '🔴 Closed'} · **{name}** ({hours})")
            else:
                st.write("No major stock exchange in our list for this country.")

    gap = (local_time(TO).utcoffset() - local_time(FROM).utcoffset()).total_seconds() / 3600
    st.write(f"⏱️ {COUNTRIES[TO]['name']} is **{abs(gap):g} hours "
             f"{'ahead of' if gap > 0 else 'behind' if gap < 0 else 'the same as'}** "
             f"{COUNTRIES[FROM]['name']}." if gap else
             f"⏱️ Both countries are in the same time zone.")
    st.write(("🟢 The global **forex market is open** (it trades 24 hours a day, Monday to Friday)."
              if forex_market_open() else
              "🔴 The global **forex market is closed** for the weekend (it reopens Sunday ~22:00 UTC). "
              "Xtra still delivers, at the latest live rate."))
    st.caption("Average costs: World Bank, Remittance Prices Worldwide (cost of sending $200: banks, "
               "digital-only apps and global average Q3 2025; money transfer companies Q1 2025). "
               "Stock exchange hours are main sessions only; lunch breaks and holidays not included.")

# ---------------------------------------------------------------------------
# Tab 2: Send
# ---------------------------------------------------------------------------
with tab2:
    st.header(f"Send money to {country_label(TO)}")
    balance = st.session_state.balance_eur * cross_rate(RATES, "EUR", FROM_CUR)
    st.metric("Your balance", money(balance, FROM_CUR))

    if TO in SANCTIONED:
        st.error(f"Transfers to {COUNTRIES[TO]['name']} are blocked: this country is under "
                 "broad international sanctions. Please choose another destination.")
    else:
        method = st.radio("How should the money arrive?", ["Bank account", "Mobile wallet"],
                          horizontal=True)
        fields = bank_fields(TO) if method == "Bank account" else ["Mobile number", "Wallet provider"]
        prefix = f"{TO}_{method}"

        if st.button("✨ Fill in sample details (demo)"):
            st.session_state[f"{prefix}_rname"] = "Priya Sharma" if TO == "IN" else "Sample Recipient"
            st.session_state[f"{prefix}_raddr"] = "12 Main Street, Capital City"
            for f in fields:
                if f != "Account type":
                    st.session_state[f"{prefix}_{f}"] = sample_value(f, TO)

        with st.form("send_form"):
            st.markdown("**1. You (sender)**")
            s1, s2 = st.columns(2)
            sender_name = s1.text_input("Your full name", "Sample Sender")
            s2.text_input("Sending from", country_label(FROM), disabled=True)

            st.markdown("**2. Recipient**")
            c1, c2 = st.columns(2)
            r_name = c1.text_input("Recipient full name (as on the account)", key=f"{prefix}_rname")
            r_addr = c2.text_input("Recipient address and city", key=f"{prefix}_raddr")
            purpose = c1.selectbox("Purpose of transfer", PURPOSES)
            c2.text_input("Receiving country", country_label(TO), disabled=True)

            st.markdown(f"**3. {method} details for {COUNTRIES[TO]['name']}**")
            values = {}
            cols = st.columns(2)
            for i, f in enumerate(fields):
                with cols[i % 2]:
                    if f == "Account type":
                        values[f] = st.selectbox(f, ["Checking", "Savings"], key=f"{prefix}_{f}")
                    else:
                        values[f] = st.text_input(f, key=f"{prefix}_{f}")

            st.markdown("**4. Amount**")
            send_amount = st.number_input(f"Amount ({FROM_CUR})", min_value=1.0, value=200.0, step=10.0)
            submitted = st.form_submit_button("🚀 Send now", type="primary")

        if submitted:
            errors = [check_field(f, v, TO) for f, v in values.items() if f != "Account type"]
            errors += [] if len(r_name.strip()) >= 3 else ["Recipient full name is required."]
            errors += [] if len(r_addr.strip()) >= 3 else ["Recipient address is required."]
            errors += [] if len(sender_name.strip()) >= 3 else ["Your full name is required."]
            errors = [e for e in errors if e]
            amount_eur = send_amount * cross_rate(RATES, FROM_CUR, "EUR")
            if amount_eur > st.session_state.balance_eur:
                errors.append("Not enough money in your balance.")
            if errors:
                for e in errors:
                    st.error(e)
            else:
                fee, received = xtra_quote(send_amount, MID, USD_TO_FROM)
                extra = received - competitor_received(send_amount, MID, WORLD_AVERAGE)
                saved_from = extra / MID
                ledger = st.session_state.ledger
                now_utc = datetime.now(timezone.utc)
                details = "; ".join(f"{f}: {v if f in ('Account type', 'Bank name', 'Wallet provider') else mask(v)}"
                                    for f, v in values.items())
                record = {
                    "Tx ID": "XT-" + hashlib.sha256(f"{now_utc}{r_name}".encode()).hexdigest()[:8].upper(),
                    "Date (UTC)": now_utc.strftime("%Y-%m-%d %H:%M:%S"),
                    "Sender local time": f"{local_time(FROM).strftime('%d/%m %H:%M')} ({COUNTRIES[FROM]['name']})",
                    "Recipient local time": f"{local_time(TO).strftime('%d/%m %H:%M')} ({COUNTRIES[TO]['name']})",
                    "Sender": sender_name.strip(),
                    "From": country_label(FROM),
                    "Amount sent": money(send_amount, FROM_CUR),
                    "Fee": money(fee, FROM_CUR),
                    "Rate": f"1 {FROM_CUR} = {MID * (1 - XTRA_FX_MARGIN):,.4f} {TO_CUR}",
                    "Recipient": r_name.strip(),
                    "Recipient address": r_addr.strip(),
                    "To": country_label(TO),
                    "Delivery": method,
                    "Account details": details,
                    "Purpose": purpose,
                    "Amount received": money(received, TO_CUR),
                    "Your Xtra": money(extra, TO_CUR),
                    "Saved": money(saved_from, FROM_CUR),
                    "Status": "✅ Delivered",
                    "_saved_eur": round(saved_from * cross_rate(RATES, FROM_CUR, "EUR"), 2),
                    "_sent_eur": round(amount_eur, 2),
                    "Previous fingerprint": ledger[-1]["Fingerprint"] if ledger else "start",
                }
                record["Fingerprint"] = fingerprint(record)
                ledger.append(record)
                st.session_state.balance_eur -= amount_eur
                total_saved = sum(r["_saved_eur"] for r in ledger) * cross_rate(RATES, "EUR", FROM_CUR)
                st.balloons()
                st.success(f"✅ Done! **{r_name}** receives **{record['Amount received']}** in under a "
                           f"minute. Transaction **{record['Tx ID']}** is saved in the ledger (tab 3).")
                st.info(f"💚 Your family received **{money(extra, TO_CUR)} extra** compared with the "
                        f"average provider. Your total Xtra so far: "
                        f"**{money(total_saved, FROM_CUR)}**.")

# ---------------------------------------------------------------------------
# Tab 3: Check
# ---------------------------------------------------------------------------
with tab3:
    st.header("Check every transfer")
    ledger = st.session_state.ledger
    if not ledger:
        st.info("No transfers yet. Send one in tab 2.")
    else:
        to_from = cross_rate(RATES, "EUR", FROM_CUR)
        total_saved = sum(r["_saved_eur"] for r in ledger) * to_from
        total_sent = sum(r["_sent_eur"] for r in ledger) * to_from
        st.success(f"🎉 Your total Xtra: since you joined, your families have received "
                   f"**{money(total_saved, FROM_CUR)} more** than with the average provider.")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Transfers", len(ledger))
        m2.metric("Total sent", money(total_sent, FROM_CUR))
        m3.metric("Total Xtra", money(total_saved, FROM_CUR))
        intact = ledger_is_intact(ledger)
        m4.metric("Ledger", "✅ Intact" if intact else "❌ Tampered")

        if intact:
            st.success("All transfers are genuine. Each record's fingerprint matches its content "
                       "and the record before it.")
        else:
            st.error("Warning: a transfer was changed after it was recorded! "
                     "Its fingerprint no longer matches.")

        visible = [{k: v for k, v in r.items() if not k.startswith("_")} for r in ledger]
        summary_cols = ["Tx ID", "Date (UTC)", "Sender", "Recipient", "To", "Amount sent",
                        "Amount received", "Your Xtra", "Status", "Fingerprint"]
        st.dataframe(pd.DataFrame(visible)[summary_cols], hide_index=True, use_container_width=True)

        st.subheader("Receipts")
        for r in reversed(visible):
            with st.expander(f"🧾 {r['Tx ID']} · {r['Recipient']} · {r['Amount received']}"):
                a, b = st.columns(2)
                items = list(r.items())
                half = (len(items) + 1) // 2
                for col, part in ((a, items[:half]), (b, items[half:])):
                    for k, v in part:
                        col.markdown(f"**{k}:** {v}")

        c1, c2, c3 = st.columns(3)
        if c1.button("😈 Try to cheat: change the first amount"):
            ledger[0]["Amount sent"] = money(999999, FROM_CUR)
            st.rerun()
        c2.download_button("⬇️ Download ledger (CSV)", pd.DataFrame(visible).to_csv(index=False),
                           "xtra_ledger.csv", "text/csv")
        if c3.button("Reset the demo"):
            st.session_state.clear()
            st.rerun()

# ---------------------------------------------------------------------------
# Tab 4: FX risk
# ---------------------------------------------------------------------------
with tab4:
    st.header(f"How risky is {FROM_CUR} → {TO_CUR}?")
    if FROM_CUR == TO_CUR:
        st.info("You are sending and receiving the same currency, so there is no exchange-rate risk.")
    else:
        st.write("Exchange rates move every day. The longer your money is travelling, "
                 "the more the rate can move against your family.")
        risk_amount = st.number_input(f"Amount you send ({FROM_CUR})", min_value=1.0, value=300.0,
                                      step=10.0, key="risk_amount")
        try:
            with st.spinner("Loading 90 days of rate history..."):
                history = rate_history(FROM_CUR, TO_CUR)
        except Exception:
            st.error("Could not load the rate history for this pair right now. Please try again "
                     "in a minute, or choose another currency.")
            history = None

        if history is not None:
            report = risk_report(history)
            st.subheader(f"1 {FROM_CUR} in {TO_CUR}, last 90 days")
            chart_data = history.rename_axis("Date").reset_index(name="Rate")
            st.altair_chart(
                alt.Chart(chart_data).mark_line().encode(
                    x=alt.X("Date:T", title=None),
                    y=alt.Y("Rate:Q", title=f"1 {FROM_CUR} in {TO_CUR}", scale=alt.Scale(zero=False)),
                    tooltip=["Date:T", alt.Tooltip("Rate:Q", format=",.4f")],
                ),
                use_container_width=True,
            )

            k1, k2, k3 = st.columns(3)
            k1.metric("Risk level", report["level"])
            k2.metric("Volatility (per year)", f"{report['annual_vol']:.1f}%",
                      f"{report['recent_annual_vol'] - report['annual_vol']:+.1f} pts last 30 days",
                      delta_color="inverse")
            k3.metric("Change over 90 days", f"{report['change_period']:+.1f}%")
            k4, k5, k6 = st.columns(3)
            k4.metric("Worst single day", f"{report['worst_day']:.2f}%")
            k5.metric("Best single day", f"+{report['best_day']:.2f}%")
            k6.metric("Bad day (1 in 20)", f"-{report['var95']:.2f}%")

            st.subheader("Why speed protects your family")
            st.write("Possible loss from a rate move while the money is travelling "
                     "(a bad case that happens about 1 time in 20):")
            rows = []
            for name, c in list(COMPETITORS.items()) + [("Xtra", {"time": "Under 1 minute", "days": 0})]:
                loss = 1.645 * report["daily_vol"] * math.sqrt(c["days"]) * 100
                rows.append({"Option": name, "Money travelling for": c["time"],
                             "Possible rate loss": f"{loss:.2f}%",
                             f"In {FROM_CUR}": money(risk_amount * loss / 100, FROM_CUR)})
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
            st.info("Xtra locks in the rate and delivers in under a minute, so your family "
                    "is not exposed to days of exchange-rate moves.")

            with st.expander("How we calculate this"):
                st.write(
                    "- **Volatility**: standard deviation of daily rate changes over 90 days, "
                    "scaled to a year (× √252 working days).\n"
                    "- **Risk level**: Low below 5% a year, Medium 5–10%, High above 10%.\n"
                    "- **Bad day (1 in 20)**: historical 95% Value at Risk of a one-day move.\n"
                    "- **Possible rate loss**: 1.645 × daily volatility × √(days travelling).\n"
                    "- Data: daily rates from the open-source fawazahmed0 currency API."
                )

st.divider()
st.caption("Demo only: no real money is sent and all bank details shown are fictional. "
           "Exchange rates are live; Xtra's own fees are sample values.")
