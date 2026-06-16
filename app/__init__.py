from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename  # For secure file uploads
import os  # For file path operations
import uuid  # For generating unique filenames
from deepface import DeepFace  # For mood detection
import cv2  # For image capture and processing
import numpy as np  # For image handling

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///../users.db'  # Database in the instance folder
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = '91dfa00052db1d185e99a5102397598c' 

# Configure upload folder for profile pictures
PROFILE_UPLOAD_FOLDER = os.path.join('app', 'static', 'uploads')  # Folder for profile pictures
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['PROFILE_UPLOAD_FOLDER'] = PROFILE_UPLOAD_FOLDER

# Configure upload folder for mood images
MOOD_UPLOAD_FOLDER = os.path.join('app', 'static', 'mood_images')  # New folder for mood images
app.config['MOOD_UPLOAD_FOLDER'] = MOOD_UPLOAD_FOLDER

# Ensure the upload folders exist
os.makedirs(PROFILE_UPLOAD_FOLDER, exist_ok=True)
os.makedirs(MOOD_UPLOAD_FOLDER, exist_ok=True)

db = SQLAlchemy(app)

# User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)
    name = db.Column(db.String(80), nullable=True)  # New column
    profile_picture = db.Column(db.String(120), nullable=True)  # New column

# Create the database and tables
with app.app_context():
    db.create_all()
    print("Database and tables created successfully!")

# Helper function to check allowed file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def home():
    user = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
    return render_template('index.html', user=user)

# New route for handling the "Get Started" button
@app.route('/get_started')
def get_started():
    if 'user_id' in session:
        # User is signed in, redirect to capture_mood.html
        return redirect(url_for('capture_mood'))
    else:
        # User is not signed in, redirect to signin page
        flash('Please sign in to get started.', 'error')
        return redirect(url_for('signin'))

@app.route('/capture_mood')
def capture_mood():
    user = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
    return render_template('capture_mood.html', user=user)

@app.route('/about')
def about():
    user = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
    return render_template('about.html', user=user)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # Check if the user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already exists. Please sign in.', 'error')
            return redirect(url_for('signin'))

        # Create a new user
        new_user = User(email=email, password=password)
        db.session.add(new_user)
        db.session.commit()

        flash('Signup successful! Please sign in.', 'success')
        return redirect(url_for('signin'))

    return render_template('signup.html')

@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # Check if the user exists
        user = User.query.filter_by(email=email).first()
        if user and user.password == password:
            session['user_id'] = user.id  # Start a session
            session['user_email'] = user.email
            flash('Signin successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid email or password.', 'error')
            return render_template('signin.html', error=True)  # Show error message

    return render_template('signin.html')

@app.route('/signout')
def signout():
    session.clear()  # End the session
    flash('You have been signed out.', 'success')
    return redirect(url_for('home'))

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        flash('Please sign in to access your profile.', 'error')
        return redirect(url_for('signin'))

    user = User.query.get(session['user_id'])

    if request.method == 'POST':
        name = request.form['name']
        profile_picture = request.files['profile_picture']

        # Update user details
        user.name = name

        # Handle profile picture upload
        if profile_picture and allowed_file(profile_picture.filename):
            # Generate a unique filename
            unique_filename = str(uuid.uuid4()) + '_' + secure_filename(profile_picture.filename)
            filepath = os.path.join(app.config['PROFILE_UPLOAD_FOLDER'], unique_filename)
            profile_picture.save(filepath)
            user.profile_picture = url_for('static', filename=f'uploads/{unique_filename}')

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))

    return render_template('profile.html', user=user)

# New route to save the photo
@app.route('/save_photo', methods=['POST'])
def save_photo():
    # Check if a file was uploaded
    if 'file' not in request.files:
        print("No file uploaded")  # Debugging
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files['file']

    # If no file is selected
    if file.filename == '':
        print("No file selected")  # Debugging
        return jsonify({"error": "No file selected"}), 400

    # If the file is valid
    if file and allowed_file(file.filename):
        # Generate a unique filename
        unique_filename = str(uuid.uuid4()) + '.jpg'
        file_path = os.path.join(app.config['MOOD_UPLOAD_FOLDER'], unique_filename)

        try:
            # Read the image file
            image = cv2.imdecode(np.frombuffer(file.read(), np.uint8), cv2.IMREAD_COLOR)

            # Flip the image horizontally (mirror effect)
            flipped_image = cv2.flip(image, 1)

            # Save the flipped image to the mood images folder
            cv2.imwrite(file_path, flipped_image)

            print(f"File saved successfully: {file_path}")  # Debugging

            # Return the image URL
            return jsonify({
                "message": "Photo saved successfully",
                "image_url": unique_filename
            })
        except Exception as e:
            print(f"Error saving file: {e}")  # Debugging
            return jsonify({"error": str(e)}), 500
    else:
        print("Invalid file type")  # Debugging
        return jsonify({"error": "Invalid file type"}), 400

