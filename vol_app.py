# Import modules
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo
import requests
import pandas as pd
import numpy as np
import os
import time
from sqlalchemy.orm import sessionmaker
from matplotlib import pyplot as plt
from datetime import datetime
from astropy.time import Time
import base64
from io import BytesIO
from APIfunc import fetch_photometry_data_for_source, fetch_source_data


basedir = os.path.abspath(os.path.dirname(__file__))

# Create flask app instance
vol_app = Flask(__name__)
vol_app.config["SQLALCHEMY_DATABASE_URI"] = 'sqlite:///' + os.path.join(basedir, 'vol_app.db')
vol_app.config['SECRET_KEY'] = 'your_secret_key_here'

db = SQLAlchemy(vol_app)
ma = Marshmallow(vol_app)
login_manager = LoginManager()
login_manager.init_app(vol_app)
login_manager.login_view = 'login'

FRITZ_API_TOKEN = 'your-token-here'
FRITZ_BASE_URL = 'https://fritz.science/api'

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
    mjd = db.Column(db.Float, nullable=True)  # Add this line

    def __init__(self, obj_id, ra, dec, redshift, transient, varstar, is_roid, mjd=None) -> None:
        super(SourceData, self).__init__()
        self.obj_id = obj_id
        self.ra = ra
        self.dec = dec
        self.redshift = redshift
        self.transient = transient
        self.varstar = varstar
        self.is_roid = is_roid
        self.mjd = mjd

    def __repr__(self) -> str:
        return '<SourceData %r>' % self.obj_id

class PhotometryData(db.Model):
    __tablename__ = 'photometry_table'
    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.Integer, db.ForeignKey('source_table.id'))
    mjd = db.Column(db.Float, nullable=False)
    mag = db.Column(db.Float, nullable=True)
    filter = db.Column(db.String, nullable=True)
    limiting_mag = db.Column(db.Float, nullable=True)

    def __init__(self, source_id, mjd, mag, filter, limiting_mag) -> None:
        super(PhotometryData, self).__init__()
        self.source_id = source_id
        self.mjd = mjd
        self.mag = mag
        self.filter = filter
        self.limiting_mag = limiting_mag


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

if not os.path.exists('page_number.txt'):
    with open('page_number.txt', 'w') as file:
        file.write('1')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class SourceDataSchema(ma.Schema):
    class Meta:
        fields = ('id', 'obj_id', 'ra', 'dec', 'redshift', 'transient', 'varstar', 'is_roid', 'mjd')

single_source_data_schema = SourceDataSchema()
multiple_source_data_schema = SourceDataSchema(many=True)

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

with vol_app.app_context():
    db.create_all()

def get_current_page():
    try:
        with open('page_number.txt', 'r') as file:
            page_number = int(file.read().strip())
    except FileNotFoundError:
        page_number = 1
    return page_number

def increment_page_number():
    current_page = get_current_page()
    next_page = current_page + 1
    with open('page_number.txt', 'w') as file:
        file.write(str(next_page))
    return next_page

@vol_app.route('/fetch_sources', methods=['GET'])
def add_source_data():
    current_page = increment_page_number()
    sources = fetch_source_data(current_page)

    entry_list = []

    with vol_app.app_context():
        Session = sessionmaker(bind=db.engine)
        session = Session()

        try:
            for source in sources:
                if isinstance(source, dict):
                    # Check if the source already exists in the database
                    existing_entry = session.query(SourceData).filter_by(obj_id=source.get('id')).first()
                    if existing_entry:
                        print(f"Source {source.get('id')} already exists in the database. Skipping.")
                        continue

                    new_entry = SourceData(
                        obj_id=source.get('id'),
                        ra=source.get('ra'),
                        dec=source.get('dec'),
                        redshift=source.get('redshift'),
                        transient=source.get('transient', True),  # Default to False if not present
                        varstar=source.get('varstar', False),  # Default to False if not present
                        is_roid=source.get('is_roid', False),  # Default to False if not present
                        mjd=source.get('mjd')
                    )
                    session.add(new_entry)
                    session.commit()  # Commit the session to get the ID for the new entry
                    entry_list.append(new_entry)
                    print(f'Created entry: {new_entry}')  # Debug: Print created entry
                else:
                    print("Unexpected data format:", source)

                try:
                    # Fetch photometry data for each source and add to photometry table
                    photometry_data = fetch_photometry_data_for_source(new_entry.obj_id)
                    if not photometry_data:
                        continue  # Skip to next source if no photometry data is found

                    for photometry in photometry_data:
                        new_photometry_entry = PhotometryData(
                            source_id=new_entry.id,
                            mjd=photometry['mjd'],
                            mag=photometry['mag'],
                            filter=photometry['filter'],
                            limiting_mag=photometry['limiting_mag']
                        )
                        session.add(new_photometry_entry)
                        session.commit()
                        print(f'Added photometry data for {new_entry.obj_id} to db.')

                except Exception as e:
                    print(f'Unable to add photometry data for {new_entry.obj_id} to db. Error: {e}')
                    session.rollback()  # Roll back the session to clear the failed transaction
                    continue

            response_data = multiple_source_data_schema.dump(entry_list)
        finally:
            session.close()

    return jsonify(response_data)

def mjd_to_days_ago(mjd):
    current_time = Time(datetime.utcnow())
    mjd_time = Time(mjd, format='mjd')
    days_ago = (current_time - mjd_time).value
    return days_ago


@vol_app.route('/', methods=['GET'])
@login_required
def create_main():
    # Retrieve the most recent 10 entries
    recent_data = SourceData.query.order_by(SourceData.id.desc()).limit(10).all()
    recent_data_ser = multiple_source_data_schema.dump(recent_data)
    recent_data_df = pd.DataFrame(recent_data_ser)

    # Generate plots for each source and store the plot filenames
    plot_files = {}
    for source in recent_data:
        plot_file = plot_photometry(source.obj_id)
        if plot_file:
            plot_files[source.obj_id] = os.path.basename(plot_file)  # Just the filename

    print("Data passed to template:", recent_data_df)
    return render_template('index.html', source_data=recent_data_df.to_dict(orient='records'), plot_files=plot_files)
    
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def plot_photometry(source_id):
    photometry_data = fetch_photometry_data_for_source(source_id)
    if not photometry_data:
        print(f'No photometry data found for source {source_id}.')
        return None

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

    plot_filename = f'static/photometry_{source_id}.png'
    plt.savefig(os.path.join(basedir, plot_filename))
    plt.close()

    return plot_filename

@vol_app.route('/classify/<source_id>', methods=['GET'])
@login_required
def classify(source_id):
    source = SourceData.query.filter_by(obj_id=source_id).first()
    if not source:
        flash('Source not found', 'danger')
        return redirect(url_for('create_main'))
    
    plot_file = plot_photometry(source.obj_id)
    plot_files = {source.obj_id: os.path.basename(plot_file)} if plot_file else {}
    
    return render_template('classify.html', source=source, plot_files=plot_files)




@vol_app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)


@vol_app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            return redirect(url_for('create_main'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html', form=form)

@vol_app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))