# -*- coding: utf-8 -*-
"""
AquaAlert Rainfall GAN — TimeGAN-inspired architecture
Trains a conditional GAN on historical rainfall sequences.
Generates synthetic extreme rainfall scenarios for flood stress-testing.

Usage:
    py notebooks/train_rainfall_gan.py
"""

import os
import sys
import json
import numpy as np

# Add project root to path so local imports resolve consistently.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import requests as req_lib

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

# ── Config ──────────────────────────────────────────────────────────────────
SEQ_LEN    = 72       # 72 hours
LATENT_DIM = 32       # noise vector size
EPOCHS     = 500
BATCH_SIZE = 32
CITIES = {
    "mumbai":    {"lat": 19.0760, "lon": 72.8777},
    "chennai":   {"lat": 13.0827, "lon": 80.2707},
    "bengaluru": {"lat": 12.9716, "lon": 77.5946},
    "pune":      {"lat": 18.5204, "lon": 73.8567},
}

BASE_DIR   = PROJECT_ROOT
MODELS_DIR = os.path.join(PROJECT_ROOT, "models", "gan")
os.makedirs(MODELS_DIR, exist_ok=True)

# ── Data Collection ──────────────────────────────────────────────────────────
def fetch_historical_sequences(city_cfg, n_years=3):
    """Fetch multi-year hourly rainfall and extract 72h windows."""
    sequences = []
    for year in range(2022, 2022 + n_years):
        try:
            url = "https://archive-api.open-meteo.com/v1/archive"
            params = {
                "latitude": city_cfg["lat"],
                "longitude": city_cfg["lon"],
                "start_date": f"{year}-06-01",
                "end_date":   f"{year}-09-30",
                "hourly": "precipitation",
                "timezone": "Asia/Kolkata"
            }
            r = req_lib.get(url, params=params, timeout=30)
            r.raise_for_status()
            precip = r.json()["hourly"]["precipitation"]
            precip = [p if p is not None else 0.0 for p in precip]

            # Sliding window — extract all 72h sequences
            for i in range(0, len(precip) - SEQ_LEN, 6):
                seq = precip[i:i + SEQ_LEN]
                if sum(seq) > 0:  # only keep sequences with some rain
                    sequences.append(seq)
        except Exception as e:
            print(f"  [data] {year} fetch failed: {e}")

    return np.array(sequences, dtype=np.float32)


def normalize(data, max_val=50.0):
    return np.clip(data / max_val, 0.0, 1.0)


def denormalize(data, max_val=50.0):
    return np.clip(data * max_val, 0.0, None)


# ── GAN Architecture ─────────────────────────────────────────────────────────
def build_generator(latent_dim, seq_len, condition_dim=1):
    """
    Conditional Generator:
    Input: [noise(latent_dim) + condition(intensity_factor)]
    Output: synthetic rainfall sequence (seq_len,)
    """
    noise = keras.Input(shape=(latent_dim,), name="noise")
    cond  = keras.Input(shape=(condition_dim,), name="condition")

    x = layers.Concatenate()([noise, cond])
    x = layers.Dense(128, activation="relu")(x)
    x = layers.Dense(256, activation="relu")(x)
    x = layers.Reshape((16, 16))(x)
    x = layers.LSTM(64, return_sequences=True)(x)
    x = layers.LSTM(32, return_sequences=True)(x)
    x = layers.TimeDistributed(layers.Dense(1, activation="sigmoid"))(x)

    # Upsample from 16 steps to seq_len
    x = layers.Reshape((16,))(x)
    x = layers.Dense(seq_len, activation="sigmoid")(x)

    return keras.Model([noise, cond], x, name="Generator")


def build_discriminator(seq_len, condition_dim=1):
    """
    Conditional Discriminator:
    Input: [sequence(seq_len) + condition(intensity_factor)]
    Output: real/fake probability
    """
    seq  = keras.Input(shape=(seq_len,), name="sequence")
    cond = keras.Input(shape=(condition_dim,), name="condition")

    x = layers.Concatenate()([seq, cond])
    x = layers.Reshape((seq_len + condition_dim, 1))(x)
    x = layers.Conv1D(32, 4, strides=2, padding="same", activation="leaky_relu")(x)
    x = layers.Conv1D(64, 4, strides=2, padding="same", activation="leaky_relu")(x)
    x = layers.Flatten()(x)
    x = layers.Dense(64, activation="leaky_relu")(x)
    x = layers.Dropout(0.3)(x)
    x = layers.Dense(1, activation="sigmoid")(x)

    return keras.Model([seq, cond], x, name="Discriminator")


