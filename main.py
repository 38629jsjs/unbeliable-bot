import requests, time, random, json, re, threading, os

# ==========================================
# CONFIGURATION
# ==========================================
# In Koyeb, set OWNERS to: 123456789,987654321
OWNERS_RAW = os.getenv("OWNERS", "")
OWNER_IDS = [int(i.strip()) for i in OWNERS_RAW.split(",") if i.strip()]

MAIN_TOKEN = os.getenv("MAIN_TOKEN") 
ALT_TOKEN = os.getenv("ALT_TOKEN") 
# ==========================================

# Inside on_message(ws, message):
    data = json.loads(message)
    if data.get("t") == "MESSAGE_CREATE":
        m = data["d"]
        author_id = int(m.get("author", {}).get("id")) # Get the ID as an integer
        
        # 1. SECURITY: Only YOU or your FRIEND can trigger it
        if author_id not in OWNER_IDS: 
            return

def delete_msg(token, channel_id, msg_id, delay):
    time.sleep(delay)
    url = f"https://discord.com/api/v9/channels/{channel_id}/messages/{msg_id}"
    requests.delete(url, headers={"Authorization": token})

def ghost_post(content, channel_id, delete_after=2):
    url = f"https://discord.com/api/v9/channels/{channel_id}/messages"
    headers = {"Authorization": ALT_TOKEN}
    
    # Fast thinking delay
    time.sleep(random.uniform(1.2, 2.0))
    
    res = requests.post(url, headers=headers, json={"content": content.lower()})
    if res.status_code == 200:
        msg_id = res.json()['id']
        threading.Thread(target=delete_msg, args=(ALT_TOKEN, channel_id, msg_id, delete_after)).start()

def typing_signal(channel_id):
    url = f"https://discord.com/api/v9/channels/{channel_id}/typing"
    headers = {"Authorization": ALT_TOKEN}
    for _ in range(2):
        requests.post(url, headers=headers)
        time.sleep(1.0)

def search_roulette(guild_id, channel_id):
    url = f"https://discord.com/api/v9/guilds/{guild_id}/messages/search?channel_id={channel_id}&content=roulette"
    headers = {"Authorization": MAIN_TOKEN}
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            data = res.json()
            msgs = [m[0]['content'].lower() for m in data.get('messages', [])[:25]]
            found = [c for c in ["black", "red"] if any(c in m for m in msgs)]
            if not found: return None
            
            b, r = found.count("black"), found.count("red")
            pick = "black" if r > b else "red"
            return f"{pick} { 'high' if abs(r-b) > 2 else 'low' }"
        return None
    except: return None

def bj_logic(my_t, d_u, is_p, count):
    decision = "hit"
    if my_t >= 17: decision = "stand"
    elif 13 <= my_t <= 16 and d_u <= 6: decision = "stand"
    elif my_t == 11: decision = "double"
    elif is_p and my_t in [16, 12, 4]: decision = "split"
    
    prob = 48
    if my_t >= 20: prob = 90
    elif 4 <= d_u <= 6: prob += 10
    prob -= (count - 2) * 5
    return f"{decision} {max(5, min(99, prob))}%"

def on_message(ws, message):
    data = json.loads(message)
    if data.get("t") == "MESSAGE_CREATE":
        m = data["d"]
        content = m.get("content", "").lower().strip()
        
        # 1. SECURITY: Only YOU can trigger it
        if m.get("author", {}).get("id") != MAIN_ID: return
        
        channel_id = m.get("channel_id")
        msg_id = m.get("id")
        guild_id = m.get("guild_id")

        # 2. TRIGGER: Check for exact commands without ping
        if content.startswith(".h ") or content == ".ra":
            
            # --- AUTO-DELETE YOUR COMMAND (1s) ---
            threading.Thread(target=delete_msg, args=(MAIN_TOKEN, channel_id, msg_id, 1)).start()

            # --- PROCESS BLACKJACK ---
            if content.startswith(".h "):
                try:
                    p = content.split(".h ")[1].split(" ")
                    # Format: .h [Total] [Dealer] [Pair y/n] [CardsCount]
                    res = bj_logic(int(p[0]), int(p[1]), p[2]=='y', int(p[3]))
                    threading.Thread(target=ghost_post, args=(res, channel_id)).start()
                except: pass

            # --- PROCESS ROULETTE ---
            elif content == ".ra":
                advice = search_roulette(guild_id, channel_id)
                if advice:
                    threading.Thread(target=ghost_post, args=(advice, channel_id)).start()
                else:
                    threading.Thread(target=typing_signal, args=(channel_id,)).start()

def run_bot():
    import websocket
    while True:
        try:
            ws = websocket.WebSocketApp("wss://gateway.discord.gg/?v=9&encoding=json", on_message=on_message)
            ws.on_open = lambda ws: ws.send(json.dumps({"op": 2, "d": {"token": MAIN_TOKEN, "properties": {"$os": "windows"}}}))
            ws.run_forever()
        except: time.sleep(5)

if __name__ == "__main__":
    print(">>> Ghost Active: Type .h or .ra (No Ping Needed)")
    run_bot()
