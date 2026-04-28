import streamlit as st
import yfinance as yf
from google import genai
import requests
import base64
from datetime import datetime, time
import plotly.graph_objects as go
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pytz

st.set_page_config(
    page_title="Master Trading Agent",
    page_icon="🧠",
    layout="wide"
)

st.markdown('<meta http-equiv="refresh" content="1800">', unsafe_allow_html=True)

uk_tz = pytz.timezone('Europe/London')
uk_now = datetime.now(uk_tz)

st.title("🧠 Master Trading Agent")
st.caption(f"Last updated: {uk_now.strftime('%d/%m/%Y %H:%M:%S')} (UK time)")
st.caption("⏱️ Auto refreshes every 30 minutes — Managing all specialist agents")
st.progress(1.0)

market_open = time(8, 0)
market_close = time(16, 30)
current_time = uk_now.time()
is_weekday = uk_now.weekday() < 5

if is_weekday and market_open <= current_time <= market_close:
    st.success("🟢 Market is OPEN — Live data active")
else:
    st.warning("🔴 Market is CLOSED — Showing last closing prices")

T212_API_KEY = st.secrets["T212_API_KEY"]
T212_API_SECRET = st.secrets["T212_API_SECRET"]
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
GMAIL_ADDRESS = st.secrets["GMAIL_ADDRESS"]
GMAIL_APP_PASSWORD = st.secrets["GMAIL_APP_PASSWORD"]
ALERT_EMAIL = st.secrets["ALERT_EMAIL"]
TELEGRAM_BOT_TOKEN = st.secrets["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]

client = genai.Client(api_key=GEMINI_API_KEY)
credentials = f"{T212_API_KEY}:{T212_API_SECRET}"
encoded = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
t212_headers = {"Authorization": f"Basic {encoded}"}
BASE_URL = "https://live.trading212.com/api/v0"

def safe_change(current, open_price):
    if open_price and open_price > 0:
        return ((current - open_price) / open_price) * 100
    return 0.0

def send_telegram(message, bot_token, chat_id):
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        response = requests.post(url, json=payload)
        return response.status_code == 200
    except Exception:
        return False

def send_morning_briefing_email(briefing_text, signals, gmail_address, gmail_password, alert_emails):
    try:
        recipients = [email.strip() for email in alert_emails.split(',')]
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"🧠 Master Agent Morning Briefing — {uk_now.strftime('%d/%m/%Y')}"
        msg['From'] = gmail_address
        msg['To'] = ', '.join(recipients)
        body = f"""
🧠 MASTER TRADING AGENT — MORNING BRIEFING
{uk_now.strftime('%d/%m/%Y %H:%M')} (UK Time)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MARKET SNAPSHOT:
{signals}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

AI MASTER ANALYSIS:
{briefing_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This is an automated briefing from your Master Trading Agent.
This is not financial advice. All decisions are yours to make.
        """
        msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(gmail_address, gmail_password)
        server.sendmail(gmail_address, recipients, msg.as_string())
        server.quit()
        return True
    except Exception:
        return False

def get_asset_data(ticker, name, is_gold=False):
    try:
        stock = yf.Ticker(ticker)
        history = stock.history(period="3mo")
        info = stock.info
        if history.empty:
            return None
        history['MA20'] = history['Close'].rolling(window=20).mean()
        history['MA50'] = history['Close'].rolling(window=50).mean()
        current_price = history['Close'].iloc[-1]
        ma20 = history['MA20'].iloc[-1]
        ma50 = history['MA50'].iloc[-1]
        avg_volume = history['Volume'].mean()
        current_volume = history['Volume'].iloc[-1]
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
        week52_high = history['High'].max()
        week52_low = history['Low'].min()
        distance_from_52high = ((current_price - week52_high) / week52_high) * 100
        distance_from_52low = ((current_price - week52_low) / week52_low) * 100
        open_price = info.get('open', 0)
        todays_change = safe_change(current_price, open_price)
        position = ((current_price - week52_low) / (week52_high - week52_low)) * 100
        currency = "$" if is_gold else "£"
        above_below = "above" if current_price > ma20 else "below"
        dividend_yield = info.get('dividendYield', 0)
        target_price = info.get('targetMeanPrice', 0)
        return {
            "name": name,
            "ticker": ticker,
            "price": current_price,
            "change": todays_change,
            "position": position,
            "ma20": ma20,
            "ma50": ma50,
            "volume_ratio": volume_ratio,
            "distance_from_52high": distance_from_52high,
            "distance_from_52low": distance_from_52low,
            "week52_high": week52_high,
            "week52_low": week52_low,
            "currency": currency,
            "above_below": above_below,
            "dividend_yield": dividend_yield,
            "target_price": target_price,
            "is_gold": is_gold
        }
    except Exception:
        return None

st.subheader("💼 Your Trading 212 Account")
try:
    response = requests.get(f"{BASE_URL}/equity/account/cash", headers=t212_headers)
    if response.status_code == 200:
        cash = response.json()
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Free Cash Available", f"£{cash.get('free', 0):,.2f}")
        with col2:
            st.metric("Account Status", "✅ Connected")
        with col3:
            st.metric("Agents Active", "5 🤖")
    else:
        st.error(f"Trading 212 connection failed: {response.status_code}")
except Exception as e:
    st.error(f"Error connecting to Trading 212: {e}")

st.divider()

st.subheader("📊 Full Market Snapshot")
st.caption("All assets monitored by your specialist agents")

assets = [
    ("BT-A.L", "📡 BT Group", False),
    ("VOD.L", "📱 Vodafone", False),
    ("LLOY.L", "🏦 Lloyds", False),
    ("LGEN.L", "💰 Legal & General", False),
    ("NG.L", "⚡ National Grid", False),
    ("GC=F", "🥇 Gold", True),
]

asset_data = []
signals_text = ""

with st.spinner("Fetching all asset data..."):
    for ticker, name, is_gold in assets:
        data = get_asset_data(ticker, name, is_gold)
        if data:
            asset_data.append(data)

for d in asset_data:
    change_icon = "📈" if d['change'] > 0 else "📉"
    if d['position'] >= 80:
        position_icon = "🔴"
        position_comment = "Near yearly high"
    elif d['position'] <= 30:
        position_icon = "🟢"
        position_comment = "Near yearly low — watch for opportunity"
    else:
        position_icon = "🟡"
        position_comment = "Mid range"

    if d['change'] >= 10 or d['change'] <= -10:
        alert_icon = "🔴"
    elif d['change'] >= 5 or d['change'] <= -5:
        alert_icon = "🟠"
    elif d['change'] >= 3 or d['change'] <= -3:
        alert_icon = "🟡"
    else:
        alert_icon = "🟢"

    col1, col2, col3, col4 = st.columns([2, 1, 1, 2])
    with col1:
        st.markdown(f"**{d['name']}**")
    with col2:
        st.markdown(f"{change_icon} {d['currency']}{d['price']:.2f} ({d['change']:+.2f}%)")
    with col3:
        st.markdown(f"{position_icon} {d['position']:.0f}% of range")
    with col4:
        st.markdown(f"📊 Price {d['above_below']} 20day avg | {alert_icon} Alert")

    signals_text += (
        f"{d['name']}: {d['currency']}{d['price']:.2f} ({d['change']:+.2f}%) | "
        f"{d['position']:.0f}% of 52wk range | "
        f"Price {d['above_below']} 20day average\n"
    )

st.divider()

st.subheader("🧠 Master AI Analysis")
st.caption("Synthesising signals from all specialist agents")

master_analysis = ""

with st.spinner("Master Agent analysing all assets..."):
    master_prompt = (
        "You are a Master Trading Agent overseeing a portfolio of specialist agents. "
        "You are supporting a retail investor who prefers buying dips and selling when in profit. "
        "The investor trades UK stocks and Gold on Trading 212 ISA. "
        "Here is the current data from all specialist agents:\n\n"
    )

    for d in asset_data:
        master_prompt += (
            f"{d['name']} ({d['ticker']}): "
            f"Price {d['currency']}{d['price']:.2f} ({d['change']:+.2f}% today) | "
            f"20day avg: {d['currency']}{d['ma20']:.2f} | "
            f"Price is {d['above_below']} average | "
            f"{d['position']:.0f}% of 52wk range | "
            f"Volume: {d['volume_ratio']:.2f}x normal"
        )
        if not d['is_gold'] and d['target_price']:
            master_prompt += f" | Analyst target: {d['currency']}{d['target_price']:.2f}"
        if not d['is_gold'] and d['dividend_yield']:
            master_prompt += f" | Dividend: {d['dividend_yield']:.2f}%"
        master_prompt += "\n"

    master_prompt += (
        "\nBased on all this data please provide:\n"
        "1. BEST OPPORTUNITY TODAY: Which single asset looks most attractive and why\n"
        "2. AVOID TODAY: Which asset looks most risky or extended\n"
        "3. OVERALL MARKET MOOD: One sentence on the general market feeling\n"
        "4. KEY THING TO WATCH: One specific level or event across all assets\n"
        "5. SUMMARY: Two sentence plain English summary for a retail investor\n"
        "Keep it under 200 words, plain English, no jargon."
    )

    try:
        ai_response = client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=master_prompt
        )
        master_analysis = ai_response.text
        st.info(master_analysis)

    except Exception:
        st.warning("⏳ AI analysis temporarily unavailable — will resume shortly")

