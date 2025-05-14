# importing important libraries
import psycopg2
import psycopg2.extras
from flask import Flask, render_template, request, session, redirect, url_for, flash, g
from flask_socketio import SocketIO
from datetime import datetime
import configparser

# setting up the flask application
app = Flask(__name__)
app.config["SECRET_KEY"]='lahoua_key'
socketio = SocketIO(app)


# PostgreSQL database connection
db_params = {
    'host': 'localhost',
    'database': 'BDIA',
    'user': 'postgres',
    'password': 'admin',  # Change this
    'port': '5432'
}

# Create a connection function
def get_db_connection():
    conn = psycopg2.connect(**db_params)
    return conn

# time function
def format_datetime(value, format='%Y-%m-%d %H:%M'):
    return value.strftime(format)
app.jinja_env.filters['strftime']=format_datetime


# home app route
@app.route("/")
def home():
    return render_template("login.html")

# login logic
@app.route("/login", methods=["POST"])
def login():
    if request.method=="POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        cursor.execute(
            "SELECT * FROM users WHERE username = %s AND password = %s",
            (username, password)
        )
        user = cursor.fetchone()

        if user and user['is_approved']:
            session["user"]={
                "username": user['username'],
                "fullname": user['fullname'],
                "pseudo": user['pseudo'],
            }
            cursor.close()
            conn.close()
            flash("login successful")
            return redirect(url_for("room"))
        elif user and not user['is_approved']:
            cursor.close()
            conn.close()
            flash("account is waiting approval.")
            return redirect(url_for("home"))
        else:
            cursor.close()
            conn.close()
            flash("Invalide login credentials")
            return redirect(url_for("home"))

# logout logic
@app.route("/logout", methods=["POST"])
def logout():
    if 'user' in session:
        session.pop('user', None)
        flash("Vous avez été déconnecté avec succès.")
    else:
        flash("Vous n'êtes pas connecté.")
    return redirect(url_for("home"))

# signup logic
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        fullname = request.form["fullname"]
        pseudo = request.form["pseudo"]
        username = request.form["username"]
        password = request.form["password"]
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO users (fullname, pseudo, username, password, is_approved) VALUES (%s, %s, %s, %s, FALSE)",
            (fullname, pseudo, username, password),
        )
        conn.commit()
        cursor.close()
        conn.close()
        
        flash("Sign up successful.")
        return redirect(url_for("home"))
    return render_template("signup.html")

#chat room logic
@app.route("/room", methods=['GET', 'POST'])
def room():
    if 'user' not in session:
        flash('Vous devez être connecté pour accéder à cette page.')
        return redirect(url_for('home'))
    user_pseudo = session['user']['pseudo']
    #Get the list of connected users (not implemented)
    users =[session['user']]
    # Check if the request is a POST (message submission)
    if request.method == 'POST':
        # Get the message from the form
        message_text = request.form.get('message_text')
        # Get the current timestamp and insert message
        timestamp = datetime.now()
        insert_message(user_pseudo, message_text, timestamp)
        # Redirect to the /room route to perform the GET request and avoid duplication on refresh
        return redirect(url_for('room', new_messages=True))
    # Retrieve messages from the database
    messages = retrieve_messages()
    return render_template("room.html", user_pseudo=user_pseudo, messages=messages, users=users)

def retrieve_messages():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    # Retrieve the last N number messages from the Messages table
    cursor.execute("SELECT sender_pseudo, message_text, timestamp FROM Messages ORDER BY timestamp DESC LIMIT 50")
    messages = cursor.fetchall()
    cursor.close()
    conn.close()
    return messages

def insert_message(sender_pseudo, message_text, timestamp):
    conn = get_db_connection()
    cursor = conn.cursor()
    # Insert the message into the Messages table
    cursor.execute("INSERT INTO Messages (sender_pseudo, message_text, timestamp) VALUES (%s, %s, %s)",
                   (sender_pseudo, message_text, timestamp))
    conn.commit()
    cursor.close()
    conn.close()

# contact us redirection
@app.route("/contact")
def contact():
    return render_template("contact.html")