# New route to detect mood using the saved photo
@app.route('/detect_mood', methods=['GET'])
def detect_mood():
    # Check if the user is logged in
    if 'user_id' not in session:
        flash('Please sign in to detect mood.', 'error')
        return redirect(url_for('signin'))

    user = User.query.get(session['user_id'])

    # Get the image filename from the query parameters
    image_filename = request.args.get('image')
    if not image_filename:
        return jsonify({"error": "No image specified"}), 400

    # Store the image filename in the session for later use
    session['last_image_filename'] = image_filename

    # Construct the full file path
    file_path = os.path.join(app.config['MOOD_UPLOAD_FOLDER'], image_filename)

    # Analyze the image for mood
    try:
        result = DeepFace.analyze(file_path, actions=['emotion'])
        dominant_emotion = result[0]['dominant_emotion']
        emotion_scores = result[0]['emotion']

        # Store the mood result in the session
        session['mood'] = dominant_emotion

        # Render the result page with the user object
        return render_template('result.html', 
                              user=user,
                              dominant_emotion=dominant_emotion,
                              emotion_scores=emotion_scores,
                              image_url=url_for('static', filename=f'mood_images/{image_filename}'))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# New route to get the detected mood
@app.route('/get_mood', methods=['GET'])
def get_mood():
    if 'mood' not in session:
        return jsonify({"error": "No mood detected yet"}), 400

    return jsonify({
        "dominant_emotion": session['mood']
    })

# New route for music recommendations
@app.route('/music_recommendations')
def music_recommendations():
    # Check if the user is logged in
    if 'user_id' not in session:
        flash('Please sign in to get music recommendations.', 'error')
        return redirect(url_for('signin'))

    user = User.query.get(session['user_id'])
    mood = request.args.get('mood', 'neutral')  # Default to 'neutral' if mood is not provided

    # Get the image filename from the query parameters or session
    image_filename = request.args.get('image')  # Pass this from the result page
    if not image_filename:
        # If image_filename is not provided, try to get it from the session
        image_filename = session.get('last_image_filename')

    if not image_filename:
        flash('No image found. Please capture a photo first.', 'error')
        return redirect(url_for('capture_mood'))

    # Construct the image URL
    image_url = url_for('static', filename=f'mood_images/{image_filename}')

    # Dictionary of songs categorized by mood (updated with 5 songs per mood)
    MOOD_SONGS = {
        "happy": [
            {"title": "Happy", "artist": "Pharrell Williams", "link": "https://open.spotify.com/track/60nZcImufyMA1MKQY3dcCH"},
            {"title": "Can't Stop the Feeling!", "artist": "Justin Timberlake", "link": "https://open.spotify.com/track/1WkMMavIMc4JZ8cfMmxHkI"},
            {"title": "Uptown Funk", "artist": "Mark Ronson ft. Bruno Mars", "link": "https://open.spotify.com/track/4rmPQGwcLQjCoFq5NrTA0D"},
            {"title": "Shut Up and Dance", "artist": "WALK THE MOON", "link": "https://open.spotify.com/track/4kbj5MwxO1bq9wjT5g9HaA"},
            {"title": "Don't Stop Me Now", "artist": "Queen", "link": "https://open.spotify.com/track/7hQJA50XrCWABAu5v6QZ4i"},
        ],
        "sad": [
            {"title": "Someone Like You", "artist": "Adele", "link": "https://open.spotify.com/track/1zwMYTA5nlNjZxYrvBB2pV"},
            {"title": "Fix You", "artist": "Coldplay", "link": "https://open.spotify.com/track/7LVHVU3tWfcxj5aiPFEW4Q"},
            {"title": "Say Something", "artist": "A Great Big World & Christina Aguilera", "link": "https://open.spotify.com/track/6Vc5wAMmXdKIAM7WUoEb7N"},
            {"title": "The Night We Met", "artist": "Lord Huron", "link": "https://open.spotify.com/track/0QZ5yyl6B6utIWkxeBDxQN"},
            {"title": "Skinny Love", "artist": "Bon Iver", "link": "https://open.spotify.com/track/3B3eOgLJSqPEA0RfboIQVM"},
        ],
        "angry": [
            {"title": "Break Stuff", "artist": "Limp Bizkit", "link": "https://open.spotify.com/track/2YC6ET3q1F29B0V7UcPV70"},
            {"title": "Bodies", "artist": "Drowning Pool", "link": "https://open.spotify.com/track/2OlnpAmV3i6Nl0bl7gVUfd"},
            {"title": "Killing in the Name", "artist": "Rage Against the Machine", "link": "https://open.spotify.com/track/59WN2psjkt1tyaxjspN8fp"},
            {"title": "Given Up", "artist": "Linkin Park", "link": "https://open.spotify.com/track/1kz6BZgA0A1QbT0x0gZqB5"},
            {"title": "Chop Suey!", "artist": "System of a Down", "link": "https://open.spotify.com/track/2Dl7l6Q6a1ZqL7Z2d6q7zM"},
        ],
        "neutral": [
            {"title": "Shape of You", "artist": "Ed Sheeran", "link": "https://open.spotify.com/track/7qiZfU4dY1lWllzX7mPBI3"},
            {"title": "Blinding Lights", "artist": "The Weeknd", "link": "https://open.spotify.com/track/0VjIjW4GlUZAMYd2vXMi3b"},
            {"title": "Levitating", "artist": "Dua Lipa", "link": "https://open.spotify.com/track/39LLxExYz6ewLAcYrzQQyP"},
            {"title": "Watermelon Sugar", "artist": "Harry Styles", "link": "https://open.spotify.com/track/6UelLqGlWMcVH1E5c4H7lY"},
            {"title": "Peaches", "artist": "Justin Bieber ft. Daniel Caesar, Giveon", "link": "https://open.spotify.com/track/4iJyoBOLtHqaGxP12qzhQI"},
        ],
    }

    songs = MOOD_SONGS.get(mood, [])
    return render_template('music_recommendations.html', user=user, mood=mood, songs=songs, image_url=image_url)

if __name__ == '__main__':
    app.run(debug=True)