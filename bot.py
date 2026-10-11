import datetime
import http.server
import socketserver
import threading
import time
from decimal import Decimal, getcontext
import requests

getcontext().prec = 50

# ----------------- BACK4APP HEALTH CHECK WEB SERVER -----------------
class HealthHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"CTG Gaming Prediction Bot Running 24/7!")

    def log_message(self, format, *args):
        pass

def run_web_server():
    try:
        with socketserver.TCPServer(("", 8080), HealthHandler) as httpd:
            httpd.serve_forever()
    except Exception as e:
        print("Web server error:", e)

threading.Thread(target=run_web_server, daemon=True).start()
# --------------------------------------------------------------------

API_URL = "https://draw.ar-lottery01.com/WinGo/WinGo_1M/GetHistoryIssuePage.json"
BOT_TOKEN = "8662159068:AAFhMvrJUVC1Sj4EG8rVDkuJhAXvtT5PYq8"
CHAT_ID = "-1004446531098"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Content-Type": "application/json;charset=UTF-8",
    "Accept": "application/json, text/plain, */*",
}

FIXED_DIVIDEND = 2738

bot_state = {
    "is_active": False,
    "target_wins": 0,
    "total_predictions": 0,
    "total_wins": 0,
    "total_num_wins": 0,
    "current_level": 1,
    "max_level": 1,
    "scheduled_time": None, # (hour, minute)
    "scheduled_target": 0
}

last_processed_issue = None
previous_prediction = None
previous_lucky_nums = []
target_issue = None

def send_telegram(text, target_chat=CHAT_ID):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": target_chat, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print("Telegram Send Error:", e)

def calculate_prediction(history_list):
    try:
        latest_num = int(history_list[0].get("number"))
        count_to_take = 5 if (latest_num % 2 != 0) else 6
        selected_numbers = [int(item.get("number")) for item in history_list[:count_to_take]]

        concat_str = "".join(str(n) for n in selected_numbers)
        divisor = int(concat_str)
        if divisor == 0:
            divisor = 1

        division_val = Decimal(FIXED_DIVIDEND) / Decimal(divisor)
        decimal_parts = str(division_val).split(".")
        decimal_str = decimal_parts[1][:20] if len(decimal_parts) > 1 else "00000000000000000000"
        if len(decimal_str) < 20:
            decimal_str = decimal_str.ljust(20, "0")

        d1 = decimal_str[-2]
        d2 = decimal_str[-1]
        n1 = int(d1)
        n2 = int(d2)

        size1 = "BIG" if n1 >= 5 else "SMALL"
        size2 = "BIG" if n2 >= 5 else "SMALL"

        if size1 == size2:
            pred = size1
            chosen_digit = n1
            chosen_count = decimal_str.count(d1)
            reason = f"Both {size1}"
        else:
            c1 = decimal_str.count(d1)
            c2 = decimal_str.count(d2)
            if c1 >= c2:
                chosen_digit = n1
                chosen_count = c1
            else:
                chosen_digit = n2
                chosen_count = c2
            pred = "SMALL" if chosen_digit <= 4 else "BIG"
            reason = f"Majority ({chosen_digit})"

        lucky_nums = [n1, n2]
        return pred, chosen_digit, chosen_count, decimal_str, lucky_nums, reason
    except Exception as e:
        print("Calc Error:", e)
        return "BIG", 5, 1, "00000000000000000000", [5, 7], "Fallback"

