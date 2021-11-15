import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, date
import json

from helpers import login_required


# Configure application
app = Flask(__name__)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///timetracker.db")

@app.route("/", methods=["GET"])
@login_required
def dashboard():
    """ Shows overview of sessions """

    today = date.today()
    total_time = 0
    tag_time = {}
    tags = []

    rows = db.execute("SELECT tag, session FROM records WHERE date = :date AND user_id = :user_id",
                        date=today, user_id=session["user_id"])
    rows_tags = db.execute("SELECT name FROM tags WHERE user_id = :user_id",
                        user_id=session["user_id"])

    for x in rows:
        total_time += int(x["session"])

    i = 0
    for y in rows_tags:
        time = 0
        for x in rows:
            if y["name"] == x["tag"]:
                time += int(x["session"])
        if time > 0:
            tag_time[y["name"]] = time
            tags.append(y["name"])
            i += 1

    tagtime_json = json.dumps(tag_time)
    tags_json = json.dumps(tags)

    return render_template("dashboard.html", total_time=total_time, tags=tags, tags_json=tags_json, tagtime_json=tagtime_json)

@app.route("/add", methods=["POST"])
@login_required
def add():
    """ Allows user to add a new tag """

    # Set intial errors to None
    error = None

    # Get tags
    tags = db.execute("SELECT name FROM tags WHERE user_id = :user_id",
                        user_id=session["user_id"])

    # Check if name of tag entered
    tag = request.form.get("tag")
    if tag == None:
        error = "Please enter a name for the tag"
        return render_template("tags.html", error=error, tags=tags)

    # Check if tag already exists
    rows = db.execute("SELECT * FROM tags WHERE name = :name AND user_id = :user_id",
                        name=tag, user_id=session["user_id"])
    if len(rows) > 0:
        tags = db.execute("SELECT * FROM tags WHERE user_id = :user_id",
                            user_id=session["user_id"])
        error = "Tag already exists"
        return render_template("tags.html", error=error, tags=tags)

    # Add new tag to database
    db.execute("INSERT INTO tags(name, user_id) VALUES(:name, :user_id)",
                name=tag, user_id=session["user_id"])

    flash("Tag added")
    return redirect(url_for("tags"))

@app.route("/change", methods=["GET", "POST"])
@login_required
def change():
    """ Allows user to change their password """

    # Set initial errors to None
    error = None


    # Reach via POST (user trying to change password)
    if request.method == "POST":
        password = request.form.get("password_old")
        password_new = request.form.get("password_new")
        password_new2 = request.form.get("password_new_confirm")

        # Check if current password is correct
        rows = db.execute("SELECT * from users WHERE id = :id",
                            id=session["user_id"])
        if not check_password_hash(rows[0]["hash"], password):
            error = "Incorrect password"
            return render_template("change.html", error=error)

        # Check if new password is the same as current password
        if password == password_new:
            error = "New password cannot be the same as current password"
            return render_template("change.html", error=error)

        # Check if new passwords match
        if password_new != password_new2:
            error = "Failed to confirm new password"
            return render_template("change.html", error=error)

        # Update hash in user database
        db.execute("UPDATE users SET hash = :hash WHERE id = :id",
                    hash=generate_password_hash(password_new), id=session["user_id"])

        # Redirect back to home page
        flash("Password changed")
        return redirect(url_for("dashboard"))

    # Reach via GET (via redirect or link)
    else:
        return render_template("change.html")

@app.route("/delete", methods=["GET", "POST"])
@login_required
def delete():
    """ Allows user to delete account """

    # Set initial errors to none
    error = None

    # If reach via POST (user trying to delete account)
    if request.method == "POST":

        password = request.form.get("password")

        # Check if password is correct
        rows = db.execute("SELECT * FROM users WHERE id = :id",
                id = session["user_id"])
        if not check_password_hash(rows[0]["hash"], password):
            error = "Incorrect password"
            return render_template("delete.html", error=error)

        # Drop user from database
        db.execute("DELETE FROM users WHERE id = :id",
                    id=session["user_id"])

        # Delete tags related to account
        db.execute("DELETE FROM tags WHERE user_id = :user_id",
                    user_id=session["user_id"])

        # Delete records related to account
        db.execute("DELETE FROM records WHERE user_id = :user_id",
                    user_id=session["user_id"])
        flash("Account successfully deleted")

        # Redirect back to login page
        return redirect(url_for("login"))

    # If reach via GET (via redirect or link)
    else:
        rows = db.execute("SELECT * FROM users WHERE id = :id",
                            id=session["user_id"])
        return render_template("delete.html", username=rows[0]["username"])

@app.route("/deletetag", methods=["POST"])
@login_required
## Should the records for the tag be deleted too??
def deletetag():
    """ Allows user to delete a tag """

    # Set initial errors to None
    error = None

    # Get tags
    tags = db.execute("SELECT name FROM tags WHERE user_id = :user_id",
                        user_id=session["user_id"])

    tag = request.form.get("tag")

    # Check if tag exists
    rows = db.execute("SELECT * FROM tags WHERE name = :name AND user_id = :user_id",
                        name=tag, user_id=session["user_id"])
    if len(rows) != 1:
        error = "Something went wrong"
        return render_template("tags.html", error=error, tags=tags)

    # Remove tag from database
    db.execute("DELETE FROM tags WHERE name = :name AND user_id = :user_id",
                name=tag, user_id=session["user_id"])

    # Remove records under tag
    db.execute("DELETE FROM records WHERE tag = :tag AND user_id = :user_id",
                tag=tag, user_id=session["user_id"])

    flash("Tag successfully deleted")
    return redirect(url_for("tags"))

