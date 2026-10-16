import os
import pandas as pd
import numpy as np
import rasterio
from tensorflow.keras.applications import ResNet50
from tensorflow.keras.layers import Dense, GlobalAveragePooling2D
from tensorflow.keras.models import Model
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import matplotlib.pyplot as plt

# Paths
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data_dir = os.path.join(base_dir, 'data', 'raw', 'v1.1')
splits_dir = os.path.join(data_dir, 'splits', 'flood_handlabeled')
images_dir = os.path.join(data_dir, 'data', 'flood_events', 'HandLabeled', 'S1Hand')
labels_dir = os.path.join(data_dir, 'data', 'flood_events', 'HandLabeled', 'LabelHand')
models_dir = os.path.join(base_dir, 'models', 'vision')
os.makedirs(models_dir, exist_ok=True)

# Load splits
train_df = pd.read_csv(os.path.join(splits_dir, 'flood_train_data.csv'), header=None, names=['image', 'label'])
val_df = pd.read_csv(os.path.join(splits_dir, 'flood_valid_data.csv'), header=None, names=['image', 'label'])
test_df = pd.read_csv(os.path.join(splits_dir, 'flood_test_data.csv'), header=None, names=['image', 'label'])

# Function to load and preprocess image
def load_image(img_path, label_path, target_size=(224, 224)):
    with rasterio.open(img_path) as src:
        img = src.read(1)  # Read first band (SAR is single band)
    
    # Handle NaN
    img = np.nan_to_num(img, nan=0.0)
    
    # Normalize
    if np.max(img) > np.min(img):
        img = (img - np.min(img)) / (np.max(img) - np.min(img))
    else:
        img = np.zeros_like(img)
    
    # Resize
    from skimage.transform import resize
    img = resize(img, target_size, mode='constant')
    
    # Convert to 3 channels
    img = np.stack([img] * 3, axis=-1)
    
    # Load label
    with rasterio.open(label_path) as src:
        label = src.read(1)
    
    # Check if has flood
    has_flood = np.any(label > 0)
    
    return img, int(has_flood)

# Load data
def load_data(df):
    images = []
    labels = []
    for _, row in df.iterrows():
        img_path = os.path.join(images_dir, row['image'])
        label_path = os.path.join(labels_dir, row['label'])
        if os.path.exists(img_path) and os.path.exists(label_path):
            img, label = load_image(img_path, label_path)
            images.append(img)
            labels.append(label)
    return np.array(images), np.array(labels)

print("Loading training data...")
X_train, y_train = load_data(train_df)
print("Loading validation data...")
X_val, y_val = load_data(val_df)
print("Loading test data...")
X_test, y_test = load_data(test_df)

# Balance the training data
from imblearn.over_sampling import RandomOverSampler
ros = RandomOverSampler(random_state=42)
X_train_flat = X_train.reshape(X_train.shape[0], -1)
X_train_balanced, y_train_balanced = ros.fit_resample(X_train_flat, y_train)
X_train_balanced = X_train_balanced.reshape(-1, 224, 224, 3)

print(f"Balanced Train: {X_train_balanced.shape}, {y_train_balanced.shape}")
print(f"Val: {X_val.shape}, {y_val.shape}")
print(f"Test: {X_test.shape}, {y_test.shape}")

# Build model
base_model = ResNet50(weights='imagenet', include_top=False, input_shape=(224, 224, 3))
x = base_model.output
x = GlobalAveragePooling2D()(x)
x = Dense(1024, activation='relu')(x)
predictions = Dense(1, activation='sigmoid')(x)
model = Model(inputs=base_model.input, outputs=predictions)

# Freeze base layers
for layer in base_model.layers:
    layer.trainable = False

# Compile
model.compile(optimizer=Adam(learning_rate=0.001), loss='binary_crossentropy', metrics=['accuracy'])

# Train
from sklearn.utils.class_weight import compute_class_weight
class_weights = compute_class_weight('balanced', classes=np.unique(y_train_balanced), y=y_train_balanced)
class_weights = dict(enumerate(class_weights))

history = model.fit(X_train_balanced, y_train_balanced, validation_data=(X_val, y_val), epochs=20, batch_size=32, class_weight=class_weights)

# Unfreeze some layers
for layer in base_model.layers[-10:]:
    layer.trainable = True

model.compile(optimizer=Adam(learning_rate=0.0001), loss='binary_crossentropy', metrics=['accuracy'])

history2 = model.fit(X_train_balanced, y_train_balanced, validation_data=(X_val, y_val), epochs=20, batch_size=32, class_weight=class_weights)

# Evaluate
y_pred = (model.predict(X_test) > 0.5).astype(int)
print(classification_report(y_test, y_pred))

# Save model
model.save(os.path.join(models_dir, 'resnet50_flood_classification.h5'))

# Plot history
train_acc = history.history['accuracy'] + history2.history['accuracy']
val_acc = history.history['val_accuracy'] + history2.history['val_accuracy']
plt.plot(train_acc)
plt.plot(val_acc)
plt.title('Model accuracy')
plt.ylabel('Accuracy')
plt.xlabel('Epoch')
plt.legend(['Train', 'Val'], loc='upper left')
plt.savefig(os.path.join(models_dir, 'resnet50_accuracy.png'))
# plt.show()  # Remove to avoid display issues