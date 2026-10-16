import os
import pandas as pd
import numpy as np
import rasterio
from tensorflow.keras.applications import ResNet50
from tensorflow.keras.layers import Dense, GlobalAveragePooling2D
from tensorflow.keras.models import Model
from tensorflow.keras.optimizers import Adam
from sklearn.utils.class_weight import compute_class_weight
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score, roc_curve
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Paths
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data_dir = os.path.join(base_dir, 'data', 'raw', 'v1.1')
splits_dir = os.path.join(data_dir, 'splits', 'flood_handlabeled')
images_dir = os.path.join(data_dir, 'data', 'flood_events', 'HandLabeled', 'S1Hand')
labels_dir = os.path.join(data_dir, 'data', 'flood_events', 'HandLabeled', 'LabelHand')
models_dir = os.path.join(base_dir, 'models', 'vision')
os.makedirs(models_dir, exist_ok=True)

# Patch configuration
PATCH_SIZE = 64
PATCH_STRIDE = 32

# Load splits
train_df = pd.read_csv(os.path.join(splits_dir, 'flood_train_data.csv'), header=None, names=['image', 'label'])
val_df = pd.read_csv(os.path.join(splits_dir, 'flood_valid_data.csv'), header=None, names=['image', 'label'])
test_df = pd.read_csv(os.path.join(splits_dir, 'flood_test_data.csv'), header=None, names=['image', 'label'])

# Function to load image
def load_image(img_path):
    with rasterio.open(img_path) as src:
        img = src.read(1)
    img = np.nan_to_num(img, nan=0.0)
    return img

# Function to load label
def load_label(label_path):
    with rasterio.open(label_path) as src:
        label = src.read(1)
    return label

# Function to extract patches with labels
def extract_patches(img, label, patch_size=64, stride=32):
    patches = []
    patch_labels = []
    
    h, w = img.shape
    for y in range(0, h - patch_size + 1, stride):
        for x in range(0, w - patch_size + 1, stride):
            patch = img[y:y+patch_size, x:x+patch_size]
            patch_label = label[y:y+patch_size, x:x+patch_size]
            
            # Check if patch is valid
            if patch.shape == (patch_size, patch_size):
                # Label: 1 if any flood pixel, 0 otherwise
                label_value = 1 if np.any(patch_label > 0) else 0
                patches.append(patch)
                patch_labels.append(label_value)
    
    return patches, patch_labels

# Load data and extract patches
def load_patches_dataset(df):
    all_patches = []
    all_labels = []
    
    for idx, row in df.iterrows():
        img_path = os.path.join(images_dir, row['image'])
        label_path = os.path.join(labels_dir, row['label'])
        
        if os.path.exists(img_path) and os.path.exists(label_path):
            img = load_image(img_path)
            label = load_label(label_path)
            
            patches, patch_labels = extract_patches(img, label, PATCH_SIZE, PATCH_STRIDE)
            all_patches.extend(patches)
            all_labels.extend(patch_labels)
    
    return np.array(all_patches), np.array(all_labels)

print("Extracting patches from training data...")
X_train_patches, y_train_patches = load_patches_dataset(train_df)
print(f"Training patches: {X_train_patches.shape}, Labels: {y_train_patches.shape}")

print("Extracting patches from validation data...")
X_val_patches, y_val_patches = load_patches_dataset(val_df)
print(f"Validation patches: {X_val_patches.shape}, Labels: {y_val_patches.shape}")

print("Extracting patches from test data...")
X_test_patches, y_test_patches = load_patches_dataset(test_df)
print(f"Test patches: {X_test_patches.shape}, Labels: {y_test_patches.shape}")

# Preprocess patches
def preprocess_patches(patches):
    # Normalize each patch
    normalized = np.zeros((patches.shape[0], PATCH_SIZE, PATCH_SIZE, 3))
    for i in range(patches.shape[0]):
        patch = patches[i]
        if np.max(patch) > np.min(patch):
            patch = (patch - np.min(patch)) / (np.max(patch) - np.min(patch))
        # Convert to 3 channels
        normalized[i] = np.stack([patch, patch, patch], axis=-1)
    return normalized

print("Preprocessing patches...")
X_train = preprocess_patches(X_train_patches)
X_val = preprocess_patches(X_val_patches)
X_test = preprocess_patches(X_test_patches)

print(f"Final datasets:")
print(f"Train: {X_train.shape}, {y_train_patches.shape}")
print(f"Val: {X_val.shape}, {y_val_patches.shape}")
print(f"Test: {X_test.shape}, {y_test_patches.shape}")

