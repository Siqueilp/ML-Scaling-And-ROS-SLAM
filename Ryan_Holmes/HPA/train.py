# Import necessary libraries
import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from sklearn.model_selection import train_test_split
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.callbacks import EarlyStopping

# === Load and Prepare Data ===
df = pd.read_csv("tetris_metrics_HPA_new.csv")  # Load dataset

# Define feature columns and target column
features = ["short_http", "long_http", "cpu", "memory",
            "short_http_per_pod", "long_http_per_pod", "cpu_per_pod", "memory_per_pod"]
target = "pods"

X = df[features].values  # Feature matrix
y = df[target].values    # Target vector

# Normalize features between 0 and 1
scaler = MinMaxScaler(feature_range=(0, 1))
X_scaled = scaler.fit_transform(X)

# === Create Time-Series Sequences ===
time_steps = 10  # Number of past time steps to consider
X_seq, y_seq = [], []

# Build sequences for LSTM input
for i in range(len(X_scaled) - time_steps):
    X_seq.append(X_scaled[i : i + time_steps])  # Sequence of features
    y_seq.append(y[i + time_steps])              # Target value after the sequence

X_seq, y_seq = np.array(X_seq), np.array(y_seq)  # Convert lists to numpy arrays

# === Train-Test Split ===
X_train, X_test, y_train, y_test = train_test_split(X_seq, y_seq, test_size=0.2, random_state=42)

# === Define LSTM Model ===
model = Sequential([
    LSTM(50, input_shape=(X_train.shape[1], X_train.shape[2]), return_sequences=False),  # Single LSTM layer
    Dense(1)  # Output layer predicting the number of pods
])

# Compile model with Mean Squared Error loss and Adam optimizer
model.compile(optimizer=Adam(learning_rate=0.001), loss='mse')

# === Define EarlyStopping Callback ===
early_stopping = EarlyStopping(
    monitor='val_loss',      # Monitor validation loss
    patience=10,             # Stop if no improvement for 10 epochs
    restore_best_weights=True  # Restore the best model
)

# === Train the Model ===
history = model.fit(
    X_train, y_train,
    epochs=50,              # Maximum of 50 epochs
    batch_size=16,          # 16 samples per batch
    validation_data=(X_test, y_test),
    callbacks=[early_stopping]  # Enable early stopping
)

# === Save Trained Model ===
model.save('hpa_lstm_model.h5')  # Save model in HDF5 format

# === Output Training History ===
print("Training History:")
print(history.history)  # Print loss and validation loss over epochs

