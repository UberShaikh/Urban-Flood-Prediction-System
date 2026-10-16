import os
import pandas as pd
import numpy as np
import tensorflow as tf
from tensorflow.keras.layers import Input, Conv2D, UpSampling2D, concatenate, BatchNormalization, Activation
from tensorflow.keras.models import Model
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.losses import BinaryCrossentropy
from tensorflow.keras import backend as K
import rasterio
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# 1. Setup
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
data_dir = os.path.join(project_root, 'data', 'raw', 'v1.1')
models_dir = os.path.join(project_root, 'models')
os.makedirs(os.path.join(models_dir, 'vision'), exist_ok=True)

split_dir = os.path.join(data_dir, 'splits', 'flood_handlabeled')
image_dir = os.path.join(data_dir, 'data', 'flood_events', 'HandLabeled', 'S1Hand')
label_dir = os.path.join(data_dir, 'data', 'flood_events', 'HandLabeled', 'LabelHand')

PATCH_SIZE = 128
PATCH_STRIDE = 64

# 2. Data helpers

def normalize_patch(patch):
    patch = np.nan_to_num(patch, nan=0.0)
    patch = patch.astype(np.float32)
    if np.max(patch) > np.min(patch):
        patch = (patch - np.min(patch)) / (np.max(patch) - np.min(patch))
    return patch


def load_sar_image(path):
    with rasterio.open(path) as src:
        img = src.read(1).astype(np.float32)
    return np.nan_to_num(img, nan=0.0)


def load_label_image(path):
    with rasterio.open(path) as src:
        label = src.read(1).astype(np.float32)
    return np.nan_to_num(label, nan=0.0)


def extract_patch_pairs(img, label, patch_size=128, stride=64):
    patches = []
    masks = []
    h, w = img.shape
    for y in range(0, h - patch_size + 1, stride):
        for x in range(0, w - patch_size + 1, stride):
            patch = img[y:y+patch_size, x:x+patch_size]
            mask = label[y:y+patch_size, x:x+patch_size]
            if patch.shape != (patch_size, patch_size) or mask.shape != (patch_size, patch_size):
                continue
            if np.all(np.isnan(patch)):
                continue
            patch = normalize_patch(patch)
            patch = np.stack([patch, patch, patch], axis=-1)
            mask = (mask > 0).astype(np.float32)
            mask = np.expand_dims(mask, axis=-1)
            patches.append(patch)
            masks.append(mask)
    return patches, masks


def load_dataset(split_csv):
    df = pd.read_csv(split_csv, header=None, names=['image', 'label'])
    imgs = []
    masks = []
    for _, row in df.iterrows():
        image_path = os.path.join(image_dir, row['image'])
        label_path = os.path.join(label_dir, row['label'])
        if not os.path.exists(image_path) or not os.path.exists(label_path):
            continue
        img = load_sar_image(image_path)
        label = load_label_image(label_path)
        patches, patch_masks = extract_patch_pairs(img, label, PATCH_SIZE, PATCH_STRIDE)
        imgs.extend(patches)
        masks.extend(patch_masks)
    return np.array(imgs, dtype=np.float32), np.array(masks, dtype=np.float32)

# 3. Load splits
train_csv = os.path.join(split_dir, 'flood_train_data.csv')
val_csv = os.path.join(split_dir, 'flood_valid_data.csv')
test_csv = os.path.join(split_dir, 'flood_test_data.csv')

print('Loading training patches...')
X_train, Y_train = load_dataset(train_csv)
print('Loading validation patches...')
X_val, Y_val = load_dataset(val_csv)
print('Loading test patches...')
X_test, Y_test = load_dataset(test_csv)

print(f'Train patches: {X_train.shape}, masks: {Y_train.shape}')
print(f'Val patches: {X_val.shape}, masks: {Y_val.shape}')
print(f'Test patches: {X_test.shape}, masks: {Y_test.shape}')

# 4. Build ResNet50 + U-Net
inputs = Input(shape=(PATCH_SIZE, PATCH_SIZE, 3))
base_model = tf.keras.applications.ResNet50(weights='imagenet', include_top=False, input_tensor=inputs)

skip1 = base_model.get_layer('conv1_relu').output    # 64x64x64
skip2 = base_model.get_layer('conv2_block3_out').output  # 32x32x256
skip3 = base_model.get_layer('conv3_block4_out').output  # 16x16x512
skip4 = base_model.get_layer('conv4_block6_out').output  # 8x8x1024
x = base_model.get_layer('conv5_block3_out').output       # 4x4x2048

# Decoder
x = UpSampling2D((2, 2))(x)
x = Conv2D(512, (3, 3), padding='same')(x)
x = BatchNormalization()(x)
x = Activation('relu')(x)
x = concatenate([x, skip4])