# Class distribution
unique_train, counts_train = np.unique(y_train_patches, return_counts=True)
print(f"Train class distribution: {dict(zip(unique_train, counts_train))}")
unique_test, counts_test = np.unique(y_test_patches, return_counts=True)
print(f"Test class distribution: {dict(zip(unique_test, counts_test))}")

# Build model
base_model = ResNet50(weights='imagenet', include_top=False, input_shape=(PATCH_SIZE, PATCH_SIZE, 3))
x = base_model.output
x = GlobalAveragePooling2D()(x)
x = Dense(512, activation='relu')(x)
x = Dense(128, activation='relu')(x)
predictions = Dense(1, activation='sigmoid')(x)
model = Model(inputs=base_model.input, outputs=predictions)

# Freeze base layers
for layer in base_model.layers:
    layer.trainable = False

# Compile
model.compile(optimizer=Adam(learning_rate=0.001), loss='binary_crossentropy', metrics=['accuracy', 'AUC'])

# Compute class weights
class_weights = compute_class_weight('balanced', classes=np.unique(y_train_patches), y=y_train_patches)
class_weights = dict(enumerate(class_weights))
print(f"Class weights: {class_weights}")

# Train with frozen base
print("\n=== Phase 1: Training with frozen base ===")
history = model.fit(X_train, y_train_patches, 
                    validation_data=(X_val, y_val_patches), 
                    epochs=15, batch_size=64, class_weight=class_weights, 
                    verbose=1)

# Unfreeze some layers
print("\n=== Phase 2: Fine-tuning last layers ===")
for layer in base_model.layers[-10:]:
    layer.trainable = True

model.compile(optimizer=Adam(learning_rate=0.0001), loss='binary_crossentropy', metrics=['accuracy', 'AUC'])

history2 = model.fit(X_train, y_train_patches, 
                     validation_data=(X_val, y_val_patches), 
                     epochs=10, batch_size=64, class_weight=class_weights,
                     verbose=1)

# Evaluate
print("\n=== Evaluation ===")
y_pred_probs = model.predict(X_test)
y_pred = (y_pred_probs > 0.5).astype(int).reshape(-1)

# Metrics
print(classification_report(y_test_patches, y_pred, zero_division=0))

# ROC-AUC
try:
    auc_score = roc_auc_score(y_test_patches, y_pred_probs)
    print(f"ROC-AUC Score: {auc_score:.4f}")
except:
    print("Cannot compute ROC-AUC (possibly due to single class)")

# Confusion Matrix
cm = confusion_matrix(y_test_patches, y_pred)
print(f"Confusion Matrix:\n{cm}")

# Accuracy metrics
tn, fp, fn, tp = cm.ravel()
accuracy = (tp + tn) / (tp + tn + fp + fn)
precision = tp / (tp + fp) if (tp + fp) > 0 else 0
recall = tp / (tp + fn) if (tp + fn) > 0 else 0
f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

print(f"\nDetailed Metrics:")
print(f"Accuracy: {accuracy:.4f}")
print(f"Precision: {precision:.4f}")
print(f"Recall: {recall:.4f}")
print(f"F1-Score: {f1:.4f}")

# Save model
model.save(os.path.join(models_dir, 'resnet50_patch_classifier.h5'))
print(f"Model saved to {os.path.join(models_dir, 'resnet50_patch_classifier.h5')}")

# Plot history
plt.figure(figsize=(15, 5))

plt.subplot(1, 3, 1)
plt.plot(history.history['accuracy'] + history2.history['accuracy'])
plt.plot(history.history['val_accuracy'] + history2.history['val_accuracy'])
plt.title('Model Accuracy')
plt.ylabel('Accuracy')
plt.xlabel('Epoch')
plt.legend(['Train', 'Val'], loc='lower right')
plt.grid(True)

plt.subplot(1, 3, 2)
plt.plot(history.history['loss'] + history2.history['loss'])
plt.plot(history.history['val_loss'] + history2.history['val_loss'])
plt.title('Model Loss')
plt.ylabel('Loss')
plt.xlabel('Epoch')
plt.legend(['Train', 'Val'], loc='upper right')
plt.grid(True)

plt.subplot(1, 3, 3)
plt.bar(['No Flood', 'Flood'], [tn, tp])
plt.title('Test Predictions')
plt.ylabel('Count')
plt.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(os.path.join(models_dir, 'resnet50_patch_training.png'), dpi=150)
print(f"Training plot saved to {os.path.join(models_dir, 'resnet50_patch_training.png')}")
