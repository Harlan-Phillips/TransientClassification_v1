
import requests

FRITZ_API_TOKEN = ''
FRITZ_BASE_URL = 'https://fritz.science/api'

def fetch_photometry_data_for_source(source_id):
    base_url = f"{FRITZ_BASE_URL}/sources/{source_id}/photometry"
    headers = {'Authorization': f'token {FRITZ_API_TOKEN}'}
    params = {
        "format": "mag",   # Return the photometry in magnitude space
        "magsys": "ab",    # The magnitude or zeropoint system of the output
    }

    response = requests.get(base_url, params=params, headers=headers)

    if response.status_code != 200:
        print(f"Error fetching photometry data for source {source_id}: {response.status_code}")
        return []

    data = response.json()
    print("Raw Photometry API Response:", data)  # Debug: Print raw response data

    if data["status"] != "success":
        print(data)
        return []

    photometry = data["data"]
    print(f"Fetched Photometry Data for source {source_id}:", photometry)  # Debug: Print fetched photometry data
    return photometry

def fetch_source_data(page_number):
    base_url = f"{FRITZ_BASE_URL}/sources"
    headers = {'Authorization': f'token {FRITZ_API_TOKEN}'}
    params = {
        "numPerPage": 10,   # Number of sources per page
        "pageNumber": page_number,    # Page number to fetch
    }

    response = requests.get(base_url, params=params, headers=headers)

    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        return []

    data = response.json()
    print("Raw Source API Response:", data)  # Debug: Print raw response data

    if data["status"] != "success":
        print(data)
        return []

    sources = data["data"]["sources"]
    print("Fetched Sources Data:", sources)  # Debug: Print fetched sources
    return sources