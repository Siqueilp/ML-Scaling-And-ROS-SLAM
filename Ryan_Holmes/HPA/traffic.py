	import time
import requests
import threading
import asyncio
import websockets
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

# === Configuration ===
DURATION = 8* 60 * 60                # ⏱️ Total simulation time: 8 hours
START_USERS = 2                   # 👤 Initial number of users
MAX_USERS = 20                    # 👥 Maximum number of users
RAMP_UP_DURATION = 4*60* 60         # ⏫ Ramp-up duration: 4 hrs
RAMP_DOWN_DURATION = 4*60 * 60       # ⏬ Ramp-down duration: 4 hrs
SLEEP_BETWEEN_WAVES = 10           # 💤 Time between user waves (seconds)

INTERACTIONS_PER_USER = 10         # 🔁 Number of request iterations per user
THINK_TIME = 0.5                   # 🧠 Think time between actions (seconds)

TARGET_HOST = "http://192.168.1.245:30002"  # 🌐 Target HTTP endpoint
WS_HOST = "ws://192.168.1.245:30002"         # 🔌 Target WebSocket endpoint

# === Thread-safe Request Counter ===
request_counter = 0
counter_lock = threading.Lock()

def record_request():
    """Increment request counter safely across threads."""
    global request_counter
    with counter_lock:
        request_counter += 1

# === Load curve: users over time ===
def calculate_user_count(current_time):
    """Calculate number of users based on elapsed time."""
    if current_time <= RAMP_UP_DURATION:
        return int(START_USERS + (MAX_USERS - START_USERS) * (current_time / RAMP_UP_DURATION))
    elif current_time <= DURATION - RAMP_DOWN_DURATION:
        return MAX_USERS
    else:
        return int(MAX_USERS - (MAX_USERS - START_USERS) * ((current_time - (DURATION - RAMP_DOWN_DURATION)) / RAMP_DOWN_DURATION))

# === WebSocket registration simulation ===
async def simulate_websocket(battle_id, username):
    """Simulate a WebSocket client registering."""
    try:
        async with websockets.connect(WS_HOST) as websocket:
            register_msg = {
                "type": "register",
                "battleId": battle_id,
                "name": username
            }
            await websocket.send(json.dumps(register_msg))
            print(f"🔌 WS: {username} registered in {battle_id}")

            # Listen briefly for a server response
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=2)
                print(f"📨 WS Message: {message}")
            except asyncio.TimeoutError:
                pass
    except Exception as e:
        print(f"❌ WS Error ({username}): {e}")

# === HTTP + WebSocket interaction per user ===
def simulate_user(user_id):
    """Simulate user behavior: HTTP + WebSocket."""
    timestamp = int(time.time())
    battle_id = f"battle_{user_id}_{timestamp}"
    username = f"player_{user_id}_{timestamp}"

    for _ in range(INTERACTIONS_PER_USER):
        try:
            # POST /battle
            post_resp = requests.post(
                f"{TARGET_HOST}/battle",
                json={"username": username, "battleId": battle_id},
                timeout=5
            )
            print(f"[User {user_id}] POST /battle - Status {post_resp.status_code}")
            record_request()
        except Exception as e:
            print(f"[User {user_id}] POST failed: {e}")

        try:
            # GET /game.html
            get_resp = requests.get(
                f"{TARGET_HOST}/game.html?battleId={battle_id}&name={username}",
                timeout=5
            )
            print(f"[User {user_id}] GET /game.html - Status {get_resp.status_code}")
            record_request()
        except Exception as e:
            print(f"[User {user_id}] GET failed: {e}")

        try:
            # Simulate WebSocket registration
            asyncio.run(simulate_websocket(battle_id, username))
        except Exception as e:
            print(f"[User {user_id}] WS simulation failed: {e}")

        time.sleep(THINK_TIME)

# === Load Testing Engine ===
def simulate_user_traffic():
    """Main simulation controller."""
    start_time = time.time()

    while True:
        current_time = time.time() - start_time
        if current_time > DURATION:
            print("✅ Traffic simulation complete.")
            break

        num_users = calculate_user_count(current_time)
        print(f"\n[Time {int(current_time)}s] Simulating {num_users} concurrent users...")

        with ThreadPoolExecutor(max_workers=num_users) as executor:
            futures = [executor.submit(simulate_user, user_id) for user_id in range(num_users)]
            for future in as_completed(futures):
                pass  # Wait for all users to finish

        with counter_lock:
            print(f"[Stats] Total requests sent so far: {request_counter}")

        time.sleep(SLEEP_BETWEEN_WAVES)

# === Entry Point ===
if __name__ == "__main__":
    simulate_user_traffic()
