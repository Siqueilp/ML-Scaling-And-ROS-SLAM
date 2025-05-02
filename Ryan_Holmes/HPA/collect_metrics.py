import numpy as np
import pandas as pd
import time
import curl
import os
import signal
import sys
import json

# === File paths ===
output_path = "tetris_metrics_HPA_test_HPA_testing.csv"
temp_path = "tetris_metrics_temp.csv"
TRAFFIC_LOG_FILE = "current_traffic_load.json"

# === Graceful shutdown ===
def save_and_exit(data):
    # Save collected data and exit cleanly
    print("\n[!] Saving progress before exit...")
    if data:
        df = pd.DataFrame(data, columns=[
            "short_http", "long_http", "cpu", "memory", "pods",
            "short_http_per_pod", "long_http_per_pod", "cpu_per_pod", "memory_per_pod"
        ])
        df.to_csv(output_path, index=False)
        print(f"✅ Final data saved to {output_path}")
    else:
        print("⚠️ No data to save.")
    sys.exit(0)

def signal_handler(sig, frame):
    # Trigger graceful shutdown on SIGINT or SIGTERM
    save_and_exit(data)

# Setup signal handlers for CTRL+C or kill signals
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# === Dynamic traffic load estimator (no per-pod) ===
def calculate_traffic_load(short_http, long_http):
    # Basic weighted average between short and long http load
    load = 0.6 * short_http + 0.4 * long_http
    return round(min(load, 100), 2)

# === JSON writer ===
def update_traffic_json(traffic_load):
    # Update the JSON file with latest traffic load and timestamp
    data = {
        "traffic_load": traffic_load,
        "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ')
    }
    with open(TRAFFIC_LOG_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"📊 Traffic load updated: {traffic_load}%")

# === Setup ===
deployment_name = "tetris"
deployment_curl = curl.curl(deployment_name)
data = []

step_interval = 5  # Sampling interval in seconds
duration = 8 * 60 * 60  # 8 hours in seconds
time_steps = duration // step_interval

print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting 8-hour metrics collection ({time_steps} steps)...")

try:
    for i in range(int(time_steps)):
        # Collect current metrics from Prometheus
        short_http, long_http, _, cpu, memory = deployment_curl.hpa_curl()
        pods = deployment_curl.replicas()
        pods = pods if pods > 0 else 1e-6  # Safeguard: avoid division by zero

        # Per-pod metrics calculation
        short_per_pod = short_http / pods
        long_per_pod = long_http / pods
        cpu_per_pod = cpu / pods
        memory_per_pod = memory / pods

        # Save this time step
        data.append([
            short_http, long_http, cpu, memory, pods,
            short_per_pod, long_per_pod, cpu_per_pod, memory_per_pod
        ])

        # Every 10 seconds, update the traffic load JSON
        if i % 2 == 0:
            load = calculate_traffic_load(short_http, long_http)
            update_traffic_json(load)

        # Every 60 steps (5 minutes), save intermediate temp data
        if i % 60 == 0 and i > 0:
            print(f"[{time.strftime('%H:%M:%S')}] Step {i}/{time_steps} — Saving temp data...")
            pd.DataFrame(data, columns=[
                "short_http", "long_http", "cpu", "memory", "pods",
                "short_http_per_pod", "long_http_per_pod", "cpu_per_pod", "memory_per_pod"
            ]).to_csv(temp_path, index=False)

        time.sleep(step_interval)

except Exception as e:
    # Catch and log any fatal errors before exiting
    print(f"❌ Error: {e}")
    save_and_exit(data)

# Final save after the loop is done
save_and_exit(data)
