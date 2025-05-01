import os
from cs50 import SQL
from datetime import date, datetime, timedelta
from flask import Flask, flash, redirect, render_template, request, session, jsonify
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from helper import apology
from functools import wraps
from flask_mail import Mail, Message
from apscheduler.schedulers.background import BackgroundScheduler
from flask_ngrok import run_with_ngrok

app = Flask(__name__)
run_with_ngrok(app)  # Enable ngrok for Flask app

# Configure email settings
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 465
app.config["MAIL_USERNAME"] = "manujchaudhari456@gmail.com"  # Replace with your email
app.config["MAIL_PASSWORD"] = "fgjb vwgt ibfy iryv"  # Use your App Password
app.config["MAIL_USE_TLS"] = False
app.config["MAIL_USE_SSL"] = True
app.config["MAIL_DEBUG"] = True  # Enable mail debug mode

# Configure the current URL of your app to send emails and trigger responses
app.config["BASE_URL"] = (
    "https://308c-2409-40c2-2f-3c68-82b3-824f-a6c6-3db9.ngrok-free.app/"  # Replace with your actual base URL
)

mail = Mail(app)

# Initialize APScheduler
scheduler = BackgroundScheduler()
scheduler.start()

# Configure session
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Database connection
db = SQL("sqlite:///classroom.db")

