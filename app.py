from flask import Flask, render_template, request, redirect, url_for, session
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from flask import Flask, render_template, redirect, url_for, request
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField
from wtforms.validators import DataRequired, Email
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask import flash



app = Flask(__name__)
app.secret_key = 'your_secret_key'

# SECRET key for CSRF protection in Flask-WTF forms
app.config['SECRET_KEY'] = 'supersecretkey123'  # you can change it

# Using SQLite as a database (users.db will be created)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize the database
db = SQLAlchemy(app)

# Load dataset once at startup
data = pd.read_csv('cleaned_testdata.csv')
data.columns = data.columns.str.strip()

# Flask-WTF form for registration
from wtforms import ValidationError

def validate_email(self, field):
        if '@gmail.com' not in field.data.lower():
            raise ValidationError('Please enter a valid Gmail address.')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])  # Keep Email() for basic format check
    password = PasswordField('Password', validators=[DataRequired()])

# Database model for the User
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    # Create tables manually at startup
with app.app_context():
    db.create_all()
    print("✅ Tables created!")

# Required columns
required_columns = ['Crop', 'Yield', 'Area', 'Annual_Rainfall', 'Fertilizer', 'Pesticide', 'Crop_Year', 'Season', 'State']
for col in required_columns:
    if col not in data.columns:
        raise ValueError(f"Missing column in dataset: {col}")

data = data.dropna(subset=required_columns)

# Label encode for ML
label_encoders = {}
for column in data.select_dtypes(include=['object']).columns:
    le = LabelEncoder()
    data[column] = le.fit_transform(data[column])
    label_encoders[column] = le

# ML training
yield_features = ['Area', 'Annual_Rainfall', 'Fertilizer', 'Pesticide']
yield_target = 'Yield'
crop_features = ['Area', 'Annual_Rainfall', 'Fertilizer', 'Pesticide']
crop_target = 'Crop'

X_yield = data[yield_features]
y_yield = data[yield_target]
X_crop = data[crop_features]
y_crop = data[crop_target]

yield_model = RandomForestRegressor()
yield_model.fit(X_yield, y_yield)

crop_model = RandomForestClassifier()
crop_model.fit(X_crop, y_crop)

@app.route('/')
def about_us():
    return render_template('aboutus.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Check if user exists
        user = User.query.filter_by(username=username).first()

        # ✅ Verify hashed password
        if user and check_password_hash(user.password, password):
            session['user'] = user.username
            return redirect(url_for('about_us'))
        else:
            return render_template('login.html', error='Invalid credentials')

    return render_template('login.html')



# This route should not be indented inside the login route
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()

    if form.validate_on_submit():
        username = form.username.data
        email = form.email.data
        password = form.password.data

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email address already registered. Please use a different one.', 'danger')
            return redirect(url_for('register'))

        new_user = User(username=username, email=email, password=generate_password_hash(password))
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('login'))
    
    # ✅ Keep this indented at same level as `if form.validate_on_submit():`
    print("📭 Form GET or not validated")
    return render_template('register.html', form=form)
@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('about_us'))

@app.route('/dashboard')
def dashboard():
    return redirect(url_for('dataset'))

# Updated `/dataset` route
@app.route('/dataset')
def dataset():
    df = pd.read_csv('cleaned_testdata.csv')
    df.columns = df.columns.str.strip()

    # Get full unique lists BEFORE filtering
    crop_list = sorted(df['Crop'].dropna().unique())
    state_list = sorted(df['State'].dropna().unique())
    season_list = sorted(df['Season'].dropna().unique())

    # Get filters from query params
    crop = request.args.get('crop', '')
    state = request.args.get('state', '')
    season = request.args.get('season', '')

    # Apply filters
    if crop:
        df = df[df['Crop'] == crop]
    if state:
        df = df[df['State'] == state]
    if season:
        df = df[df['Season'] == season]

    return render_template('dataset.html',
                           data=df.to_dict(orient='records'),
                           columns=df.columns,
                           crop_list=crop_list,
                           state_list=state_list,
                           season_list=season_list,
                           selected_crop=crop,
                           selected_state=state,
                           selected_season=season)


@app.route('/yield_prediction', methods=['GET', 'POST'])
def yield_prediction():
    if 'user' not in session:
        return redirect(url_for('login'))

    df = pd.read_csv('cleaned_testdata.csv')
    crops = sorted(df['Crop'].dropna().unique())
    seasons = sorted(df['Season'].dropna().unique())
    states = sorted(df['State'].dropna().unique())

    if request.method == 'POST':
        try:
            inputs = [
                float(request.form['area']),
                float(request.form['rainfall']),
                float(request.form['fertilizer']),
                float(request.form['pesticide'])
            ]
            prediction = yield_model.predict([inputs])[0]
            return render_template('yield_prediction.html', prediction=round(prediction, 2), crop=request.form['crop'], season=request.form['season'], state=request.form['state'], crops=crops, seasons=seasons, states=states)
        except Exception as e:
            return render_template('yield_prediction.html', error=str(e), crops=crops, seasons=seasons, states=states)
    return render_template('yield_prediction.html', crops=crops, seasons=seasons, states=states)

@app.route('/generate_pdf', methods=['POST'])
def generate_pdf():
     return "PDF generation not implemented yet"

@app.route('/crop_suggestion', methods=['GET', 'POST'])
def crop_suggestion():
    if 'user' not in session:
        return redirect(url_for('login'))

    df = pd.read_csv('cleaned_testdata.csv')
    seasons = sorted(df['Season'].dropna().unique())
    states = sorted(df['State'].dropna().unique())

    if request.method == 'POST':
        selected_season = request.form['season']
        selected_state = request.form['state']

        filtered = df[(df['Season'] == selected_season) & (df['State'] == selected_state)]

        if filtered.empty:
            return render_template('crop_suggestion.html', seasons=seasons, states=states, selected_season=selected_season, selected_state=selected_state, no_data=True)

        suggested = filtered['Crop'].value_counts().head(5).index.tolist()
        return render_template('crop_suggestion.html', seasons=seasons, states=states, selected_season=selected_season, selected_state=selected_state, suggested=suggested)

    return render_template('crop_suggestion.html', seasons=seasons, states=states)

@app.route('/powerbi')
def powerbi():
    return render_template('powerbi.html')

import os

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))  # default to 5000 locally
    app.run(host='0.0.0.0', port=port)

