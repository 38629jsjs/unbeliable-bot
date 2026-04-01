import requests
import time
import random
import json
import os
import websocket
import threading

# ==========================================
# CONFIGURATION
# ==========================================
OWNERS_RAW = os.getenv("OWNERS", "")
OWNER_IDS = [int(i.strip()) for i in OWNERS_RAW.split(",") if i.strip()]

MAIN_TOKEN = os.getenv("MAIN_TOKEN") # Used for .ra search
ALT_TOKEN = os.getenv("ALT_TOKEN")   # The bot's account token

# Temporary list for authorized friends (Resets if bot restarts)
AUTH_USERS = set(OWNER_IDS)
# ==========================================

def search_roulette():
    # Since DMs don't have a 'Guild', we use a fixed Channel ID for roulette search
    # Set this in Koyeb or replace 'ROULETTE_CHANNEL_ID' with your main gambling channel ID
    target_channel = os.getenv("ROULETTE_CHANNEL") 
    url = f"https://discord.com/api/v9/channels/{target_channel}/messages/search?content=landed on"
    headers = {"Authorization": MAIN_TOKEN}
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            msgs = [m[0]['content'].lower() for m in res.json().get('messages', [])[:20]]
            found = [c for m in msgs for c in ["black", "red"] if c in m]
            if not found: return "No recent data found."
            b, r = found.count("black"), found.count("red")
            pick = "black" if r > b else "red"
            return f"Suggest: **{pick.upper()}** ({'High' if abs(r-b) > 2 else 'Low'} confidence)"
        return "Search failed."
    except: return "Error searching."

def bj_logic(my_t, d_u, is_p, count):
    # my_t: Your Total (Aces are 11)
    # d_u: Dealer Upcard (2-11)
    # is_p: Pair (y/n)
    # count: Cards in hand
    
    decision = "hit"
    
    # --- 1. SURRENDER (The "Save Your Money" Pool) ---
    if count == 2:
        if my_t == 16 and d_u in [9, 10, 11]: decision = "surrender"
        elif my_t == 15 and d_u == 10: decision = "surrender"

    # --- 2. SPLIT POOL (The 'y' Logic) ---
    if is_p and count == 2 and decision == "hit":
        if my_t in [16, 22]: decision = "split" # Always 8s/Aces
        elif my_t == 18 and d_u not in [7, 10, 11]: decision = "split" # 9s
        elif my_t == 14 and d_u <= 7: decision = "split" # 7s
        elif my_t == 12 and d_u <= 6: decision = "split" # 6s
        elif my_t == 8 and d_u in [5, 6]: decision = "split" # 4s
        elif my_t in [4, 6] and d_u <= 7: decision = "split" # 2s/3s

    # --- 3. SOFT TOTALS (Hands with an Ace) ---
    if count == 2 and decision == "hit":
        # Soft 13-18 (Ace + 2 thru Ace + 7)
        if 13 <= my_t <= 18 and 4 <= d_u <= 6: decision = "double"
        elif my_t == 18 and d_u in [2, 3, 7, 8]: decision = "stand"
        elif my_t >= 19: decision = "stand"

    # --- 4. DOUBLE DOWN POOL (Aggressive Hard Totals) ---
    if decision == "hit" and count == 2:
        if my_t == 11: decision = "double"
        elif my_t == 10 and d_u <= 9: decision = "double"
        elif my_t == 9 and 3 <= d_u <= 6: decision = "double"

    # --- 5. STAND POOL (Basic Strategy) ---
    if decision == "hit":
        if my_t >= 17: decision = "stand"
        elif 13 <= my_t <= 16 and d_u <= 6: decision = "stand"
        elif my_t == 12 and 4 <= d_u <= 6: decision = "stand"

    # --- 6. PROBABILITY POOL (The Math) ---
    # Dealer Bust Odds: 2(35%), 3(37%), 4(40%), 5(42%), 6(42%), 7(26%), 8(24%), 9(23%), 10(21%), 11(11%)
    bust_odds = {2:35, 3:37, 4:40, 5:42, 6:42, 7:26, 8:24, 9:23, 10:21, 11:11}
    
    # Base calculation
    base_win = 99 if my_t == 21 else (40 + (my_t / 2))
    final_prob = (base_win + bust_odds.get(d_u, 21)) / 2
    
    # Tension Penalty (Card Counting logic)
    # The more cards you have, the less likely you are to get the specific card you need
    tension = (count - 2) * 6
    final_prob -= tension

    return f"Move: **{decision.upper()}** (Win: {max(5, min(99, int(final_prob)))}%)"

def send_dm(channel_id, content):
    url = f"https://discord.com/api/v9/channels/{channel_id}/messages"
    requests.post(url, headers={"Authorization": ALT_TOKEN}, json={"content": content})

def on_message(ws, message):
    data = json.loads(message)
    if data.get("t") == "MESSAGE_CREATE":
        m = data["d"]
        author_id = int(m.get("author", {}).get("id"))
        content = m.get("content", "").lower().strip()
        channel_id = m.get("channel_id")

        # ONLY RESPOND IN DMs
        if m.get("guild_id") is not None:
            return

        # 1. AUTH COMMAND (Owners Only)
        if content.startswith(".auth ") and author_id in OWNER_IDS:
            try:
                new_id = int(content.split(".auth ")[1])
                AUTH_USERS.add(new_id)
                send_dm(channel_id, f"✅ User {new_id} authorized.")
            except: pass
            return

        # 2. CHECK IF AUTHORIZED
        if author_id not in AUTH_USERS:
            return

        # 3. GAME COMMANDS
        if content.startswith(".h "):
            try:
                # Expected format: .h [MyTotal] [DealerUp] [Pair y/n] [CardCount]
                p = content.split(".h ")[1].split(" ")
                res = bj_logic(int(p[0]), int(p[1]), p[2]=='y', int(p[3]))
                send_dm(channel_id, res)
            except: 
                send_dm(channel_id, "❌ Error. Use: `.h [Total] [Dealer] [y/n] [Count]`")
        
        elif content == ".ra":
            send_dm(channel_id, search_roulette())

def run_bot():
    while True:
        try:
            ws = websocket.WebSocketApp("wss://gateway.discord.gg/?v=9&encoding=json", on_message=on_message)
            def on_open(ws):
                auth_payload = {
                    "op": 2,
                    "d": {
                        "token": ALT_TOKEN,
                        "properties": {
                            "$os": "windows",
                            "$browser": "chrome",
                            "$device": ""
                        }
                    }
                }
                ws.send(json.dumps(auth_payload))
            
            ws.on_open = on_open
            ws.run_forever()
        except Exception as e:
            print(f"Connection error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    run_bot()
