import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import tensorflow as tf
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image
import numpy as np
import pickle
from database import init_db, get_db_connection
from datetime import datetime
import uuid

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create upload folder if not exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('instance', exist_ok=True)

# Initialize database
init_db()

# Load model and class names
try:
    model = load_model('poultry_disease_classifier.h5')
    with open('class_names.pkl', 'rb') as f:
        CLASS_NAMES = pickle.load(f)
    MODEL_LOADED = True
except:
    MODEL_LOADED = False
    CLASS_NAMES = []

# Disease remedies database
REMEDIES = {
    'New Castle Diseas': {
        'name': 'Newcastle Disease',
        'symptoms': ['Respiratory distress', 'Greenish diarrhea', 'Nervous disorders', 'Drop in egg production'],
        'prevention': [
            'Vaccinate birds regularly',
            'Maintain strict biosecurity measures',
            'Isolate new birds for 2-3 weeks',
            'Keep poultry house clean and disinfected'
        ],
        'treatment': [
            'No specific treatment - focus on prevention',
            'Supportive care with vitamins and electrolytes',
            'Antibiotics to prevent secondary infections',
            'Proper nutrition and hydration'
        ]
    },
    'Coccidiosis': {
        'name': 'Coccidiosis',
        'symptoms': ['Swelling of head', 'Purple discoloration', 'Respiratory issues', 'Sudden death'],
        'prevention': [
            'Strict biosecurity protocols',
            'Prevent contact with wild birds',
            'Regular cleaning and disinfection',
            'Proper waste management'
        ],
        'treatment': [
            'Immediate reporting to veterinary authorities',
            'Quarantine affected birds',
            'Supportive care with vitamins',
            'Antiviral medications as prescribed'
        ]
    },
    'salmonella': {
        'name': 'Infectious Bronchitis',
        'symptoms': ['Coughing', 'Sneezing', 'Nasal discharge', 'Reduced egg quality'],
        'prevention': [
            'Vaccination program',
            'Good ventilation in poultry houses',
            'Avoid overcrowding',
            'Regular sanitization'
        ],
        'treatment': [
            'Antibiotics for secondary infections',
            'Vitamin supplements',
            'Proper ventilation',
            'Adequate warmth and hydration'
        ]
    },
    'Healthy': {
        'name': 'Healthy Bird',
        'symptoms': ['Normal behavior', 'Good appetite', 'Active movement', 'Bright eyes'],
        'prevention': [
            'Regular health checks',
            'Balanced nutrition',
            'Clean water supply',
            'Proper housing conditions'
        ],
        'treatment': [
            'Continue good management practices',
            'Regular vaccination schedule',
            'Monitor for any changes',
            'Maintain optimal environment'
        ]
    }
}

def predict_disease(image_path):
    """Predict disease from image"""
    if not MODEL_LOADED:
        return None
    
    try:
        img = image.load_img(image_path, target_size=(150, 150))
        img_array = image.img_to_array(img)
        img_array = img_array / 255.0
        img_array = np.expand_dims(img_array, axis=0)
        
        predictions = model.predict(img_array)
        predicted_class_idx = np.argmax(predictions[0])
        predicted_class = CLASS_NAMES[predicted_class_idx]
        confidence = float(predictions[0][predicted_class_idx])
        
        # Debug logging
        print(f"Predicted class: {predicted_class}")
        print(f"All class names: {CLASS_NAMES}")
        print(f"Confidence: {confidence}")
        
        return {
            'class': predicted_class,
            'confidence': confidence,
            'all_predictions': predictions[0].tolist()
        }
    except Exception as e:
        print(f"Prediction error: {e}")
        return None

def save_detection_history(user_id, image_path, prediction):
    """Save detection to history"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO detection_history (user_id, image_path, predicted_class, confidence)
        VALUES (?, ?, ?, ?)
    ''', (user_id, image_path, prediction['class'], prediction['confidence']))
    
    conn.commit()
    conn.close()

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute(
            'SELECT * FROM users WHERE username = ?', (username,)
        ).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                (username, email, generate_password_hash(password))
            )
            conn.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except  sqlite3.IntegrityError:
            flash('Username or email already exists', 'error')
        finally:
            conn.close()
    
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    history = conn.execute('''
        SELECT * FROM detection_history 
        WHERE user_id = ? 
        ORDER BY timestamp DESC 
        LIMIT 10
    ''', (session['user_id'],)).fetchall()
    conn.close()
    
    # Calculate statistics
    total_detections = len(history)
    high_confidence = sum(1 for detection in history if detection['confidence'] >= 0.8)
    
    # Count healthy birds - check for various possible healthy class names
    healthy_count = 0
    disease_count = 0
    
    for detection in history:
        predicted_class = detection['predicted_class'].lower()
        # Check for various possible healthy class names
        if any(healthy_indicator in predicted_class for healthy_indicator in ['Healthy', 'health', 'normal', 'good']):
            healthy_count += 1
        else:
            disease_count += 1
    
    stats = {
        'total_detections': total_detections,
        'high_confidence': high_confidence,
        'healthy_count': healthy_count,
        'disease_count': disease_count
    }
    
    return render_template('dashboard.html', history=history, stats=stats)

@app.route('/detect', methods=['GET', 'POST'])
def detect():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)
        
        if file:
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4().hex}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(filepath)
            
            prediction = predict_disease(filepath)
            if prediction:
                save_detection_history(session['user_id'], unique_filename, prediction)
                return render_template('results.html', 
                                    prediction=prediction,
                                    image_url=url_for('static', filename=f'uploads/{unique_filename}'),
                                    class_names=CLASS_NAMES,
                                    remedies=REMEDIES.get(prediction['class'], REMEDIES['Healthy']))
            else:
                flash('Error processing image', 'error')
    
    return render_template('detect.html')

@app.route('/remedies')
def remedies():
    return render_template('remedies.html', remedies=REMEDIES)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))
# Add this route to app.py for debugging
@app.route('/debug_history')
def debug_history():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    history = conn.execute('''
        SELECT * FROM detection_history 
        WHERE user_id = ? 
        ORDER BY timestamp DESC
    ''', (session['user_id'],)).fetchall()
    conn.close()
    
    # Convert to list for easier debugging
    history_list = []
    for row in history:
        history_list.append({
            'id': row['id'],
            'predicted_class': row['predicted_class'],
            'confidence': row['confidence'],
            'timestamp': row['timestamp']
        })
    
    return jsonify(history_list)
if __name__ == '__main__':
    app.run(debug=True)