@app.route("/edit", methods=["POST"])
@login_required
def edit():
    """ Allows user to edit tags """

    # Set initial errors to none
    error = None

    # Get all tags
    tags = db.execute("SELECT name FROM tags WHERE user_id = :user_id",
                        user_id=session["user_id"])

    old_name = request.form.get("old_name")
    new_name = request.form.get("edit_name")

    # Check if tag exists
    rows = db.execute("SELECT * FROM tags WHERE name = :name AND user_id = :user_id",
                        name=old_name, user_id=session["user_id"])

    if len(rows) != 1:
        error = "Something went wrong, this tag doesn't exist"
        return render_template("tags.html", error=error, tags=tags)

    # Check if new name is the same as old name
    if old_name.strip() == new_name.strip():
        error = "New name must be different from the old name"
        return render_template("tags.html", error=error)

    # Check if new name is name of another existing tag
    rows = db.execute("SELECT * FROM tags WHERE name = :name AND user_id = :user_id",
                        name=new_name, user_id=session["user_id"])

    if len(rows) > 0:
        error = "Tag with name '%s' already exists" % new_name
        return render_template("tags.html", error=error, tags=tags)

    # Update database with new name
    db.execute("UPDATE tags SET name = :name WHERE name = :old_name",
                name=new_name, old_name=old_name)

    db.execute("UPDATE records SET tag = :name WHERE tag = :old_name",
                name=new_name, old_name=old_name)

    flash("Tag name updated")
    return redirect(url_for("tags"))

@app.route("/login", methods=["GET", "POST"])
def login():
    """ Logs in user """

    # Set initial error message to be empty
    error = None

    # Forget any user_id
    try:
        if session["user_id"]:
            session.clear()
    except:
        pass

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Create error if username or password is incorrect
        if len(rows) != 1:
            error = "Username does not exist"

        elif not check_password_hash(rows[0]["hash"], request.form.get("password")):
            error = "Password is incorrect"

        # If successful
        else:
            # Remember which user has logged in
            session["user_id"] = rows[0]["id"]

            flash("Logged in successfully")
            return redirect(url_for("dashboard"))

        # Redirect user back to login page with error
        return render_template("login.html", error=error)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout", methods=["GET"])
@login_required
def logout():
    """ Logs user out and clears session """
    session.clear()
    flash("Logged out successfully")
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    """ Allows new user to register account """

    # Set initial errors to none
    error = None

    # User reaches page via POST (registering new account)
    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")
        password_confirm = request.form.get("confirm-password")

        # Check if username already exists
        rows = db.execute("SELECT * from users WHERE username = :username",
                        username=username)
        if len(rows) != 0:
            error = "Sorry, this username already exists"
            return render_template("register.html", error=error)

        # Check if passwords match
        if password != password_confirm:
            error = "Please make sure your passwords match"
            return render_template("register.html", error=error)

        # Add user to database
        db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)",
                    username=username, hash=generate_password_hash(password))

        flash("Successfully registered! Log in to proceed.")

        # Redirect back to login page with success message
        return redirect(url_for("login"))

    # User reaches page via GET (reach page through redirect or link)
    else:
        return render_template("register.html")

@app.route("/start", methods=["GET", "POST"])
@login_required
def start():
    """ The first page when log in """
    """ User can choose the length of session and add a tag to the session """

    # Set initial error to none
    error = None

    # Fetch user's tags
    tags = db.execute("SELECT * FROM tags WHERE user_id = :user_id",
                            user_id=session["user_id"])

    # Reach via POST (user trying to start timer)
    if request.method == "POST":
        time = request.form.get("time")
        tag = request.form.get("tag")

        # Check if fields are valid
        rows = db.execute("SELECT * FROM tags WHERE name = :name AND user_id = :user_id",
                            name=tag, user_id=session["user_id"])
        if len(rows) < 1:
            error = "Please select a valid tag"
            return render_template("start.html", error=error, tags=tags)

        # Returns new page with a timer, passing through variable for time and tag
        return render_template("timer.html", time=time, tag=tag)

    # Reach via GET (reach page through link or redirect)
    else:
        return render_template("start.html", tags=tags)

@app.route("/tags", methods=["GET"])
@login_required
def tags():
    """ Allows user to manage tags """
    rows = db.execute("SELECT name FROM tags WHERE user_id = :user_id",
                        user_id=session["user_id"])

    return render_template("tags.html", tags=rows)

@app.route("/update_record")
def update_record():
    """ Updates records when session is completed """

    # Get data parsed as arguments
    time = request.args.get('session', type=int)
    tag = request.args.get('tag', type=str)
    today = date.today()

    # Insert new record into database
    db.execute("INSERT INTO records (date, session, tag, user_id) VALUES (:today, :session, :tag, :user_id)",
                today=today, session=time, tag=tag, user_id=session["user_id"])