def send_session_closed_summary():
    msg_1 = (
        f"┏━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
        f"  📊 *DETAILS OF COMPLETED PREDICTION* \n"
        f"┗━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"  🎯 *Total Prediction Given*   : *{bot_state['total_predictions']}*\n"
        f"  🏆 *Total Wins Achieved*      : *{bot_state['total_wins']}*\n"
        f"  🎲 *Total Number Wins (Hits)* : *{bot_state['total_num_wins']}*\n"
        f"  🔥 *Highest Level Crossed*     : *Level {bot_state['max_level']}*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"  👑 *Prediction Completed by* : *@Gara00077*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    send_telegram(msg_1)
    time.sleep(1)

    msg_2 = (
        f"╔══════════════════════════╗\n"
        f"   ❌  *𝐒𝐄𝐒𝐒𝐈𝐎𝐍 𝐂𝐋𝐎𝐒𝐄𝐃*  🔒\n"
        f"╚══════════════════════════╝\n\n"
        f"  🛑 *Target Achieved Successfully!*\n"
        f"  💰 *Enjoy Your Profits & Rest Now!*"
    )
    send_telegram(msg_2)

def start_bot_session(target):
    bot_state["is_active"] = True
    bot_state["target_wins"] = target
    bot_state["total_predictions"] = 0
    bot_state["total_wins"] = 0
    bot_state["total_num_wins"] = 0
    bot_state["current_level"] = 1
    bot_state["max_level"] = 1
    bot_state["scheduled_time"] = None
    
    mode = f"{target} WINS TARGET" if target > 0 else "UNLIMITED 24/7"
    send_telegram(f"🚀 *CTG BOT STARTED!*\n🎯 Mode: *{mode}*")

def stop_bot_session():
    if bot_state["is_active"]:
        bot_state["is_active"] = False
        send_session_closed_summary()
    else:
        bot_state["scheduled_time"] = None

def telegram_listener():
    last_update_id = 0
    # Clear backlog old messages first
    try:
        init_res = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset=-1", timeout=10).json()
        results = init_res.get("result", [])
        if results:
            last_update_id = results[-1]["update_id"]
    except Exception:
        pass

    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
            params = {"offset": last_update_id + 1, "timeout": 15}
            resp = requests.get(url, params=params, timeout=20).json()
            
            for update in resp.get("result", []):
                last_update_id = update["update_id"]
                msg_obj = update.get("message", {})
                chat_id = msg_obj.get("chat", {}).get("id")
                msg = msg_obj.get("text", "").strip()
                if not msg:
                    continue
                
                parts = msg.split()
                cmd = parts[0].lower()
                
                if cmd in ["/start", "start"]:
                    target = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
                    start_bot_session(target)
                    send_telegram(f"✅ Bot started with {target if target>0 else '24/7'} wins target!", chat_id)

                elif cmd in ["/schedule", "schedule"]:
                    if len(parts) >= 2:
                        time_part = parts[1]
                        h, m = map(int, time_part.split(":"))
                        target = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
                        bot_state["scheduled_time"] = (h, m)
                        bot_state["scheduled_target"] = target
                        bot_state["is_active"] = False
                        send_telegram(f"⏰ *SCHEDULE SET!*\nBot will start at *{time_part} IST* with target *{target if target>0 else '24/7'} wins*.", chat_id)

                elif cmd in ["/stop", "stop"]:
                    stop_bot_session()
                    send_telegram("🛑 *Bot Stopped Successfully!*", chat_id)

        except Exception as e:
            time.sleep(2)
        time.sleep(1)

threading.Thread(target=telegram_listener, daemon=True).start()

# Main Prediction Loop
while True:
    try:
        if not bot_state["is_active"] and bot_state["scheduled_time"]:
            now_utc = datetime.datetime.utcnow()
            now_ist = now_utc + datetime.timedelta(hours=5, minutes=30)
            sh, sm = bot_state["scheduled_time"]
            if now_ist.hour == sh and now_ist.minute == sm:
                start_bot_session(bot_state["scheduled_target"])

        if bot_state["is_active"]:
            resp = requests.get(API_URL, params={"pageNo": 1, "pageSize": 10}, headers=HEADERS, timeout=10).json()
            data_list = resp.get("data", {}).get("list", []) or resp.get("list", [])

            if data_list and len(data_list) >= 6:
                latest = data_list[0]
                current_issue = int(latest.get("issueNumber") or latest.get("period"))
                result_num = int(latest.get("number"))
                actual_size = "BIG" if result_num >= 5 else "SMALL"

                if current_issue != last_processed_issue:
                    if target_issue and current_issue == target_issue:
                        is_size_win = previous_prediction == actual_size
                        is_number_hit = result_num in previous_lucky_nums

                        if is_size_win or is_number_hit:
                            bot_state["total_wins"] += 1
                            if is_number_hit:
                                bot_state["total_num_wins"] += 1
                                status_badge = "🎰 *✦ J A C K P O T   W I N ✦* 🎰"
                                status_tag = f"🎯 *DIRECT NUMBER HIT ({result_num})*"
                            else:
                                status_badge = "🏆 *✦ W I N N E R ✦* 🏆"
                                status_tag = "✅ *WIN PASSED*"

                            cleared = bot_state["current_level"]
                            bot_state["current_level"] = 1
                            level_desc = f"✨ *CLEARED AT LEVEL : {level_cleared}*"
                        else:
                            status_badge = "💀 *✦ L O S S ✦* 💀"
                            status_tag = "❌ *FAILED*"
                            bot_state["current_level"] += 1
                            if bot_state["current_level"] > bot_state["max_level"]:
                                bot_state["max_level"] = bot_state["current_level"]
                            level_desc = f"⚠️ *RECOVERY LEVEL : {bot_state['current_level']}*"

                        target_text = f"🎯 *TARGET GOAL* : *{bot_state['total_wins']}/{bot_state['target_wins']} WINS*\n" if bot_state['target_wins'] > 0 else ""

                        result_card = (
                            f"┏━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                            f"     {status_badge}\n"
                            f"┗━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                            f"  🎯 *PERIOD* : `#{str(current_issue)[-4:]}`\n"
                            f"  🎲 *WINNING* : `NUM {result_num}` *({actual_size})*\n"
                            f"  📊 *STATUS* : {status_tag}\n"
                            f"  🔥 *STAGE* : {level_desc}\n"
                            f"  ⚡ *MAX RECORD* : *LEVEL {bot_state['max_level']}*\n"
                            f"{target_text}"
                            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"  👑 *CTG GAMING PREDICTION*"
                        )
                        send_telegram(result_card)

                        if bot_state["target_wins"] > 0 and bot_state["total_wins"] >= bot_state["target_wins"]:
                            stop_bot_session()

                    last_processed_issue = current_issue

                    if bot_state["is_active"]:
                        target_issue = current_issue + 1
                        pred, chosen_digit, count, dec_str, lucky_nums, reason = calculate_prediction(data_list)
                        previous_prediction = pred
                        previous_lucky_nums = lucky_nums
                        bot_state["total_predictions"] += 1

                        if bot_state["current_level"] > bot_state["max_level"]:
                            bot_state["max_level"] = bot_state["current_level"]

                        pred_display = "🟢 *BIG [ 5 - 9 ]*" if pred == "BIG" else "🔴 *SMALL [ 0 - 4 ]*"
                        win_progress = f"  🏁 *WIN PROGRESS* : *{bot_state['total_wins']}/{bot_state['target_wins']}*\n" if bot_state['target_wins'] > 0 else ""

                        signal_msg = (
                            f"┏━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                            f"   👑 *CTG GAMING PREDICTION* 👑\n"
                            f"┗━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                            f"  🎮 *SERVER* : *WINGO 1 MIN [VIP]*\n"
                            f"  🎯 *TARGET ISSUE* : `#{str(target_issue)[-4:]}`\n\n"
                            f"  🔮 *PREDICTION* : {pred_display}\n"
                            f"  🎲 *HOT NUMBERS* : `{lucky_nums[0]}` *&* `{lucky_nums[1]}`\n\n"
                            f"  📊 *CHOSEN DIGIT* : `{chosen_digit}` *(Repeated {count}x - {reason})*\n"
                            f"  🔢 *DECIMAL (20D)* : `0.{dec_str[:10]}...{dec_str[-2:]}`\n\n"
                            f"  ⚡ *CURRENT LEVEL  : {bot_state['current_level']}*\n"
                            f"  🔥 *MAX LEVEL REACHED : {bot_state['max_level']}*\n"
                            f"{win_progress}"
                            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"  📩 *OFFICIAL HELP* : *@Gara00077*\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━━━━━"
                        )
                        send_telegram(signal_msg)

    except Exception as e:
        print("Loop Error:", e)

    time.sleep(5)
