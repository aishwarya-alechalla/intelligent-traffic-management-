from flask import Flask, render_template, redirect, flash,url_for, request, jsonify
import os,re
import utils
from datetime import datetime
import time
import json
from distraction import detect_mobile_phone
from helmet import detect_plates
from ocr import extract_text_from_images
from traffic_signal import detect_signal_violation
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_migrate import Migrate
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
import cv2
import easyocr
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SECRET_KEY'] = 'your_secret_key'

db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
bcrypt = Bcrypt(app)

ROOT_DIR = "./"

@login_manager.user_loader
def load_user(email):
    user = User.query.filter_by(email=email).first()  # Check if admin
    if user:
        return user  # Return admin if found
    
    return User1.query.filter_by(email=email).first()  # Otherwise, return regular user


### Admin Model ###
class User(db.Model, UserMixin):  
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=True) 

    def get_id(self):
        return self.email  # Return email instead of ID 

    def set_password(self, password):
        self.password = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password, password)

### User Model ###
class User1(db.Model, UserMixin):  
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    vehicle_number = db.Column(db.String(20), unique=True, nullable=False)
    phone_number = db.Column(db.String(15), unique=True, nullable=False)
    is_admin = db.Column(db.Boolean, default=False)  

    def get_id(self):
        return self.email  # Return email instead of ID

    def set_password(self, password):
        self.password = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password, password)
    





