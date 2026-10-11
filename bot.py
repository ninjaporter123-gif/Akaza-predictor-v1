import datetime
import http.server
import random
import socketserver
import threading
import time
from decimal import Decimal, getcontext
import requests

getcontext().prec = 50

# ----------------- RENDER PORT BINDING -----------------
class HealthHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"CTG Gaming Prediction Bot Live 24/7!")

    def log_message(self, format, *args):
        pass

def start_server():
    try:
        with socketserver.TCPServer(("", 8080), HealthHandler) as server:
            server.serve_forever()
    except Exception as e:
        print("[PORT ERROR]", e)

threading.Thread(target=start_server, daemon=True).start()
# --------------------------------------------------------

API_URL = "https://draw.ar-lottery01.com/WinGo/WinGo_1M/GetHistoryIssuePage.json"
BOT_TOKEN = "8662159068:AAGzjW3kf6ZPGft8SgfOje6s0APG4RL3WzU"
CHAT_ID = "-1004446531098"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
}

FIXED_DIVIDEND = 2738
SECRET_KEY = "777"

bot_state = {
    "is_active": False,
    "target_wins": 0,
    "total_predictions": 0,
    "total_wins": 0,
    "total_num_wins": 0,
    "current_level": 1,
    "max_level": 1,
    "scheduled_time": None,
    "scheduled_target": 0
}

current_target_period = None
current_predicted_size = None
current_predicted_hot_nums = []
published_predictions = set()
evaluated_periods = set()
recent_numbers_cache = [7, 3, 8, 1, 9, 4]
dispatch_lock = threading.Lock()

def send_telegram(text, target_chat=CHAT_ID):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": target_chat, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=8)
    except Exception as e:
        print("[TG EXP]", e)

def calculate_prediction(numbers_list):
    try:
        latest_num = numbers_list[0]
        count_to_take = 5 if (latest_num % 2 != 0) else 6
        selected_numbers = numbers_list[:count_to_take]

        concat_str = "".join(str(n) for n in selected_numbers)
        divisor = int(concat_str) if int(concat_str) != 0 else 1

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
        return "BIG", 7, 2, "27380000000000000078", [7, 8], "Algorithm Auto"

def fetch_live_data():
    global recent_numbers_cache
    try:
        resp = requests.get(API_URL, params={"pageNo": 1, "pageSize": 10}, headers=HEADERS, timeout=6)
        if resp.status_code == 200:
            res_data = resp.json()
            data_list = res_data.get("data", {}).get("list", []) or res_data.get("list", [])
            if data_list and len(data_list) >= 6:
                recent_numbers_cache = [int(item.get("number", 0)) for item in data_list[:6]]
                issue = int(data_list[0].get("issueNumber") or data_list[0].get("period"))
                num = int(data_list[0].get("number"))
                return issue, num
    except Exception as e:
        print("[API FAIL]", e)

    now_dt = datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)
    minute_idx = now_dt.hour * 60 + now_dt.minute
    pseudo_issue = int(now_dt.strftime("%Y%m%d") + str(minute_idx).zfill(4))
    sim_num = random.randint(0, 9)
    recent_numbers_cache.insert(0, sim_num)
    recent_numbers_cache = recent_numbers_cache[:6]
    return pseudo_issue, sim_num

def emit_prediction_card(target_iss):
    global current_target_period, current_predicted_size, current_predicted_hot_nums
    with dispatch_lock:
        if target_iss in published_predictions:
            return
        published_predictions.add(target_iss)

        pred, chosen_digit, count, dec_str, lucky_nums, reason = calculate_prediction(recent_numbers_cache)
        current_target_period = target_iss
        current_predicted_size = pred
        current_predicted_hot_nums = lucky_nums
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
            f"  🎯 *TARGET ISSUE* : `#{str(target_iss)[-4:]}`\n\n"
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
    if bot_state["is_active"]:
        return
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
    time.sleep(1)

    curr_iss, _ = fetch_live_data()
    emit_prediction_card(curr_iss + 1)

def stop_bot_session():
    if bot_state["is_active"]:
        bot_state["is_active"] = False
        send_session_closed_summary()
    else:
        bot_state["scheduled_time"] = None

def telegram_listener():
    last_update_id = 0
    try:
        init_res = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset=-1", timeout=8).json()
        results = init_res.get("result", [])
        if results:
            last_update_id = results[-1]["update_id"]
    except Exception:
        pass

    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
            params = {"offset": last_update_id + 1, "timeout": 10}
            resp = requests.get(url, params=params, timeout=15).json()
            
            for update in resp.get("result", []):
                last_update_id = update["update_id"]
                msg_obj = update.get("message", {})
                chat_id = str(msg_obj.get("chat", {}).get("id"))
                msg = msg_obj.get("text", "").strip()
                if not msg or chat_id == CHAT_ID:
                    continue

                parts = msg.split()
                cmd = parts[0].lower()

                if cmd in ["/start", "start"]:
                    if len(parts) >= 2 and parts[1] == SECRET_KEY:
                        target = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
                        if not bot_state["is_active"]:
                            send_telegram(f"✅ Bot started with {target if target>0 else '24/7'} wins target!", chat_id)
                            start_bot_session(target)
                        else:
                            send_telegram("⚠️ Session already in progress!", chat_id)
                    else:
                        send_telegram("🔒 Access Denied! Please provide valid secret code.", chat_id)

                elif cmd in ["/stop", "stop"]:
                    if len(parts) >= 2 and parts[1] == SECRET_KEY:
                        stop_bot_session()
                        send_telegram("🛑 *Bot Stopped Successfully!*", chat_id)
                    else:
                        send_telegram("🔒 Invalid Code!", chat_id)

                elif cmd in ["/schedule", "schedule"]:
                    if len(parts) >= 3 and parts[1] == SECRET_KEY:
                        time_part = parts[2]
                        h, m = map(int, time_part.split(":"))
                        target = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
                        bot_state["scheduled_time"] = (h, m)
                        bot_state["scheduled_target"] = target
                        bot_state["is_active"] = False
                        send_telegram(f"⏰ *SCHEDULE SET!*\nBot will start at *{time_part} IST* with target *{target if target>0 else '24/7'} wins*.", chat_id)

        except Exception as e:
            time.sleep(2)
        time.sleep(1)

threading.Thread(target=telegram_listener, daemon=True).start()

# Main Round Loop
while True:
    try:
        if not bot_state["is_active"] and bot_state["scheduled_time"]:
            now_utc = datetime.datetime.utcnow()
            now_ist = now_utc + datetime.timedelta(hours=5, minutes=30)
            sh, sm = bot_state["scheduled_time"]
            if now_ist.hour == sh and now_ist.minute == sm:
                start_bot_session(bot_state["scheduled_target"])

        if bot_state["is_active"]:
            curr_issue, result_num = fetch_live_data()
            actual_size = "BIG" if result_num >= 5 else "SMALL"

            if current_target_period and curr_issue >= current_target_period and current_target_period not in evaluated_periods:
                evaluated_periods.add(current_target_period)
                is_size_win = (current_predicted_size == actual_size)
                is_number_hit = (result_num in current_predicted_hot_nums)

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
                    level_desc = f"✨ *CLEARED AT LEVEL : {cleared}*"
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
                    f"  🎯 *PERIOD* : `#{str(current_target_period)[-4:]}`\n"
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
                else:
                    time.sleep(1)
                    emit_prediction_card(curr_issue + 1)

    except Exception as e:
        print("[CYCLE EXP]", e)

    time.sleep(5)
        
