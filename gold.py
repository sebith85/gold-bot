import requests
import pandas as pd
import ta
import time
import json

# ==============================
# 🔐 TELEGRAM
# ==============================
TOKEN = "8506732864:AAEhU8kP_h6-n-1NmsazGRtOpzah9seNePM"
CHAT_ID = "7162708521"

def send_message(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text}
    try:
        r = requests.post(url, data=data)
        print("📩", r.text)
    except:
        print("❌ Telegram Error")

# ==============================
# 🧠 MEMORY
# ==============================
last_signal = ""
last_trade_time = 0
cooldown = 300  # 5 min

wins = 0
losses = 0
active_trade = None

send_message("🚀 PRO BOT STARTED")

# ==============================
# 🔁 LOOP
# ==============================
while True:
    try:
        print("🚀 Running...")

        # ==============================
        # 📊 PRICE
        # ==============================
        data = requests.get("https://api.gold-api.com/price/XAU").json()
        price = float(data["price"]) / 2

        # ==============================
        # 📈 HISTORY
        # ==============================
        hist = requests.get("https://api.gold-api.com/price/XAU?days=50").json()
        prices = [i["price"]/2 for i in hist.get("prices", [])]

        if len(prices) < 30:
            prices = [2300,2310,2320,2330,2340,2350,2360]

        prices.append(price)
        df = pd.DataFrame(prices, columns=["close"])

        # ==============================
        # 📊 INDICATORS
        # ==============================
        df["ema200"] = df["close"].ewm(span=200).mean()
        df["ema50"] = df["close"].ewm(span=50).mean()
        df["ema20"] = df["close"].ewm(span=20).mean()
        df["ema5"] = df["close"].ewm(span=5).mean()

        df["rsi"] = ta.momentum.RSIIndicator(df["close"]).rsi()

        macd = ta.trend.MACD(df["close"])
        df["macd"] = macd.macd()
        df["macd_signal"] = macd.macd_signal()

        df["vol"] = df["close"].rolling(5).std()

        # ==============================
        # 🧠 VALUES
        # ==============================
        last = df.iloc[-1]

        ema200 = last["ema200"]
        ema50 = last["ema50"]
        ema20 = last["ema20"]
        ema5 = last["ema5"]

        rsi = last["rsi"]
        if pd.isna(rsi):
            rsi = 50

        macd_val = last["macd"]
        macd_sig = last["macd_signal"]

        vol = last["vol"]
        if pd.isna(vol):
            vol = 1

        # ==============================
        # 🧠 LOGIC
        # ==============================
        score = 0

        if price > ema200:
            trend = "UP"
            score += 2
        else:
            trend = "DOWN"
            score -= 2

        score += 1 if ema50 > ema200 else -1
        score += 1 if ema5 > ema20 else -1

        if rsi > 60:
            score += 1
        elif rsi < 40:
            score -= 1

        score += 1 if macd_val > macd_sig else -1

        # LESS STRICT FILTER (more signals)
        if score >= 3:
            signal = "BUY"
        elif score <= -3:
            signal = "SELL"
        else:
            signal = "WAIT"

        # ==============================
        # 🎯 SL / TP
        # ==============================
        sl_points = max(5, vol)   # tighter
        tp_points = sl_points * 2

        if signal == "BUY":
            entry = price
            sl = price - sl_points
            tp = price + tp_points
        elif signal == "SELL":
            entry = price
            sl = price + sl_points
            tp = price - tp_points
        else:
            entry = sl = tp = 0

        # ==============================
        # 💾 SAVE FILE
        # ==============================
        with open("signal.json", "w") as f:
            json.dump({
                "signal": signal,
                "price": price,
                "entry": entry,
                "sl": sl,
                "tp": tp
            }, f)

        # ==============================
        # 🚀 TELEGRAM SIGNAL
        # ==============================
        now = time.time()

        if signal != "WAIT" and signal != last_signal and (now - last_trade_time > cooldown):

            rr = round(tp_points / sl_points, 2)
            confidence = min(100, abs(score) * 20)

            message = f"""🔥 PRO GOLD SIGNAL 🔥

📊 Type: {signal}
📈 Trend: {trend}
⭐ Score: {score}
💰 Entry: {entry:.2f}
🛑 SL: {sl:.2f}
🎯 TP: {tp:.2f}
⚖️ RR: 1:{rr}
📉 RSI: {rsi:.2f}
📊 Volatility: {vol:.2f}
🧠 Confidence: {confidence}%
"""

            send_message(message)

            active_trade = {
                "signal": signal,
                "entry": entry,
                "sl": sl,
                "tp": tp,
                "breakeven": False
            }

            last_signal = signal
            last_trade_time = now

        # ==============================
        # 🧠 TRADE MANAGEMENT
        # ==============================
        if active_trade:

            if active_trade["signal"] == "BUY":

                if price > active_trade["entry"] + 5 and not active_trade["breakeven"]:
                    active_trade["sl"] = active_trade["entry"]
                    active_trade["breakeven"] = True
                    send_message("🔒 BREAK EVEN")

                if price > active_trade["entry"] + 10:
                    active_trade["sl"] = price - 5

                if price >= active_trade["tp"]:
                    wins += 1
                    send_message("✅ TP HIT")
                    active_trade = None

                elif price <= active_trade["sl"]:
                    losses += 1
                    send_message("❌ SL HIT")
                    active_trade = None

            elif active_trade["signal"] == "SELL":

                if price < active_trade["entry"] - 5 and not active_trade["breakeven"]:
                    active_trade["sl"] = active_trade["entry"]
                    active_trade["breakeven"] = True
                    send_message("🔒 BREAK EVEN")

                if price < active_trade["entry"] - 10:
                    active_trade["sl"] = price + 5

                if price <= active_trade["tp"]:
                    wins += 1
                    send_message("✅ TP HIT")
                    active_trade = None

                elif price >= active_trade["sl"]:
                    losses += 1
                    send_message("❌ SL HIT")
                    active_trade = None

            with open("stats.json", "w") as f:
                json.dump({"wins": wins, "losses": losses}, f)

        print(f"{signal} | Score:{score} | Wins:{wins} | Loss:{losses}")

    except Exception as e:
        print("❌ Error:", e)

    time.sleep(60)