class Penalty(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user1.id'), nullable=False)  # Link to User1 table
    vehicle_number = db.Column(db.String(20), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)  # Timestamp
    paid = db.Column(db.Boolean, default=False)  # New column to track payment

    user = db.relationship('User1', backref=db.backref('penalties', lazy=True))  # Relationship with User1

















@app.route('/')
def home():
    return render_template('index.html')

@app.route('/admin/login', methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if current_user.is_authenticated:
            logout_user()

        email = request.form["email"]
        password = request.form["password"]
        admin = User.query.filter_by(email=email, is_admin=True).first()

        if not admin:
            flash("Admin not found! Contact support.", "error")
            return redirect(url_for("admin_login"))

        if not admin.check_password(password):
            flash("Wrong password! Try again.", "error")
            return redirect(url_for("admin_login"))

        login_user(admin)
        flash("Admin login successful!", "success")
        return redirect(url_for("admin_dashboard"))  # Ensure admins go to their dashboard

    return render_template("admin_login.html")

### Admin Register ###
@app.route('/admin/register', methods=["GET", "POST"])
def admin_register():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]

        existing_admin = User.query.filter_by(email=email).first()
        if existing_admin:
            flash("Admin with this email already exists!", "danger")
            return redirect(url_for("admin_register"))

        admin = User(username=username, email=email, is_admin=True)
        admin.set_password(password)

        db.session.add(admin)
        db.session.commit()

        flash("Admin registration successful!", "success")
        return redirect(url_for("admin_login"))

    return render_template("admin_register.html")

@app.route('/user/login', methods=["GET", "POST"])
def user_login():
    if request.method == "POST":
        if current_user.is_authenticated:
            logout_user()

        email = request.form["email"]
        password = request.form["password"]
        user = User1.query.filter_by(email=email).first()  # Fetch from User1

        if not user:
            flash("User does not exist! Please register.", "error")
            return redirect(url_for("user_login"))

        if not user.check_password(password):
            flash("Incorrect password! Try again.", "error")
            return redirect(url_for("user_login"))

        login_user(user)  # Logs in user using email
        flash("Login successful!", "success")
        return redirect(url_for("user_penalties"))

    return render_template("user_login.html")


### User Register ###
@app.route('/user/register', methods=["GET", "POST"])
def user_register():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        phone_number = request.form["phone_number"]
        vehicle_number = request.form["vehicle_number"]
        password = request.form["password"]

        existing_user = User1.query.filter(
            (User1.email == email) | (User1.phone_number == phone_number) | (User1.vehicle_number == vehicle_number)
        ).first()

        if existing_user:
            flash("User with this email, phone number, or vehicle number already exists!", "danger")
            return redirect(url_for("user_register"))

        user = User1(username=username, email=email, phone_number=phone_number, vehicle_number=vehicle_number, is_admin=False)
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        flash("Registration successful! Please log in.", "success")
        return redirect(url_for("user_login"))

    return render_template("user_register.html")

### Logout ###
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Logged out successfully.", "success")
    return redirect(url_for("home"))







@app.route('/user/penalties')
@login_required
def user_penalties():
    if current_user.is_admin:
        flash("Admins cannot access user penalties.", "warning")
        return redirect(url_for("admin_dashboard"))

    penalties = Penalty.query.filter_by(user_id=current_user.id, paid=False).all()  # Fetch only unpaid penalties
    return render_template("user_penalty.html", penalties=penalties)







@app.route('/user/pay_penalty/<int:penalty_id>', methods=['POST'])
@login_required
def pay_penalty(penalty_id):
    penalty = Penalty.query.filter_by(id=penalty_id, user_id=current_user.id, paid=False).first()

    if not penalty:
        flash("Penalty not found or already paid!", "danger")
        return redirect(url_for("user_penalties"))

    # Simulate payment processing (you can integrate with a payment gateway)
    penalty.paid = True
    db.session.commit()

    flash("Penalty paid successfully!", "success")
    return redirect(url_for("user_penalties"))












### Admin Dashboard ###
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        return redirect(url_for("check_penalties"))
    return render_template("admin_dashboard.html")

### Helmet Violation Detection ###
@app.route('/helmet_compliance', methods=['POST', 'GET'])
def helmet_video():
    print("Helmet Compliance Route Accessed")  # Debugging Print

    if request.method == 'POST':
        uploaded_file = request.files['video_file']
        if uploaded_file:
            file_name = uploaded_file.filename
            file_path = os.path.join(ROOT_DIR, file_name)
            uploaded_file.save(file_path)

            print("Uploaded File Name:", file_name)  # Debugging Print

            selected_location = request.form.get('location')
            print("Selected Location:", selected_location)  # Debugging Print

            ret = detect_plates(file_path)  # Call the detection function

            print("Detection Result:", ret)  # Debugging Print

            if ret:
                result_set = utils.perform_ocr()
                if result_set:
                    utils.make_doc(result_set)

            return jsonify(ret)

    locations = ['Miyapur', 'Kukatpally', 'L B Nagar', 'Ameerpet', 'Chanda Nagar']
    return render_template('Helmet.html', location=locations)


@app.route('/admin/insights')
@login_required
def admin_insights():
    if not current_user.is_admin:
        return redirect(url_for("check_penalties"))

    # Example Statistics (Replace with real data from database)
    insights = {
        "total_helmet_violations": 125,
        "total_signal_violations": 78,
        "most_violated_location": "Miyapur",
        "recent_violations": [
            {"type": "Helmet", "location": "Kukatpally", "time": "12:30 PM"},
            {"type": "Signal", "location": "Ameerpet", "time": "1:15 PM"},
        ]
    }

    return render_template("admin_insights.html", insights=insights)


### Traffic Violation Detection ###
@app.route('/admin/signal', methods=['POST', 'GET'])
@login_required
def signal_video():
    if not current_user.is_admin:
        return redirect(url_for("check_penalties"))

    if request.method == 'POST':
        uploaded_file = request.files['video_file']

        if uploaded_file:
            file_name = uploaded_file.filename
            file_path = os.path.join(ROOT_DIR, file_name)
            uploaded_file.save(file_path)
            print("Uploaded File Name:", file_name)

            selected_location = request.form.get('locations')
            print("Selected Location:", selected_location)

            ret = detect_signal_violation(file_path)
            print(ret)
            return jsonify(ret)

    locations = ['Miyapur', 'Kukatpally', 'L B Nagar', 'Ameerpet', 'Chanda Nagar']
    return render_template('Signal.html', location=locations)




reader = easyocr.Reader(['en'])  # Initialize EasyOCR




@app.route('/admin/penalties')
@login_required
def admin_penalties():
    if not current_user.is_admin:
        flash("Unauthorized access!", "danger")
        return redirect(url_for("admin_dashboard"))

    penalties = Penalty.query.all()  # Fetch all penalties

    return render_template("admin_penalties.html", penalties=penalties)




@app.route('/admin/ocr', methods=['GET', 'POST'])
@login_required
def admin_ocr():
    if not current_user.is_admin:
        flash("Unauthorized access!", "danger")
        return redirect(url_for("admin_dashboard"))

    extracted_texts = []
    penalties_added = []

    if request.method == 'POST':
        uploaded_files = request.files.getlist("image_files")  # Get multiple images

        if not uploaded_files or uploaded_files[0].filename == '':
            flash("Please upload at least one image.", "warning")
            return redirect(url_for("admin_ocr"))

        for file in uploaded_files:
            filename = secure_filename(file.filename)
            file_path = os.path.join("uploads", filename)  # Save in 'uploads' folder
            file.save(file_path)

            # Perform OCR on the image
            ocr_result = reader.readtext(file_path)
            raw_text = "".join([text[1] for text in ocr_result])  # No spaces
            raw_text = re.sub(r'[^a-zA-Z0-9]', '', raw_text)

            # Replace 'I' -> '1' and 'O' -> '0' at indexes 2,3,6,7,8,9
            text_list = list(raw_text)
            for i in [2, 3, 6, 7, 8, 9]:
                if i < len(text_list):  # Ensure index exists
                    if text_list[i] == 'I':
                        text_list[i] = '1'
                    elif text_list[i] == 'O':
                        text_list[i] = '0'

            formatted_text = "".join(text_list)
            extracted_texts.append(formatted_text)
            matched_user = User1.query.filter_by(vehicle_number=formatted_text).first()
            if matched_user:
                # Add a penalty for this user
                new_penalty = Penalty(user_id=matched_user.id, vehicle_number=formatted_text,)
                db.session.add(new_penalty)
                db.session.commit()
                penalties_added.append((matched_user.username, formatted_text))

        if penalties_added:
            for user, vehicle in penalties_added:
                flash(f"Penalty successfully recorded for {user} (Vehicle: {vehicle})", "success")
        else:
            flash("No matching vehicle found. No penalties recorded.", "warning")

    return render_template("admin_ocr.html", extracted_texts=extracted_texts)
### User - Check Penalties ###
@app.route('/user/penalties')
@login_required
def check_penalties():
    if current_user.is_admin:
        flash("Admins cannot access user penalties.", "warning")
        return redirect(url_for("admin_dashboard"))
    
    # Fetch penalties for the logged-in user
    penalties = []  # Replace with actual database fetch logic
    return render_template("penalties.html", penalties=penalties)

if __name__ == '__main__':
    app.run(debug=True)
