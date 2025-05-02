import os
import time
import datetime
import json
import subprocess

# === Configuration ===
deployment = "tetris"                      # Deployment name
namespace = "scaling"                      # Namespace
min_replicas = 1                           # Minimum number of pods
max_replicas = 30                          # Maximum number of pods
log_file = "scale_log.csv"                 # CSV log file
TRAFFIC_LOG_FILE = "current_traffic_load.json"  # JSON file updated with traffic load

# === Helper: Read current HTTP traffic load from file ===
def get_current_http_duration():
    try:
        with open(TRAFFIC_LOG_FILE, "r") as f:
            data = json.load(f)
            duration = data.get("traffic_load", 0)
            return max(0.0, float(duration))
    except Exception as e:
        print(f"⚠️ Failed to read HTTP duration: {e}")
        return 0.0

# === Helper: Get current number of replicas from kubectl ===
def get_current_replicas():
    try:
        result = subprocess.check_output(
            ["kubectl", "get", "deployment", deployment, "-n", namespace,
             "-o", "jsonpath={.spec.replicas}"]
        )
        return int(result.decode().strip())
    except Exception as e:
        print(f"⚠️ Failed to get current replicas: {e}")
        return min_replicas

# === Main loop ===
start_time = time.time()
TOTAL_DURATION = 8 * 60 * 60  # 8 hours total run
CHECK_INTERVAL = 60           # Check every 60 seconds

last_duration_checkpoint = None  # Stores the HTTP duration seen at last scaling decision

print("🚀 Starting autoscaler using HTTP duration (8-hour run)...\n")
while True:
    elapsed = time.time() - start_time
    if elapsed > TOTAL_DURATION:
        print("✅ Autoscaler finished after 8 hours.")
        break

    # Read current metrics
    http_duration = get_current_http_duration()
    current_replicas = get_current_replicas()
    timestamp = datetime.datetime.utcnow().isoformat()

    scaling_halfway = elapsed > (TOTAL_DURATION / 2)  # After 4 hours, start scaling down
    new_replicas = current_replicas
    should_scale = False

    if last_duration_checkpoint is None:
        last_duration_checkpoint = http_duration  # First loop init

    if not scaling_halfway:
        # First 4 hours — scale up if traffic load increases by 1%
        if http_duration - last_duration_checkpoint >= 1.0:
            new_replicas = min(current_replicas + 1, max_replicas)
            should_scale = new_replicas != current_replicas
    else:
        # Last 4 hours — scale down if traffic load decreases by 1%
        if last_duration_checkpoint - http_duration >= 1.0:
            new_replicas = max(current_replicas - 1, min_replicas)
            should_scale = new_replicas != current_replicas

    if should_scale:
        print(f"[{timestamp}] Scaling from {current_replicas} to {new_replicas} based on HTTP duration {http_duration:.2f}%")
        try:
            subprocess.run([
                "kubectl", "scale", f"deployment/{deployment}",
                f"--replicas={new_replicas}", "-n", namespace
            ], check=True)

            # Log scaling event
            with open(log_file, "a") as f:
                f.write(f"{timestamp},{new_replicas},{http_duration:.2f}\n")

            last_duration_checkpoint = http_duration  # Update for next comparisons
        except Exception as e:
            print(f"❌ Scaling error: {e}")
    else:
        print(f"[{timestamp}] No scaling needed. Current: {current_replicas} replicas, Traffic load: {http_duration:.2f}%")

    time.sleep(CHECK_INTERVAL)
