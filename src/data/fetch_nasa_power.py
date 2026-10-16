import json
import urllib.request
import urllib.parse
import urllib.error
import os

API_KEY = "zdb1iehwyUDBmyH2IZGLbUyPdabU8fHE5N85SY6b"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW_DATA_DIR = os.path.join(BASE_DIR, "data", "raw")

def fetch_nasa_earth_imagery(lon=77.2090, lat=28.6139, date="2021-01-01"):
    """
    Fetches Landsat satellite imagery from NASA Earth API.
    Useful for training the CNN/ViT models for flood detection.
    """
    print(f"Fetching NASA Earth imagery for {lon}, {lat} at {date}...")
    url = f"https://api.nasa.gov/planetary/earth/assets?lon={lon}&lat={lat}&date={date}&dim=0.15&api_key={API_KEY}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            # Save the metadata (which contains the URL to the image)
            output_file = os.path.join(RAW_DATA_DIR, "nasa_earth_imagery_meta.json")
            with open(output_file, 'w') as f:
                json.dump(data, f, indent=4)
            print(f"Saved Earth imagery metadata to {output_file}")
            print("Earth API Response keys:", list(data.keys()))
            if 'url' in data:
                print(f"Image Download URL: {data['url']}")
    except urllib.error.HTTPError as e:
        print(f"HTTP Error for Earth API: {e.code} - {e.reason}")
    except Exception as e:
        print(f"Error fetching Earth imagery: {e}")

def fetch_nasa_power_weather(lon=77.2090, lat=28.6139, start="20210101", end="20210131"):
    """
    Fetches daily rainfall and weather data from NASA POWER API.
    Useful for LSTM rainfall prediction and clustering.
    """
    print(f"\nFetching NASA POWER weather data for {lon}, {lat} from {start} to {end}...")
    url = f"https://power.larc.nasa.gov/api/temporal/daily/point?parameters=PRECTOTCORR,T2M,RH2M&community=RE&longitude={lon}&latitude={lat}&start={start}&end={end}&format=JSON"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            # Save the weather data
            output_file = os.path.join(RAW_DATA_DIR, "nasa_power_weather.json")
            with open(output_file, 'w') as f:
                json.dump(data, f, indent=4)
            print(f"Saved POWER weather data to {output_file}")
            print("POWER API Response keys:", list(data.keys()))
    except urllib.error.HTTPError as e:
        print(f"HTTP Error for POWER API: {e.code} - {e.reason}")
    except Exception as e:
        print(f"Error fetching POWER data: {e}")

if __name__ == "__main__":
    os.makedirs(RAW_DATA_DIR, exist_ok=True)
    fetch_nasa_earth_imagery()
    fetch_nasa_power_weather()
