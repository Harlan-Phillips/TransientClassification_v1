import requests
import matplotlib.pyplot as plt
import itertools

# Constants
FRITZ_API_TOKEN = ''
FRITZ_BASE_URL = 'https://fritz.science/api'

def fetch_light_curve(ra, dec, radius=0.001, catalog="ZTF_sources_20240515", radius_units="deg"):
    base_url = f"{FRITZ_BASE_URL}/archive"
    headers = {'Authorization': f'token {FRITZ_API_TOKEN}'}
    params = {
        "catalog": catalog,
        "ra": ra,
        "dec": dec,
        "radius": radius,
        "radius_units": radius_units
    }

    response = requests.get(base_url, params=params, headers=headers)

    if response.status_code != 200:
        print(f"Error fetching light curve: {response.status_code}")
        return None

    data = response.json()
    if data["status"] != "success":
        print(data)
        return None

    return data["data"]

def plot_light_curve(light_curve_data, obj_id):
    if not light_curve_data:
        print(f"No light curve data found for {obj_id}")
        return

    colors = itertools.cycle(['r', 'g', 'b', 'c', 'm', 'y', 'k'])
    filters = {}

    for lc in light_curve_data:
        filter_id = lc.get('filter', 'unknown')
        if filter_id not in filters:
            filters[filter_id] = next(colors)
        color = filters[filter_id]

        dates = [point['hjd'] for point in lc.get('data', [])]
        magnitudes = [point['mag'] for point in lc.get('data', [])]
        errors = [point['magerr'] for point in lc.get('data', [])]

        if dates and magnitudes:
            plt.errorbar(dates, magnitudes, yerr=errors, fmt='o', color=color, label=f"Filter {filter_id}")

    plt.xlabel("HJD")
    plt.ylabel("Magnitude")
    plt.title(f"Light Curve for {obj_id}")
    plt.gca().invert_yaxis()
    plt.legend()
    plt.show()



def test_fetch_light_curve():
    ra = 102.933625
    dec = 44.352139
    obj_id = "2024kwu"

    light_curve_data = fetch_light_curve(ra, dec)
    plot_light_curve(light_curve_data, obj_id)

if __name__ == '__main__':
    test_fetch_light_curve()