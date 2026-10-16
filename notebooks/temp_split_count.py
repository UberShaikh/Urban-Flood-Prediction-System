import pandas as pd
import os
base = 'C:/Users/Admin/OneDrive/Desktop/PA/flood-ai-system/data/raw/v1.1/splits/flood_handlabeled'
for name in ['flood_train_data.csv','flood_valid_data.csv','flood_test_data.csv']:
    df = pd.read_csv(os.path.join(base, name), header=None)
    print(name, len(df))
