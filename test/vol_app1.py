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

FRITZ_API_TOKEN = ''
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

    def __init__(self, obj_id, ra, dec, redshift, transient, varstar, is_roid) -> None:
        super(SourceData, self).__init__()
        self.obj_id = obj_id
        self.ra = ra
        self.dec = dec
        self.redshift = redshift
        self.transient = transient
        self.varstar = varstar
        self.is_roid = is_roid

    def __repr__(self) -> str:
        return '<SourceData %r>' % self.obj_id

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class SourceDataSchema(ma.Schema):
    class Meta:
        fields = ('id', 'obj_id', 'ra', 'dec', 'redshift', 'transient', 'varstar', 'is_roid')

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

@vol_app.route('/fetch_sources', methods=['GET'])
def add_source_data():
    sources = fetch_source_data()

    entry_list = []

    for source in sources:
        if isinstance(source, dict):
            new_entry = SourceData(
                obj_id=source.get('id'),
                ra=source.get('ra'),
                dec=source.get('dec'),
                redshift=source.get('redshift'),
                transient=source.get('transient', True),  # Default to False if not present
                varstar=source.get('varstar', False),  # Default to False if not present
                is_roid=source.get('is_roid', False)  # Default to False if not present
            )
            entry_list.append(new_entry)
            print(f'Created entry: {new_entry}')  # Debug: Print created entry
        else:
            print("Unexpected data format:", source)

    with vol_app.app_context():
        Session = sessionmaker(bind=db.engine)
        session = Session()

        for entry in entry_list:
            try:
                session.add(entry)
                session.commit()
                print(f'Added {entry.obj_id} to db.')
            except Exception as e:
                print(f'Unable to add {entry.obj_id} to db. Error: {e}')
                continue
        session.close()

    return multiple_source_data_schema.jsonify(entry_list)

@vol_app.route('/', methods=['GET'])
@login_required
def create_main():
    # Retrieve the most recent 10 entries
    recent_data = SourceData.query.order_by(SourceData.id.desc()).limit(10).all()
    recent_data_ser = multiple_source_data_schema.dump(recent_data)
    recent_data_df = pd.DataFrame(recent_data_ser)

    print("Data passed to template:", recent_data_df)
    return render_template('index.html', source_data=recent_data_df.to_dict(orient='records'))

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