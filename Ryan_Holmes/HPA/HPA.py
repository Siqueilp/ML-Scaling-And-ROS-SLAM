# Import necessary libraries
import numpy as np
import time
import os
from tensorflow.keras.models import load_model
import curl  # Custom module for accessing Kubernetes deployment metrics

# === Initialize Deployment Curl Instance ===
deployment_name = "tetris"
deployment_curl = curl.curl(deployment_name)

# === Load Pre-trained LSTM Model ===
model_path = "hpa_lstm_model.h5"
model = load_model(model_path)

# === Setup for LSTM input buffer ===
time_steps = 10       # Number of past steps for the LSTM
feature_size = 8      # Number of features per step
state_sequence = np.zeros((time_steps, feature_size))  # Rolling buffer initialized with zeros

# === Timing Configurations ===
scale_interval_seconds = 30  # Only attempt scaling every 30 seconds
loop_interval_seconds = 5    # Main loop check interval
steps_until_scale = scale_interval_seconds // loop_interval_seconds  # Steps before considering scaling

# === Feature Normalization ===
def normalize_features(short_http, long_http, cpu, memory, pods):
    eps = 1e-6  # Small epsilon to avoid division by zero
    short_http_per_pod = short_http / (pods + eps)
    long_http_per_pod = long_http / (pods + eps)
    cpu_per_pod = cpu / (pods + eps)
    memory_per_pod = memory / (pods + eps)
    return [
        short_http, long_http, cpu, memory,
        short_http_per_pod, long_http_per_pod, cpu_per_pod, memory_per_pod
    ]

# === Pod Scaling Logic ===
def scale_pods(current_pods, predicted_pods, threshold=0.9):
    predicted_rounded = int(round(predicted_pods))
    if predicted_rounded > current_pods + threshold:
        print(f"[ACTION] Scaling Up: {current_pods} → {current_pods + 1}")
        current_pods += 1
    elif predicted_rounded < current_pods - threshold and current_pods > 1:
        print(f"[ACTION] Scaling Down: {current_pods} → {current_pods - 1}")
        current_pods -= 1
    else:
        print(f"[ACTION] No scaling needed. Pods remain at {current_pods}")
    
    # Execute scaling command to Kubernetes
    os.system(f"kubectl scale --replicas={current_pods} deployment/{deployment_name} -n scaling")
    
    return current_pods

# === Main Control Loop ===
print("[INFO] Starting HPA loop using LSTM model...")
step_count = 0  # Counter to enforce scaling interval

while True:
    try:
        # Fetch live metrics from Kubernetes
        short_http, long_http, cpu, memory, pods = deployment_curl.hpa_curl()
        current_pods = deployment_curl.replicas()

        # Normalize features and update rolling window
        features = normalize_features(short_http, long_http, cpu, memory, current_pods)
        new_step = np.array(features)
        state_sequence = np.vstack([state_sequence[1:], new_step])  # Roll window by 1

        # If rolling buffer is full (no zeros), start making predictions
        if not np.any(state_sequence == 0):
            if step_count == 0:
                # Prepare input and predict next pod count
                model_input = state_sequence.reshape(1, time_steps, feature_size)
                predicted_pods = model.predict(model_input)[0][0]

                print(f"[PREDICTION] Current Pods: {current_pods} | Predicted Pods: {predicted_pods:.2f}")

                # Decide whether to scale up/down
                current_pods = scale_pods(current_pods, predicted_pods)
            else:
                print(f"[INFO] Skipping scaling this round (step {step_count}/{steps_until_scale})")
        else:
            print("[INFO] Warming up sequence buffer...")  # Waiting for initial data fill

        # Update step counter
        step_count = (step_count + 1) % steps_until_scale

        # Sleep between each loop iteration
        time.sleep(loop_interval_seconds)

    except Exception as e:
        print(f"[ERROR] Exception occurred: {e}")
        time.sleep(loop_interval_seconds)
