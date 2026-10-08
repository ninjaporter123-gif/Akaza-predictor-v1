import threading
import time
from collections import Counter
from decimal import Decimal, getcontext
from flask import Flask
import requests

# Web server for Render Free Tier Keep-Alive
app = Flask(__name__)


@app.route("/")
def home():
    return "Bot is running 24/7!"


def run_web():
    app.run(host="0.0.0.0", port=10000)


getcontext().prec = 35

API_URL = "https://draw.ar-lottery01.com/WinGo/WinGo_1M/GetHistoryIssuePage.json"
BOT_TOKEN = "8662159068:AAFhMvrJUVC1Sj4EG8rVDkuJhAXvtT5PYq8"
CHAT_ID = "-1004446531098"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    ),
    "Content-Type": "application/json;charset=UTF-8",
    "Accept": "application/json, text/plain, */*",
}

last_processed_issue = None
previous_prediction = None
target_issue = None


def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print("Telegram Connection Error:", e)


def calculate_prediction(next_issue, last_6_numbers):
    try:
        last_4_digits = int(str(next_issue)[-4:])
        sum_of_6 = sum(last_6_numbers)
        if sum_of_6 == 0:
            sum_of_6 = 1

        division_val = Decimal(last_4_digits) / Decimal(sum_of_6)
        decimal_parts = str(division_val).split(".")
        decimal_str = (
            decimal_parts[1][:15]
            if len(decimal_parts) > 1
            else "000000000000000"
        )

        counts = Counter(decimal_str)
        most_common_digit = int(counts.most_common(1)[0][0])
        occurrence_count = counts.most_common(1)[0][1]

        pred = "SMALL" if most_common_digit <= 4 else "BIG"
        return pred, most_common_digit, occurrence_count, decimal_str
    except Exception as e:
        print("Calculation Error:", e)
        return "BIG", 5, 1, "000000000000000"


def bot_loop():
    global last_processed_issue, previous_prediction, target_issue
    while True:
        try:
            response = requests.get(
                API_URL,
                params={"pageNo": 1, "pageSize": 10},
                headers=HEADERS,
                timeout=10,
            )
            res_data = response.json()

            data_list = res_data.get("data", {}).get("list", [])
            if not data_list:
                data_list = res_data.get("list", [])

            if data_list and len(data_list) >= 6:
                latest = data_list[0]
                current_issue = int(
                    latest.get("issueNumber") or latest.get("period")
                )
                result_num = int(latest.get("number"))
                actual_size = "BIG" if result_num >= 5 else "SMALL"

                if current_issue != last_processed_issue:
                    if target_issue and current_issue == target_issue:
                        status_header = (
                            "🎉 ✅ WIN"
                            if previous_prediction == actual_size
                            else "❌ LOSS"
                        )
                        result_card = (
                            f"{status_header}\n"
                            f"============================\n"
                            f"Period  => #{str(current_issue)[-4:]}\n"
                            f"Result  => NUM: {result_num} ({actual_size})\n"
                            f"============================"
                        )
                        send_telegram(result_card)

                    last_processed_issue = current_issue
                    last_6_numbers = [
                        int(item.get("number")) for item in data_list[:6]
                    ]
                    target_issue = current_issue + 1

                    pred, top_digit, count, dec_str = calculate_prediction(
                        target_issue, last_6_numbers
                    )
                    previous_prediction = pred
                    pred_display = "BIG 🟢" if pred == "BIG" else "SMALL 🔴"

                    signal_msg = (
                        f"┏━━━━━━━━━━━━━━━━━┓\n"
                        f"     WINGO 1 MIN PREDICTION\n"
                        f"┗━━━━━━━━━━━━━━━━━┛\n\n"
                        f"👉 PERIOD   -> ( {str(target_issue)[-4:]} )\n\n"
                        f"⚙️ SIGNAL   -> {pred_display}\n\n"
                        f"📊 DIGIT    -> {top_digit} (Count: {count})\n"
                        f"🔢 DECIMAL  -> `0.{dec_str[:8]}...`\n"
                        f"━━━━━━━━━━━━━━━━━━━"
                    )
                    send_telegram(signal_msg)

        except Exception as e:
            print("Fetch Error:", e)

        time.sleep(5)


if __name__ == "__main__":
    t = threading.Thread(target=bot_loop)
    t.daemon = True
    t.start()
    run_web()
                      