# Drop and recreate the timetable table with the correct schema
db.execute("DROP TABLE IF EXISTS timetable")
db.execute(
    """
    CREATE TABLE timetable (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_name TEXT NOT NULL,
        day_of_week TEXT NOT NULL,
        time_slot TEXT NOT NULL,
        lecture_time TIME NOT NULL,
        lecture_date DATE NOT NULL,
        teacher_name TEXT NOT NULL,
        teacher_email TEXT NOT NULL,
        lecture_status TEXT DEFAULT 'Pending',
        cancellation_reason TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
)

# Create email logs table if it doesn't exist
db.execute("""
    CREATE TABLE IF NOT EXISTS email_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lecture_id INTEGER,
        status TEXT,
        message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function


# Function to send email with better error handling
def send_email(teacher_email, teacher_name, subject_name, lecture_time, lecture_id):
    try:
        print(f"Attempting to send email to {teacher_email} for lecture {lecture_id}")
        
        with app.app_context():
            # Create a more detailed message
            confirm_link = f"{app.config['BASE_URL']}/confirm_lecture/{lecture_id}"
            cancel_link = f"{app.config['BASE_URL']}/cancel_lecture/{lecture_id}"
            
            msg = Message(
                f"Lecture Confirmation Required: {subject_name} at {lecture_time}",
                sender=app.config["MAIL_USERNAME"],
                recipients=[teacher_email]
            )
            
            msg.body = f"""
            Dear {teacher_name},

            This is a reminder about your upcoming lecture:
            
            Subject: {subject_name}
            Time: {lecture_time}
            
            Please confirm your availability:
            
            To confirm: {confirm_link}
            To cancel: {cancel_link}
            
            Best regards,
            Classroom Monitoring System
            """
            
            print("Sending email with the following details:")
            print(f"From: {msg.sender}")
            print(f"To: {msg.recipients}")
            print(f"Subject: {msg.subject}")
            
            mail.send(msg)
            print(f"Email sent successfully to {teacher_email}")
            
            # Log the successful email
            db.execute(
                "INSERT INTO email_logs (lecture_id, status, message) VALUES (?, ?, ?)",
                lecture_id,
                "SUCCESS",
                f"Email sent to {teacher_email} at {datetime.now()}"
            )
            
    except Exception as e:
        error_msg = f"Failed to send email: {str(e)}"
        print(error_msg)
        # Log the failed email
        db.execute(
            "INSERT INTO email_logs (lecture_id, status, message) VALUES (?, ?, ?)",
            lecture_id,
            "FAILED",
            error_msg
        )
        raise Exception(error_msg)


# Function to send emails to all teachers at their respective times
def send_emails_for_day(selected_date):
    lectures = db.execute(
        "SELECT id, teacher_email, teacher_name, subject_name, lecture_time FROM timetable WHERE lecture_date = ?",
        selected_date,
    )

    for lecture in lectures:
        lecture_id = lecture["id"]
        teacher_email = lecture["teacher_email"]
        teacher_name = lecture["teacher_name"]
        subject_name = lecture["subject_name"]
        lecture_time = lecture["lecture_time"]

        # Convert lecture_time to datetime
        now = datetime.now()
        lecture_datetime = datetime.strptime(lecture_time, "%H:%M").replace(
            year=now.year, month=now.month, day=int(selected_date.split("-")[2])
        )

        # If the lecture time is in the past for today, schedule it for tomorrow
        if lecture_datetime < now:
            lecture_datetime += timedelta(days=1)

        # Schedule email sending at lecture time using a normal function instead of a lambda
        scheduler.add_job(
            func=send_email,  # Directly use send_email function
            args=(
                teacher_email,
                teacher_name,
                subject_name,
                lecture_time,
                lecture_id,
            ),  # Pass arguments
            trigger="date",
            run_date=lecture_datetime,
        )


@app.route("/")
def home():
    return render_template("layout.html", css_file="css/layoutStyles.css")


@app.route("/login", methods=["GET", "POST"])
def login():
    session.clear()

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username == "admin" and password == "admin":
            session["user_id"] = 1  # Set a fixed user ID for admin
            return redirect("/")
        else:
            return apology("invalid username and/or password", 403)

    else:
        return render_template("login.html", css_file="css/layoutStyles.css")


@app.route("/timetable")
@login_required
def timetable():
    try:
        # Get all lectures and organize them by day and slot
        lectures = db.execute(
            """
            SELECT * FROM timetable 
            ORDER BY lecture_date, day_of_week, time_slot
            """
        )
        print("Retrieved lectures:", lectures)
        
        timetable_data = {}
        for lecture in lectures:
            day = lecture['day_of_week']
            slot = lecture['time_slot']
            key = (day, slot)
            timetable_data[key] = lecture
            print(f"Added lecture to slot {day}-{slot}:", lecture)
        
        return render_template(
            "timetable.html",
            timetable=timetable_data,
            css_file="css/timetableStyles.css"
        )
    except Exception as e:
        print("Error in timetable route:", str(e))
        flash("Error loading timetable: " + str(e), "error")
        return render_template(
            "timetable.html",
            timetable={},
            css_file="css/timetableStyles.css"
        )


@app.route("/save_timetable", methods=["POST"])
@login_required
def save_timetable():
    try:
        # Get form data
        subject_name = request.form.get("subject_name")
        day_of_week = request.form.get("day_of_week")
        time_slot = request.form.get("time_slot")
        lecture_time = request.form.get("lecture_time")
        lecture_date = request.form.get("lecture_date")
        teacher_name = request.form.get("teacher_name")
        teacher_email = request.form.get("teacher_email")

        print("Received form data:", {
            "subject": subject_name,
            "day": day_of_week,
            "slot": time_slot,
            "time": lecture_time,
            "date": lecture_date,
            "teacher": teacher_name,
            "email": teacher_email
        })

        # Validate all required fields are present
        if not all([subject_name, day_of_week, time_slot, lecture_time, 
                   lecture_date, teacher_name, teacher_email]):
            raise ValueError("All fields are required")

        # Check if a lecture already exists in this slot
        existing = db.execute(
            """
            SELECT id FROM timetable 
            WHERE day_of_week = ? AND time_slot = ? AND lecture_date = ?
            """,
            day_of_week, time_slot, lecture_date
        )

        print("Existing lecture check:", existing)

        if existing:
            # Update existing lecture
            result = db.execute(
                """
                UPDATE timetable 
                SET subject_name = ?, 
                    teacher_name = ?, 
                    teacher_email = ?, 
                    lecture_time = ?,
                    lecture_status = 'Pending'
                WHERE day_of_week = ? AND time_slot = ? AND lecture_date = ?
                """, 
                subject_name, teacher_name, teacher_email, lecture_time,
                day_of_week, time_slot, lecture_date
            )
            lecture_id = existing[0]["id"]
            print("Updated lecture with ID:", lecture_id)
        else:
            # Insert new lecture
            lecture_id = db.execute(
                """
                INSERT INTO timetable (
                    subject_name, day_of_week, time_slot, lecture_time,
                    lecture_date, teacher_name, teacher_email
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                subject_name, day_of_week, time_slot, lecture_time,
                lecture_date, teacher_name, teacher_email
            )
            print("Inserted new lecture with ID:", lecture_id)

        # Schedule email for the lecture
        schedule_lecture_email(lecture_date, lecture_time, teacher_email,
                             teacher_name, subject_name, lecture_id)

        flash("Lecture saved successfully!")
        
    except ValueError as ve:
        print("Validation error:", str(ve))
        flash("Error: " + str(ve), "error")
        
    except Exception as e:
        print("Error saving lecture:", str(e))
        flash("Error saving lecture: " + str(e), "error")
    
    return redirect("/timetable")


def schedule_lecture_email(lecture_date, lecture_time, teacher_email, teacher_name, subject_name, lecture_id):
    """Schedule email for a lecture based on specific date and time"""
    try:
        # Get current date and time
        now = datetime.now()
        print(f"Current time: {now}")
        
        # Convert lecture_date string to datetime
        lecture_date = datetime.strptime(lecture_date, '%Y-%m-%d').date()
        lecture_time_obj = datetime.strptime(lecture_time, '%H:%M').time()
        
        # Combine date and time
        lecture_datetime = datetime.combine(lecture_date, lecture_time_obj)
        
        # If lecture is in the past, don't schedule
        if lecture_datetime < now:
            error_msg = f"Cannot schedule email for past date: {lecture_datetime}"
            print(error_msg)
            flash(error_msg, "warning")
            return
        
        print(f"Scheduling email for lecture {lecture_id} at {lecture_datetime}")
        
        # Schedule the email to be sent at the lecture time
        job = scheduler.add_job(
            func=send_email,
            args=(teacher_email, teacher_name, subject_name, lecture_time, lecture_id),
            trigger='date',
            run_date=lecture_datetime,
            id=f'lecture_{lecture_id}_{lecture_datetime.strftime("%Y%m%d%H%M")}',
            replace_existing=True
        )
        
        print(f"Scheduled job: {job.id} for {lecture_datetime}")
        print(f"Next run time: {job.next_run_time}")
        
        # Log the scheduled email
        db.execute(
            "INSERT INTO email_logs (lecture_id, status, message) VALUES (?, ?, ?)",
            lecture_id,
            "SCHEDULED",
            f"Email scheduled for {lecture_datetime}"
        )
        
    except Exception as e:
        error_msg = f"Error scheduling email: {str(e)}"
        print(error_msg)
        db.execute(
            "INSERT INTO email_logs (lecture_id, status, message) VALUES (?, ?, ?)",
            lecture_id,
            "SCHEDULE_FAILED",
            error_msg
        )
        flash(f"Warning: Could not schedule email notification: {str(e)}", "warning")


@app.route("/display_timetable")
@login_required
def display_timetable():
    # Get all lectures and organize them by day and slot
    lectures = db.execute("SELECT * FROM timetable")
    timetable_data = {}
    
    for lecture in lectures:
        day = lecture['day_of_week']
        slot = lecture['time_slot']
        timetable_data[(day, slot)] = lecture
    
    return render_template(
        "display_timetable.html",
        timetable=timetable_data,
        css_file="css/timetableStyles.css"
    )


@app.route("/clear_timetable", methods=["POST"])
@login_required
def clear_timetable():
    db.execute("DELETE FROM timetable")
    flash("Timetable cleared successfully!")
    return redirect("/timetable")


@app.route("/confirm_lecture/<int:lecture_id>")
def confirm_lecture(lecture_id):
    # Update the lecture status to 'Confirmed'
    db.execute(
        "UPDATE timetable SET lecture_status = 'Confirmed' WHERE id = ?", lecture_id
    )
    flash("Lecture confirmed successfully!")
    return render_template("status_confirmed.html", css_file="css/layoutStyles.css")


@app.route("/cancel_lecture/<int:lecture_id>", methods=["GET", "POST"])
def cancel_lecture(lecture_id):
    if request.method == "POST":
        if "reason_form" in request.form:
            # Handle the cancellation reason submission
            cancellation_reason = request.form.get("reason", "")

            # Update the lecture status to 'Canceled' and store the reason
            db.execute(
                "UPDATE timetable SET lecture_status = 'Canceled', cancellation_reason = ? WHERE id = ?",
                cancellation_reason,
                lecture_id,
            )
            flash("Lecture canceled successfully!")
            # After storing the reason, show the alternative lecture form
            return render_template(
                "status_canceled.html",
                css_file="css/layoutStyles.css",
                show_alt_form=True,
            )

        else:
            # Handle the alternative lecture form submission
            subject_name = request.form.get("subject_name")
            lecture_time = request.form.get("lecture_time")
            teacher_name = request.form.get("teacher_name")
            teacher_email = request.form.get("teacher_email")
            lecture_date = request.form.get("lecture_date") or date.today().strftime(
                "%Y-%m-%d"
            )

            # Insert the alternative lecture into the timetable
            db.execute(
                "INSERT INTO timetable (subject_name, lecture_time, teacher_name, teacher_email, lecture_date) VALUES (?, ?, ?, ?, ?)",
                subject_name,
                lecture_time,
                teacher_name,
                teacher_email,
                lecture_date,
            )

            # Send emails for the new lecture
            send_emails_for_day(lecture_date)

            flash("Alternative lecture added successfully!")
            return redirect("/timetable")

    else:
        # Show the initial cancellation reason form
        return render_template(
            "status_canceled.html", css_file="css/layoutStyles.css", show_alt_form=False
        )


@app.route("/get_latest_lecture_status")
def get_latest_lecture_status():
    current_date = date.today().strftime("%Y-%m-%d")
    latest_lecture = db.execute(
        "SELECT subject_name, lecture_time, teacher_name, lecture_status, cancellation_reason "
        "FROM timetable WHERE lecture_date = ? ORDER BY lecture_time DESC LIMIT 1",
        current_date,
    )

    if latest_lecture:
        lecture = latest_lecture[0]
        teacher = lecture["teacher_name"]
        subject = lecture["subject_name"]
        lecture_time = lecture["lecture_time"]
        status = lecture["lecture_status"]

        # Build the display message in the required format
        display_message = f"{teacher}: {subject}: {lecture_time}: {status}"

        # Append cancellation reason if lecture is canceled
        if status == "Canceled":
            reason = lecture.get("cancellation_reason") or "No specific reason provided"
            display_message += f": {reason}"

        return jsonify({"display_message": display_message})
    else:
        return jsonify({"display_message": "No lectures scheduled"})


@app.route("/api/timetable_status")
def api_timetable_status():
    current_date = date.today().strftime("%Y-%m-%d")
    status = db.execute(
        """
        SELECT 
            subject_name, 
            lecture_status,
            CASE 
                WHEN lecture_status = 'Canceled' THEN 
                    COALESCE(cancellation_reason, 'No specific reason provided')
                ELSE NULL 
            END as cancellation_reason 
        FROM timetable 
        WHERE lecture_date = ?
        """,
        current_date,
    )
    return jsonify(status)


@app.route("/email_logs")
@login_required
def view_email_logs():
    logs = db.execute("SELECT * FROM email_logs ORDER BY created_at DESC LIMIT 50")
    return render_template("email_logs.html", logs=logs)


@app.route("/reset_timetable", methods=["POST"])
@login_required
def reset_timetable():
    try:
        # Get all scheduled jobs
        jobs = scheduler.get_jobs()
        
        # Remove all scheduled email jobs
        for job in jobs:
            if job.id.startswith('lecture_'):
                scheduler.remove_job(job.id)
                print(f"Removed scheduled job: {job.id}")
        
        # Clear the timetable
        db.execute("DELETE FROM timetable")
        
        # Log the reset action
        db.execute(
            "INSERT INTO email_logs (status, message) VALUES (?, ?)",
            "RESET",
            f"Timetable reset by user at {datetime.now()}"
        )
        
        flash("Timetable has been completely reset!", "success")
        
    except Exception as e:
        print("Error resetting timetable:", str(e))
        flash("Error resetting timetable: " + str(e), "error")
    
    return redirect("/display_timetable")


if __name__ == "__main__":
    app.config["DEBUG"] = True  # Enable debug mode
    app.run()
