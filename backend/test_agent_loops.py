import requests
import json
import time

API_URL = "http://localhost:8001/api/v1/chat"

def run_test(case_name, query, history=[], current_city="mumbai"):
    print(f"\n--- TEST CASE: {case_name} ---")
    print(f"User: {query}")
    
    payload = {
        "message": query,
        "history": history,
        "city": current_city
    }
    
    try:
        start_time = time.time()
        resp = requests.post(API_URL, json=payload)
        latency = time.time() - start_time
        
        if resp.status_code == 200:
            data = resp.json()
            print(f"AI: {data.get('reply')}")
            print(f"Latency: {latency:.2f}s")
            return data
        else:
            print(f"Error {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"Connection Error: {e}")

if __name__ == "__main__":
    print("starting Agent Loop Verification...")
    
    # 1. Historical Query
    run_test("Historical Query", "What was the flood risk in Mumbai on August 27, 2017?")
    
    # 2. Forecast Query
    run_test("Forecast Query", "What is the forecast risk for Bengaluru tomorrow?")
    
    # 3. Contextual Follow-up
    res = run_test("Entity Discovery", "Check Pune risk status.")
    if res:
        run_test("Contextual Follow-up", "Why is it at that level?", history=[
            {"role": "user", "text": "Check Pune risk status."},
            {"role": "ai", "text": res['reply']}
        ], current_city=res.get('city', 'pune'))
    
    # 4. Unsupported City
    run_test("Unsupported City", "How is the weather in Delhi?")
    
    # 5. Domain Guardrail
    run_test("Guardrail Rejection", "Can you explain how to bake a cake?")
