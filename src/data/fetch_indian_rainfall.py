import json
import urllib.request
import urllib.error
import os

API_KEY = "579b464db66ec23bdd000001545e5f2c26b64b3240043d79decc39c1"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW_DATA_DIR = os.path.join(BASE_DIR, "data", "raw")

def fetch_indian_rainfall_data(resource_id="38b00eb0-6ca5-46fd-bab0-329cc647b05c", limit=1000):
    """
    Fetches district-wise rainfall data from data.gov.in API.
    Used for clustering and feeding chronological data to the LSTM model.
    Note: 'resource_id' should point to the specific dataset table ID on data.gov.in.
    """
    print(f"Fetching Indian District-wise Rainfall data from data.gov.in...")
    
    # Constructing the API URL
    url = f"https://api.data.gov.in/resource/{resource_id}?api-key={API_KEY}&format=json&limit={limit}"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            # Save the dataset to data/raw
            output_file = os.path.join(RAW_DATA_DIR, "district_rainfall_data.json")
            with open(output_file, 'w') as f:
                json.dump(data, f, indent=4)
                
            print(f"Successfully saved {len(data.get('records', []))} records to {output_file}")
            
            if data.get('records'):
                print("Sample record keys:", list(data['records'][0].keys()))
                print("First record:", data['records'][0])
                
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.reason}. Please verify the resource_id.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    os.makedirs(RAW_DATA_DIR, exist_ok=True)
    fetch_indian_rainfall_data()
