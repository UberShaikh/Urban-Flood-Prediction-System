import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import numpy as np
from PIL import Image
from tensorflow.keras.models import load_model
import tensorflow as tf

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE, 'models', 'saved', 'cnn_model.h5')
IMG_PATH = os.path.join(BASE, 'data', 'raw', 'flood-area', 'Image', '37.jpg')

model = load_model(MODEL_PATH)
print("Model output shape:", model.output_shape)

# Find last conv layer
last_conv = None
for layer in reversed(model.layers):
    if 'conv2d' in layer.name:
        last_conv = layer
        print("Last conv layer:", last_conv.name, last_conv.output_shape)
        break

img = Image.open(IMG_PATH).convert('RGB').resize((128, 128))
x = np.expand_dims(np.array(img, dtype=np.float32) / 255.0, 0)

grad_model = tf.keras.models.Model(inputs=model.inputs, outputs=[last_conv.output, model.output])
with tf.GradientTape() as tape:
    conv_out, preds = grad_model(x)
    loss = tf.reduce_mean(preds)

grads = tape.gradient(loss, conv_out)
print("Grads shape:", grads.shape)
pooled = tf.reduce_mean(grads, axis=(0, 1, 2))
heatmap = conv_out[0] @ pooled[..., tf.newaxis]
heatmap = tf.squeeze(heatmap).numpy()
print("Heatmap shape:", heatmap.shape, "min:", heatmap.min(), "max:", heatmap.max())
print("GradCAM OK")