x = UpSampling2D((2, 2))(x)
x = Conv2D(256, (3, 3), padding='same')(x)
x = BatchNormalization()(x)
x = Activation('relu')(x)
x = concatenate([x, skip3])

x = UpSampling2D((2, 2))(x)
x = Conv2D(128, (3, 3), padding='same')(x)
x = BatchNormalization()(x)
x = Activation('relu')(x)
x = concatenate([x, skip2])

x = UpSampling2D((2, 2))(x)
x = Conv2D(64, (3, 3), padding='same')(x)
x = BatchNormalization()(x)
x = Activation('relu')(x)
x = concatenate([x, skip1])

x = UpSampling2D((2, 2))(x)
x = Conv2D(32, (3, 3), padding='same')(x)
x = BatchNormalization()(x)
x = Activation('relu')(x)

outputs = Conv2D(1, (1, 1), activation='sigmoid')(x)

model = Model(inputs=inputs, outputs=outputs)

# 5. Loss and metrics

def dice_coef(y_true, y_pred, smooth=1e-6):
    y_pred = K.flatten(y_pred)
    y_true = K.flatten(y_true)
    intersection = K.sum(y_true * y_pred)
    return (2.0 * intersection + smooth) / (K.sum(y_true) + K.sum(y_pred) + smooth)


def dice_loss(y_true, y_pred):
    return 1.0 - dice_coef(y_true, y_pred)


def bce_dice_loss(y_true, y_pred):
    return BinaryCrossentropy()(y_true, y_pred) + dice_loss(y_true, y_pred)


def iou_metric(y_true, y_pred, smooth=1e-6):
    y_pred = K.cast(y_pred > 0.5, 'float32')
    y_true = K.flatten(y_true)
    y_pred = K.flatten(y_pred)
    intersection = K.sum(y_true * y_pred)
    union = K.sum(y_true) + K.sum(y_pred) - intersection
    return (intersection + smooth) / (union + smooth)

model.compile(optimizer=Adam(learning_rate=1e-4), loss=bce_dice_loss, metrics=['accuracy', iou_metric])

# 6. Train
if len(X_train) == 0 or len(X_val) == 0:
    raise RuntimeError('No training or validation patches were loaded. Check the v1.1 dataset paths.')

# Use tf.data for efficient loading and parallel processing
def create_dataset(x, y, batch_size=32, shuffle=True):
    ds = tf.data.Dataset.from_tensor_slices((x, y))
    if shuffle:
        ds = ds.shuffle(buffer_size=min(1000, len(x)))
    ds = ds.batch(batch_size, drop_remainder=True)
    ds = ds.prefetch(tf.data.AUTOTUNE)
    return ds

train_ds = create_dataset(X_train, Y_train, batch_size=64, shuffle=True)
val_ds = create_dataset(X_val, Y_val, batch_size=64, shuffle=False)

print('Training segmentation model...')
print(f'Total training samples: {len(X_train)}, validation samples: {len(X_val)}')
history = model.fit(
    train_ds,
    validation_data=val_ds,
    epochs=10,
    steps_per_epoch=None,
)

# 7. Save model and metrics
model_path = os.path.join(models_dir, 'vision', 'resnet50_sar_segmentation.h5')
model.save(model_path)
print(f'Saved ResNet50 U-Net segmentation model to {model_path}')

metrics_path = os.path.join(models_dir, 'metrics.json')
metrics = {}
if os.path.exists(metrics_path):
    try:
        metrics = pd.read_json(metrics_path, typ='series').to_dict()
    except Exception:
        metrics = {}
metrics['resnet50_segmentation_accuracy'] = f"{history.history['val_accuracy'][-1] * 100:.2f}%"
metrics['resnet50_segmentation_iou'] = f"{history.history['val_iou_metric'][-1] * 100:.2f}%"
with open(metrics_path, 'w') as f:
    import json
    json.dump(metrics, f, indent=4)

# 8. Plot training
plt.figure(figsize=(12, 5))
plt.subplot(1, 2, 1)
plt.plot(history.history['accuracy'], label='train_acc')
plt.plot(history.history['val_accuracy'], label='val_acc')
plt.title('Accuracy')
plt.legend()
plt.grid(True)

plt.subplot(1, 2, 2)
plt.plot(history.history['loss'], label='train_loss')
plt.plot(history.history['val_loss'], label='val_loss')
plt.title('Loss')
plt.legend()
plt.grid(True)
plt.tight_layout()
plot_path = os.path.join(models_dir, 'vision', 'resnet50_sar_segmentation_training.png')
plt.savefig(plot_path, dpi=150)
print(f'Saved training plot to {plot_path}')
print('ResNet50 Vision Pipeline completely executed.')