st.divider()

st.subheader("📬 Send Briefing")
st.caption("Send the current master analysis to your devices")

col1, col2 = st.columns(2)

with col1:
    if st.button("📧 Send Email Briefing"):
        if master_analysis:
            sent = send_morning_briefing_email(
                master_analysis, signals_text,
                GMAIL_ADDRESS, GMAIL_APP_PASSWORD, ALERT_EMAIL
            )
            if sent:
                st.success("✅ Email briefing sent!")
            else:
                st.warning("❌ Could not send email")
        else:
            st.warning("⏳ Wait for AI analysis to complete first")

with col2:
    if st.button("📱 Send Telegram Briefing"):
        if master_analysis:
            telegram_msg = (
                f"🧠 <b>Master Trading Agent</b>\n"
                f"📅 {uk_now.strftime('%d/%m/%Y %H:%M')} (UK Time)\n\n"
                f"📊 <b>Market Snapshot:</b>\n"
            )
            for d in asset_data:
                change_icon = "📈" if d['change'] > 0 else "📉"
                telegram_msg += (
                    f"{change_icon} {d['name']}: "
                    f"{d['currency']}{d['price']:.2f} ({d['change']:+.2f}%)\n"
                )
            telegram_msg += f"\n🧠 <b>Master Analysis:</b>\n{master_analysis}"
            telegram_msg += "\n\n⚠️ Not financial advice."

            sent = send_telegram(telegram_msg, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
            if sent:
                st.success("✅ Telegram briefing sent! Check your phone 📱")
            else:
                st.warning("❌ Could not send Telegram message")
        else:
            st.warning("⏳ Wait for AI analysis to complete first")

st.divider()

st.subheader("📈 Comparative Price Chart")
st.caption("90 day performance — normalised to 100 for comparison")

if asset_data:
    fig = go.Figure()
    colors = ['#00BFFF', '#FF6B6B', '#FFD700', '#90EE90', '#DDA0DD', '#FFA500']
    for i, d in enumerate(asset_data):
        try:
            stock = yf.Ticker(d['ticker'])
            hist = stock.history(period="3mo")
            if not hist.empty:
                normalised = (hist['Close'] / hist['Close'].iloc[0]) * 100
                fig.add_trace(go.Scatter(
                    x=hist.index,
                    y=normalised,
                    name=d['name'],
                    line=dict(color=colors[i], width=2)
                ))
        except Exception:
            pass

    fig.update_layout(
        height=400,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)',
                   title="Performance (Base 100)"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02)
    )
    st.plotly_chart(fig, use_container_width=True)

st.divider()

st.subheader("🔗 Your Specialist Agents")
st.caption("Click to open each specialist agent dashboard")

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("📡 [Telecoms Agent](https://bt-trading-agent.streamlit.app)")
    st.markdown("🏦 [Banking Agent](https://banking-trading-agent.streamlit.app)")
with col2:
    st.markdown("💰 [Finance Agent](https://finance-trading-agent.streamlit.app)")
    st.markdown("⚡ [Utilities Agent](https://utilities-trading-agent.streamlit.app)")
with col3:
    st.markdown("🥇 [Commodities Agent](https://commodities-trading-agent.streamlit.app)")

st.divider()
st.caption("⚠️ This tool is for informational purposes only and does not constitute financial advice.")
