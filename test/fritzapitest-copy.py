import os
import requests
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime
from astropy.time import Time

# Replace with your actual Fritz API token
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
    print("Raw Source API Response:", data)  # Debug: Print raw response data

    if data["status"] != "success":
        print(data)
        return []

    sources = data["data"]["sources"]
    print("Fetched Sources Data:", sources)  # Debug: Print fetched sources
    return sources

def mjd_to_days_ago(mjd):
    current_time = Time(datetime.utcnow())
    mjd_time = Time(mjd, format='mjd')
    days_ago = (current_time - mjd_time).value
    return days_ago

if __name__ == "__main__":
    sources = fetch_source_data()
    
    for source in sources[:3]:  # Get the first 3 sources
        source_id = source['id']
        photometry_data = fetch_photometry_data_for_source(source_id)
        print(f"Photometry Data for Source {source_id}: {photometry_data}")
        if photometry_data:
            data = photometry_data
            
            # Convert MJD to days ago
            for d in data:
                d['days_ago'] = mjd_to_days_ago(d['mjd'])

            # Convert the data to a DataFrame
            df = pd.DataFrame(data)

            # Create the plot
            plt.figure(figsize=(10, 6))
            for filter_name in df['filter'].unique():
                df_filter = df[df['filter'] == filter_name]
                plt.scatter(df_filter['days_ago'], df_filter['mag'], label=filter_name)
                plt.plot(df_filter['days_ago'], df_filter['mag'], linestyle='--')

            # Plot limiting magnitudes as well (dashed lines)
            for filter_name in df['filter'].unique():
                df_filter = df[df['filter'] == filter_name]
                plt.scatter(df_filter['days_ago'], df_filter['limiting_mag'], label=f"{filter_name} (limiting)", marker='^')
                plt.plot(df_filter['days_ago'], df_filter['limiting_mag'], linestyle=':')

            plt.gca().invert_xaxis()  # Invert the x-axis to show 0 days ago on the far right
            plt.gca().invert_yaxis()  # Magnitude is inversely related to brightness
            plt.xlabel('Days Ago')
            plt.ylabel('Magnitude')
            plt.title(f'Photometry for Source {source_id}')
            plt.legend()
            plt.grid(True)

            plot_filename = f'photometry_{source_id}.png'
            plt.savefig(plot_filename)
            plt.close()

            print(f"Saved plot for source {source_id} as {plot_filename}")