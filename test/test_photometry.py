import os
import requests
import pandas as pd
from datetime import datetime
from astropy.time import Time
from matplotlib import pyplot as plt
from flask_sqlalchemy import SQLAlchemy
from flask import Flask
from sqlalchemy.orm import sessionmaker

# Configuration
FRITZ_API_TOKEN = ''
FRITZ_BASE_URL = 'https://fritz.science/api'
basedir = os.path.abspath(os.path.dirname(__file__))

# Create Flask app instance
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = 'sqlite:///' + os.path.join(basedir, 'test.db')
app.config['SECRET_KEY'] = 'your_secret_key_here'
db = SQLAlchemy(app)

class SourceData(db.Model):
    __tablename__ = 'source_table'
    id = db.Column(db.Integer, primary_key=True)
    obj_id = db.Column(db.String, nullable=True, unique=True)
    ra = db.Column(db.Float, nullable=True)
    dec = db.Column(db.Float, nullable=True)
    redshift = db.Column(db.Float, nullable=True)
    transient = db.Column(db.Boolean, nullable=True)
    varstar = db.Column(db.Boolean, nullable=True)
    is_roid = db.Column(db.Boolean, nullable=True)

class PhotometryData(db.Model):
    __tablename__ = 'photometry_table'
    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.Integer, db.ForeignKey('source_table.id'))
    mjd = db.Column(db.Float, nullable=False)
    mag = db.Column(db.Float, nullable=True)
    filter = db.Column(db.String, nullable=True)
    limiting_mag = db.Column(db.Float, nullable=True)

# Create database tables
with app.app_context():
    db.create_all()

def fetch_photometry_data_for_source(source_id):
    base_url = f"{FRITZ_BASE_URL}/sources/{source_id}/photometry"
    headers = {'Authorization': f'token {FRITZ_API_TOKEN}'}
    params = {
        "format": "mag",
        "magsys": "ab",
    }

    response = requests.get(base_url, params=params, headers=headers)

    if response.status_code != 200:
        print(f"Error fetching photometry data for source {source_id}: {response.status_code}")
        return []

    data = response.json()
    print("Raw Photometry API Response:", data)

    if data["status"] != "success":
        print(f"API error for source {source_id}: {data}")
        return []

    photometry = data["data"]
    print(f"Fetched Photometry Data for source {source_id}: {photometry}")
    return photometry

def mjd_to_days_ago(mjd):
    current_time = Time(datetime.utcnow())
    mjd_time = Time(mjd, format='mjd')
    days_ago = (current_time - mjd_time).value
    return days_ago

def plot_photometry(source_id):
    with app.app_context():
        source = SourceData.query.filter_by(obj_id=source_id).first()
        if not source:
            print(f"No source found with obj_id {source_id}")
            return

        photometry_data = PhotometryData.query.filter_by(source_id=source.id).all()
        if not photometry_data:
            print(f"No photometry data found for source {source_id}")
            return

        data = [{'obj_id': source_id, 'mjd': p.mjd, 'mag': p.mag, 'filter': p.filter, 'limiting_mag': p.limiting_mag} for p in photometry_data]

        for d in data:
            d['days_ago'] = mjd_to_days_ago(d['mjd'])

        df = pd.DataFrame(data)

        plt.style.use('ggplot')
        plt.figure(figsize=(10, 6))
        for filter_name in df['filter'].unique():
            df_filter = df[df['filter'] == filter_name]
            plt.scatter(df_filter['days_ago'], df_filter['mag'], label=filter_name)
            plt.plot(df_filter['days_ago'], df_filter['mag'], linestyle='--')

        for filter_name in df['filter'].unique():
            df_filter = df[df['filter'] == filter_name]
            plt.scatter(df_filter['days_ago'], df_filter['limiting_mag'], label=f"{filter_name} (limiting)", marker='^')
            plt.plot(df_filter['days_ago'], df_filter['limiting_mag'], linestyle=':')

        plt.gca().invert_xaxis()
        plt.gca().invert_yaxis()
        plt.xlabel('Days Ago')
        plt.ylabel('Magnitude')
        plt.title(f'Photometry for Source {source_id}')
        plt.legend()
        plt.grid(True)

        plot_filename = f'photometry_{source_id}.png'
        plt.savefig(plot_filename)
        plt.close()
        print(f"Plot saved as {plot_filename}")

def main():
    source_id = 'your_source_id_here'  # Replace with a valid source ID
    photometry_data = fetch_photometry_data_for_source(source_id)

    if not photometry_data:
        print(f"No photometry data fetched for source {source_id}. Exiting.")
        return

    with app.app_context():
        source = SourceData.query.filter_by(obj_id=source_id).first()
        if not source:
            source = SourceData(obj_id=source_id, ra=0, dec=0, redshift=0, transient=False, varstar=False, is_roid=False)
            db.session.add(source)
            db.session.commit()

        for photometry in photometry_data:
            new_photometry_entry = PhotometryData(
                source_id=source.id,
                mjd=photometry['mjd'],
                mag=photometry.get('mag'),
                filter=photometry.get('filter'),
                limiting_mag=photometry.get('limiting_mag')
            )
            db.session.add(new_photometry_entry)
            db.session.commit()

    plot_photometry(source_id)

if __name__ == "__main__":
    main()