# ── Training ─────────────────────────────────────────────────────────────────
def train_gan(sequences, city_name):
    print(f"\n[GAN] Training on {len(sequences)} sequences for {city_name}...")

    norm_seqs = normalize(sequences)

    G = build_generator(LATENT_DIM, SEQ_LEN)
    D = build_discriminator(SEQ_LEN)

    g_opt = keras.optimizers.Adam(1e-4, beta_1=0.5)
    d_opt = keras.optimizers.Adam(1e-4, beta_1=0.5)
    bce   = keras.losses.BinaryCrossentropy()

    g_losses, d_losses = [], []

    for epoch in range(EPOCHS):
        # Sample real batch
        idx      = np.random.randint(0, len(norm_seqs), BATCH_SIZE)
        real_seq = norm_seqs[idx]

        # Condition: intensity factor (1.0 = normal, 2.0 = double, etc.)
        real_cond = np.ones((BATCH_SIZE, 1), dtype=np.float32)

        # Train Discriminator
        noise      = np.random.normal(0, 1, (BATCH_SIZE, LATENT_DIM)).astype(np.float32)
        fake_cond  = np.random.uniform(0.5, 3.0, (BATCH_SIZE, 1)).astype(np.float32)
        fake_seq   = G([noise, fake_cond], training=False).numpy()

        with tf.GradientTape() as tape:
            real_pred = D([real_seq, real_cond], training=True)
            fake_pred = D([fake_seq, fake_cond], training=True)
            d_loss = bce(tf.ones_like(real_pred), real_pred) + \
                     bce(tf.zeros_like(fake_pred), fake_pred)

        grads = tape.gradient(d_loss, D.trainable_variables)
        d_opt.apply_gradients(zip(grads, D.trainable_variables))

        # Train Generator
        noise     = tf.convert_to_tensor(
            np.random.normal(0, 1, (BATCH_SIZE, LATENT_DIM)).astype(np.float32)
        )
        gen_cond  = tf.convert_to_tensor(
            np.random.uniform(0.5, 3.0, (BATCH_SIZE, 1)).astype(np.float32)
        )

        with tf.GradientTape() as tape:
            gen_seq   = G([noise, gen_cond], training=True)
            gen_pred  = D([gen_seq, gen_cond], training=False)
            g_loss    = bce(tf.ones_like(gen_pred), gen_pred)

        grads = tape.gradient(g_loss, G.trainable_variables)
        g_opt.apply_gradients(zip(grads, G.trainable_variables))

        g_losses.append(float(g_loss))
        d_losses.append(float(d_loss))

        if (epoch + 1) % 100 == 0:
            print(f"  Epoch {epoch+1}/{EPOCHS} | G: {g_loss:.4f} | D: {d_loss:.4f}")

    return G, {"g_losses": g_losses[-50:], "d_losses": d_losses[-50:]}


# ── Save ─────────────────────────────────────────────────────────────────────
def save_generator(G, city_name, metrics):
    path = os.path.join(MODELS_DIR, f"rainfall_gan_{city_name}.keras")
    G.save(path)
    meta = {
        "city": city_name,
        "seq_len": SEQ_LEN,
        "latent_dim": LATENT_DIM,
        "epochs": EPOCHS,
        "final_g_loss": round(metrics["g_losses"][-1], 4),
        "final_d_loss": round(metrics["d_losses"][-1], 4),
        "model_path": path
    }
    meta_path = os.path.join(MODELS_DIR, f"rainfall_gan_{city_name}_meta.json")
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"[GAN] Saved: {path}")
    return meta


# ── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    all_meta = {}
    for city_name, cfg in CITIES.items():
        print(f"\n{'='*50}")
        print(f"Processing: {city_name.upper()}")
        print(f"{'='*50}")

        seqs = fetch_historical_sequences(cfg, n_years=3)
        if len(seqs) < 10:
            print(f"  [skip] Not enough data for {city_name} ({len(seqs)} sequences)")
            continue

        G, metrics = train_gan(seqs, city_name)
        meta = save_generator(G, city_name, metrics)
        all_meta[city_name] = meta

    # Save combined summary
    summary_path = os.path.join(MODELS_DIR, "gan_summary.json")
    with open(summary_path, "w") as f:
        json.dump(all_meta, f, indent=2)

    print(f"\n[GAN] Training complete. Models saved to: {MODELS_DIR}")
    print(f"[GAN] Summary: {summary_path}")
