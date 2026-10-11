import sys
import time
from collections import Counter
from decimal import Decimal, getcontext
import requests

getcontext().prec = 50

# Target wins from command line: 0 means unlimited
target_wins = 0
if len(sys.argv) > 1:
    try:
        target_wins = int(sys.argv[1])
    except ValueError:
        target_wins = 0

API_URL = "https://draw.ar-lottery01.com/WinGo/WinGo_1M/GetHistoryIssuePage.json"
BOT_TOKEN = "8662159068:AAFhMvrJUVC1Sj4EG8rVDkuJhAXvtT5PYq8"
CHAT_ID = "-1004446531098"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Content-Type": "application/json;charset=UTF-8",
    "Accept": "application/json, text/plain, */*",
}

last_processed_issue = None
previous_prediction = None
previous_lucky_nums = []
target_issue = None
current_level = 1
max_level_reached = 1

# Session Analytics
total_predictions_given = 0
total_wins_count = 0
total_number_wins = 0

FIXED_DIVIDEND = 2738


def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print("Telegram Connection Error:", e)


def calculate_prediction(history_list):
    try:
        latest_num = int(history_list[0].get("number"))

        # Odd aithe 5 results, Even aithe 6 results
        count_to_take = 5 if (latest_num % 2 != 0) else 6
        selected_numbers = [
            int(item.get("number")) for item in history_list[:count_to_take]
        ]

        concat_str = "".join(str(n) for n in selected_numbers)
        divisor = int(concat_str)
        if divisor == 0:
            divisor = 1

        division_val = Decimal(FIXED_DIVIDEND) / Decimal(divisor)
        decimal_parts = str(division_val).split(".")

        decimal_str = (
            decimal_parts[1][:20]
            if len(decimal_parts) > 1
            else "00000000000000000000"
        )
        if len(decimal_str) < 20:
            decimal_str = decimal_str.ljust(20, "0")

        # 20 decimals lo last 2 digits
        d1 = decimal_str[-2]
        d2 = decimal_str[-1]
        n1 = int(d1)
        n2 = int(d2)

        size1 = "BIG" if n1 >= 5 else "SMALL"
        size2 = "BIG" if n2 >= 5 else "SMALL"

        # Rendu same size aithe direct ga adhe decision
        if size1 == size2:
            pred = size1
            chosen_digit = n1
            chosen_count = decimal_str.count(d1)
            reason = f"Both {size1}"
        else:
            # Okati BIG mariyu okati SMALL aithe 20 decimals lo majority check
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
        print("Calculation Error:", e)
        return "BIG", 5, 1, "00000000000000000000", [5, 7], "Fallback"