# contact us logic
@app.route("/sendcontact", methods=["GET", "POST"])
def sendcontact():
    if request.method == "POST":
        firstname = request.form["firstname"]
        lastname = request.form["lastname"]
        email = request.form["email"]
        mobile = request.form["mobile"]
        support_message = request.form["support_message"]
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO support (firstname, lastname, email, mobile, support_message) VALUES (%s, %s, %s, %s, %s)",
            (firstname, lastname, email, mobile, support_message),
        )
        conn.commit()
        cursor.close()
        conn.close()
        
        flash("message sent successfully.")
        return redirect(url_for("contact"))
    return render_template("contact.html")

# admin login redirection
@app.route("/adminlogin")
def admin_login():
    return render_template("adminlogin.html")

# admin login logic
@app.route("/adminlogin", methods=["GET", "POST"])
def adminlogin():
    if request.method == "POST":
        adminusername = request.form["admin_username"]
        adminpassword = request.form["admin_password"]
        
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        cursor.execute(
            "SELECT * FROM admins WHERE admin_username = %s AND admin_password = %s",
            (adminusername, adminpassword),
        )
        admin = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if admin:
            flash("Login successful")
            return redirect(url_for("admin_page"))
        else:
            flash("Invalid login credentials")
            return redirect(url_for("admin_login"))

# admin approval page logic
@app.route("/admin_page", methods=["GET", "POST"])
def admin_page():
    if request.method == "POST":
        selected_users = request.form.getlist('selected_users[]')
        
        if not selected_users:
            flash("No users selected for processing")
        else:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            approved_count = 0
            refused_count = 0
            
            try:
                for user_id in selected_users:
                    action = request.form.get(f"action_{user_id}")
                    
                    if action == "approve":
                        cursor.execute("UPDATE users SET is_approved = TRUE WHERE id = %s", (user_id,))
                        approved_count += 1
                    elif action == "refuse":
                        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
                        refused_count += 1
                
                conn.commit()
                
                if approved_count > 0:
                    flash(f"{approved_count} user(s) approved successfully")
                if refused_count > 0:
                    flash(f"{refused_count} user(s) refused and deleted successfully")
                    
            except Exception as e:
                flash(f"Error processing users: {str(e)}")
            finally:
                cursor.close()
                conn.close()
    
    # Fetch unapproved users
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        cursor.execute("SELECT * FROM users WHERE is_approved = FALSE")
        unapproved_users = cursor.fetchall()
    except Exception as e:
        flash(f"Error fetching unapproved users: {str(e)}")
        unapproved_users = []
    finally:
        cursor.close()
        conn.close()
        
    return render_template("admin.html", unapproved_users=unapproved_users)

# support login redirection
@app.route("/supportlogin")
def support_login():
    return render_template("supportlogin.html")

# support login logic
@app.route("/supportlogin", methods=["GET", "POST"])
def supportlogin():
    if request.method == "POST":
        supportusername = request.form["support_username"]
        supportpassword = request.form["support_password"]
        
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        cursor.execute(
            "SELECT * FROM supportadmin WHERE support_username = %s AND support_password = %s",
            (supportusername, supportpassword),
        )
        support = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if support:
            flash("Login successful")
            return redirect(url_for("support"))
        else:
            flash("Invalid login credentials")
            return redirect(url_for("support_login"))

# support messages handling logic
@app.route("/support", methods=["GET", "POST"])
def support():
    if request.method == "POST":
        selected_messages = request.form.getlist("selected_messages[]")
        
        if not selected_messages:
            flash("No messages selected for deletion")
        else:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            deleted_count = 0
            
            try:
                for message_id in selected_messages:
                    cursor.execute("DELETE FROM support WHERE id = %s", (message_id,))
                    deleted_count += 1
                
                conn.commit()
                flash(f"{deleted_count} message(s) deleted successfully")
                    
            except Exception as e:
                flash(f"Error deleting messages: {str(e)}")
            finally:
                cursor.close()
                conn.close()
    
    # Fetch unanswered messages
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        cursor.execute("SELECT * FROM support")
        unanswered_messages = cursor.fetchall()
    except Exception as e:
        flash(f"Error fetching unanswered messages: {str(e)}")
        unanswered_messages = []
    finally:
        cursor.close()
        conn.close()
        
    return render_template("support.html", unanswered_messages=unanswered_messages)

# reading the server configuration from the configuration file

config = configparser.ConfigParser()
config.read('config.ini')
host = config.get('Server', 'Host')
port = config.getint('Server', 'Port')

if __name__ == "__main__":
    socketio.run(app, host=host, port=port, debug=True)
