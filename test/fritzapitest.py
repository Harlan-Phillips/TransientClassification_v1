

import requests

# Replace with your actual Fritz API token
FRITZ_API_TOKEN = ''
FRITZ_BASE_URL = 'https://fritz.science/api'

def fetch_source_data():
    base_url = f"{FRITZ_BASE_URL}/sources"
    headers = {'Authorization': f'token {FRITZ_API_TOKEN}'}
    params = {
        "numPerPage": 10,   # Number of sources per page
        "pageNumber": 1,    # Page number to fetch
    }

    response = requests.get(base_url, params=params, headers=headers)

    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        return []

    data = response.json()
    print("Raw API Response:", data)  # Debug: Print raw response data

    if data["status"] != "success":
        print(data)
        return []

    sources = data["data"]["sources"]
    print("Fetched Sources Data:", sources)  # Debug: Print fetched sources
    return sources

if __name__ == "__main__":
    sources = fetch_source_data()
    for candidate in sources:
        print(candidate)