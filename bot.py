import os
import threading
import time
from collections import Counter
from decimal import Decimal, getcontext
from flask import Flask
import requests

getcontext().prec = 35

API_URL = "https://draw.ar-lottery01.com/WinGo/WinGo_1M/GetHistoryIssuePage.json"
BOT_TOKEN = "8662159068:AAFhMvrJUVC1Sj4EG8rVDkuJhAXvtT5PYq8"
CHAT_ID = "-1004446531098"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Content-Type": "application/json;charset=UTF-8",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://ar-lottery01.com",
    "Referer": "https://ar-lottery01.com/",
}

app = Flask(__name__)


@app.route("/")
def home():
    return "Bot is alive 24/7!"


last_processed_issue = None
previous_prediction = None
target_issue = None


def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    try:
        res = requests.post(url, json=payload, timeout=10)
        print(
            f"[TELEGRAM LOG] Sent status: {res.status_code}",
            flush=True,
        )
    except Exception as e:
        print(f"[TELEGRAM FAIL] {e}", flush=True)


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
        print(f"Calc Error: {e}", flush=True)
        return "BIG", 5, 1, "000000000000000"


def fetch_lottery_data():
    payload = {
        "pageNo": 1,
        "pageSize": 10,
        "typeId": 1,
        "language": 0,
    }
    # 1. Try POST request (Default for WinGo)
    try:
        res = requests.post(
            API_URL, json=payload, headers=HEADERS, timeout=10
        )
        if res.status_code == 200 and res.text.strip():
            return res.json()
    except Exception:
        pass

    # 2. Fallback to GET request
    try:
        res = requests.get(
            API_URL, params=payload, headers=HEADERS, timeout=10
        )
        if res.status_code == 200 and res.text.strip():
            return res.json()
    except Exception as e:
        print(f"[FETCH ERROR RAW]: {e}", flush=True)

    return None


def bot_worker():
    global last_processed_issue, previous_prediction, target_issue
    print(">>> BOT WORKER THREAD ACTIVE <<<", flush=True)

    send_telegram(
        "🚀 *WinGo 24/7 Server Connected!*\nMonitoring signals..."
    )

    while True:
        try:
            res_data = fetch_lottery_data()

            if not res_data:
                time.sleep(5)
                continue

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
                    print(
                        f"[NEW PERIOD DETECTED]: {current_issue}",
                        flush=True,
                    )

                    # Result verification
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

                    pred, top_digit, count, dec_str = (
                        calculate_prediction(target_issue, last_6_numbers)
                    )
                    previous_prediction = pred
                    pred_display = (
                        "BIG 🟢" if pred == "BIG" else "SMALL 🔴"
                    )

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
            print(f"[LOOP LOGIC ERROR] {e}", flush=True)

        time.sleep(4)


worker_thread = threading.Thread(target=bot_worker)
worker_thread.daemon = True
worker_thread.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
    
