import requests, time, random, json, re, threading, os

# ==========================================
# CONFIGURATION
# ==========================================
OWNERS_RAW = os.getenv("OWNERS", "")
OWNER_IDS = [int(i.strip()) for i in OWNERS_RAW.split(",") if i.strip()]

MAIN_TOKEN = os.getenv("MAIN_TOKEN") 
ALT_TOKEN = os.getenv("ALT_TOKEN") 
# ==========================================

def delete_msg(token, channel_id, msg_id, delay):
    """Deletes a specific message after a delay"""
    time.sleep(delay)
    url = f"https://discord.com/api/v9/channels/{channel_id}/messages/{msg_id}"
    requests.delete(url, headers={"Authorization": token})

def ghost_post(content, channel_id, delete_after=2):
    """Alt sends the advice and deletes it 2s later"""
    url = f"https://discord.com/api/v9/channels/{channel_id}/messages"
    headers = {"Authorization": ALT_TOKEN}
    time.sleep(random.uniform(1.2, 2.0)) # Simulate 'thinking'
    
    res = requests.post(url, headers=headers, json={"content": content.lower()})
    if res.status_code == 200:
        msg_id = res.json()['id']
        threading.Thread(target=delete_msg, args=(ALT_TOKEN, channel_id, msg_id, delete_after)).start()

def typing_signal(channel_id):
    """Alt types then stops if no data is found"""
    url = f"https://discord.com/api/v9/channels/{channel_id}/typing"
    headers = {"Authorization": ALT_TOKEN}
    for _ in range(2):
        requests.post(url, headers=headers)
        time.sleep(1.0)

def search_roulette(guild_id, channel_id):
    """Analyzes actual UnbelievaBoat results (not player guesses)"""
    url = f"https://discord.com/api/v9/guilds/{guild_id}/messages/search?channel_id={channel_id}&content=landed on"
    headers = {"Authorization": MAIN_TOKEN}
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            data = res.json()
            msgs = [m[0]['content'].lower() for m in data.get('messages', [])[:25]]
            found = []
            for m in msgs:
                if "black" in m: found.append("black")
                elif "red" in m: found.append("red")
            
            if not found: return None
            
            b, r = found.count("black"), found.count("red")
            # Strategic Pick: Bet on the color that is currently 'colder'
            pick = "black" if r > b else "red"
            conf = "high" if abs(r-b) > 3 else "low"
            return f"{pick} {conf}"
        return None
    except: return None

def bj_logic(my_t, d_u, is_p, count):
    """Full Math Matrix: Hard/Soft totals, Splits, and Tension"""
    decision = "hit"
    
    # 1. PAIR SPLITTING (The 'y' Logic)
    if is_p and count == 2:
        if my_t in [16, 22]: decision = "split" # 8s and Aces
        elif my_t == 20: decision = "stand"    # 10s
        elif my_t == 18 and d_u not in [7, 10, 11]: decision = "split" # 9s
        elif my_t in [4, 6, 14] and d_u <= 7: decision = "split" # 2s, 3s, 7s
        elif my_t == 12 and d_u <= 6: decision = "split" # 6s

    # 2. DOUBLE DOWN (Aggressive Math)
    if decision == "hit" and count == 2:
        if my_t == 11: decision = "double"
        elif my_t == 10 and d_u <= 9: decision = "double"
        elif my_t == 9 and 3 <= d_u <= 6: decision = "double"

    # 3. STAND RULES (Basic Strategy)
    if decision == "hit":
        if my_t >= 17: decision = "stand"
        elif 13 <= my_t <= 16:
            decision = "stand" if d_u <= 6 else "hit"
        elif my_t == 12:
            decision = "stand" if 4 <= d_u <= 6 else "hit"

    # 4. MATH MODE: WIN PROBABILITY
    # Based on dealer bust odds + your total - card tension
    bust_odds = {2:35, 3:37, 4:40, 5:42, 6:42, 7:26, 8:24, 9:23, 10:21, 11:11}
    base_win = 99 if my_t == 21 else (40 + (my_t / 2))
    
    final_prob = (base_win + bust_odds.get(d_u, 21)) / 2
    tension_penalty = (count - 2) * 7 # Probability drops as you pull more cards
    final_prob -= tension_penalty

    return f"{decision} {max(5, min(99, int(final_prob)))}%"

def on_message(ws, message):
    try:
        data = json.loads(message)
        if data.get("t") == "MESSAGE_CREATE":
            m = data["d"]
            content = m.get("content", "").lower().strip()
            author_id = int(m.get("author", {}).get("id"))
            
            # Authorization
            if author_id not in OWNER_IDS: return

            channel_id = m.get("channel_id")
            msg_id = m.get("id")
            guild_id = m.get("guild_id")

            if content.startswith(".h ") or content == ".ra":
                # Stealth: Delete your command in 1s
                threading.Thread(target=delete_msg, args=(MAIN_TOKEN, channel_id, msg_id, 1)).start()

                if content.startswith(".h "):
                    try:
                        p = content.split(".h ")[1].split(" ")
                        # Input: Total, DealerCard, Pair(y/n), CardCount
                        res = bj_logic(int(p[0]), int(p[1]), p[2]=='y', int(p[3]))
                        threading.Thread(target=ghost_post, args=(res, channel_id)).start()
                    except: pass
                elif content == ".ra":
                    advice = search_roulette(guild_id, channel_id)
                    if advice:
                        threading.Thread(target=ghost_post, args=(advice, channel_id)).start()
                    else:
                        threading.Thread(target=typing_signal, args=(channel_id,)).start()
    except: pass

def run_bot():
    import websocket
    while True:
        try:
            ws = websocket.WebSocketApp("wss://gateway.discord.gg/?v=9&encoding=json", on_message=on_message)
            ws.on_open = lambda ws: ws.send(json.dumps({"op": 2, "d": {"token": MAIN_TOKEN, "properties": {"$os": "windows"}}}))
            ws.run_forever()
        except: time.sleep(5)

if __name__ == "__main__":
    run_bot()