def send_session_closed_summary():
    # Message NO :- 1
    msg_1 = (
        f"┏━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
        f"  📊 *DETAILS OF COMPLETED PREDICTION* \n"
        f"┗━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"  🎯 *Total Prediction Given*   : *{total_predictions_given}*\n"
        f"  🏆 *Total Wins Achieved*      : *{total_wins_count}*\n"
        f"  🎲 *Total Number Wins (Hits)* : *{total_number_wins}*\n"
        f"  🔥 *Highest Level Crossed*     : *Level {max_level_reached}*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"  👑 *Prediction Completed by* : *@Gara00077*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    send_telegram(msg_1)
    time.sleep(1)

    # Message NO :- 2
    msg_2 = (
        f"╔══════════════════════════╗\n"
        f"   ❌  *𝐒𝐄𝐒𝐒𝐈𝐎𝐍 𝐂𝐋𝐎𝐒𝐄𝐃*  🔒\n"
        f"╚══════════════════════════╝\n\n"
        f"  🛑 *Target Achieved Successfully!*\n"
        f"  💰 *Enjoy Your Profits & Rest Now!*"
    )
    send_telegram(msg_2)


def check_and_process():
    global last_processed_issue, previous_prediction, previous_lucky_nums
    global target_issue, current_level, max_level_reached
    global total_predictions_given, total_wins_count, total_number_wins

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
                # 1. Result Verification Card
                if target_issue and current_issue == target_issue:
                    is_size_win = previous_prediction == actual_size
                    is_number_hit = result_num in previous_lucky_nums

                    if is_size_win or is_number_hit:
                        total_wins_count += 1
                        if is_number_hit:
                            total_number_wins += 1
                            status_badge = "🎰 *✦ J A C K P O T   W I N ✦* 🎰"
                            status_tag = (
                                f"🎯 *DIRECT NUMBER HIT ({result_num})*"
                            )
                        else:
                            status_badge = "🏆 *✦ W I N N E R ✦* 🏆"
                            status_tag = "✅ *WIN PASSED*"

                        level_cleared = current_level
                        current_level = 1
                        level_desc = f"✨ *CLEARED AT LEVEL : {level_cleared}*"
                    else:
                        status_badge = "💀 *✦ L O S S ✦* 💀"
                        status_tag = "❌ *FAILED*"
                        current_level += 1
                        if current_level > max_level_reached:
                            max_level_reached = current_level
                        level_desc = f"⚠️ *RECOVERY LEVEL : {current_level}*"

                    target_status_text = (
                        f"🎯 *TARGET GOAL* : *{total_wins_count}/{target_wins} WINS*\n"
                        if target_wins > 0
                        else ""
                    )

                    result_card = (
                        f"┏━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                        f"     {status_badge}\n"
                        f"┗━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                        f"  🎯 *PERIOD* : `#{str(current_issue)[-4:]}`\n"
                        f"  🎲 *WINNING* : `NUM {result_num}` *({actual_size})*\n"
                        f"  📊 *STATUS* : {status_tag}\n"
                        f"  🔥 *STAGE* : {level_desc}\n"
                        f"  ⚡ *MAX RECORD* : *LEVEL {max_level_reached}*\n"
                        f"{target_status_text}\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"  👑 *CTG GAMING PREDICTION*"
                    )
                    send_telegram(result_card)

                    if target_wins > 0 and total_wins_count >= target_wins:
                        print(
                            f"[TARGET REACHED] {total_wins_count} wins completed. Stopping..."
                        )
                        send_session_closed_summary()
                        return False

                last_processed_issue = current_issue

                # 2. Next Round Prediction
                target_issue = current_issue + 1

                (
                    pred,
                    chosen_digit,
                    count,
                    dec_str,
                    lucky_nums,
                    decision_reason,
                ) = calculate_prediction(data_list)

                previous_prediction = pred
                previous_lucky_nums = lucky_nums

                total_predictions_given += 1

                if current_level > max_level_reached:
                    max_level_reached = current_level

                pred_display = (
                    "🟢 *BIG [ 5 - 9 ]*"
                    if pred == "BIG"
                    else "🔴 *SMALL [ 0 - 4 ]*"
                )

                win_target_header = (
                    f"  🏁 *WIN PROGRESS* : *{total_wins_count}/{target_wins}*\n"
                    if target_wins > 0
                    else ""
                )

                signal_msg = (
                    f"┏━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                    f"   👑 *CTG GAMING PREDICTION* 👑\n"
                    f"┗━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                    f"  🎮 *SERVER* : *WINGO 1 MIN [VIP]*\n"
                    f"  🎯 *TARGET ISSUE* : `#{str(target_issue)[-4:]}`\n\n"
                    f"  🔮 *PREDICTION* : {pred_display}\n"
                    f"  🎲 *HOT NUMBERS* : `{lucky_nums[0]}` *&* `{lucky_nums[1]}`\n\n"
                    f"  📊 *CHOSEN DIGIT* : `{chosen_digit}` *(Repeated {count}x - {decision_reason})*\n"
                    f"  🔢 *DECIMAL (20D)* : `0.{dec_str[:10]}...{dec_str[-2:]}`\n\n"
                    f"  ⚡ *CURRENT LEVEL  : {current_level}*\n"
                    f"  🔥 *MAX LEVEL REACHED : {max_level_reached}*\n"
                    f"{win_target_header}"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"  📩 *OFFICIAL HELP* : *@Gara00077*\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━"
                )

                send_telegram(signal_msg)
                print(f"[SUCCESS] Result checked & Signal sent: {target_issue}")

    except Exception as e:
        print("API Fetch Error:", e)

    return True


mode_str = f"{target_wins} Wins Session" if target_wins > 0 else "Unlimited 24/7"
print(f"🚀 CTG Gaming Bot Started ({mode_str})...")

while True:
    is_running = check_and_process()
    if not is_running:
        break
    time.sleep(5)
    
