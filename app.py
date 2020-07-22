from flask import Flask
import os, logging, sys, datetime
from copy import deepcopy
from flask import Flask, flash, redirect, render_template, request, session as login_session, json
from flask_session import Session 
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from flask_sqlalchemy import SQLAlchemy

from helpers import apology, login_required

# Configure application
app = Flask(__name__)
app.config["SECRET_KEY"] = "\x87\xa5\xb1@\xe8\xb2r\x0b\xbb&\xf7\xe9\x84-\x17\xdc\xf8\xfc9l7\xbb\xe9q"

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

# Configure SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///timed.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
db = SQLAlchemy(app)



class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    hash = db.Column(db.Text, nullable=False)
    def __repr__(self):
        return "<User %r>" % self.username

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(80), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    interval = db.Column(db.Integer, nullable=False)
    def __repr__(self):
        return "<Task %r>" % self.description

class Record(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("task.id"))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    start = db.Column(db.DateTime, nullable=False)
    stop = db.Column(db.DateTime, nullable=False)
    

@app.route('/')
@login_required
def index():
    """ Show all record of user """
    # Get all record of this user
    # sort records by occurring time
    records_raw = Record.query.filter_by(user_id=login_session["user_id"]).\
              order_by(Record.start).all()
    # print(records_raw, file=sys.stderr)
    user_name = User.query.filter_by(id=login_session["user_id"]).first()
    user_name = user_name.username
    # print(user_name, file=sys.stderr)
    if not records_raw:
        # This user has no record
        return render_template("index.html" ,username=user_name)
    # create a new array
    records = []
    day = {}
    tasks = []
    for record in records_raw:
        
        # get date of a task
        date = datetime.datetime.combine(record.start.date(), datetime.time.min)
        # print("date of ", record.task_id, " is ", date, file=sys.stderr)
        date = date.timestamp() * 1000
        # print("After conversion, date of ", record.task_id, " is ", date, file=sys.stderr)


        if not day:
            # For the first record
            day["date"] = date

        elif not date == day["date"]:
            # save the loaded day
            day["tasks"] = tasks
            # print("append day ", day, file=sys.stderr)
            records.append(deepcopy(day))
            # print("after append, records is ", records, file=sys.stderr)
            # clear the lists for next-time use
            day.clear()
            tasks.clear()
            # start another day
            day["date"] = date

        # Process this record
        record = record.__dict__
        del record["_sa_instance_state"]
        # print("this record ", record, file=sys.stderr)
        name = Task.query.filter_by(id=record["task_id"]).first()
        # print(name, file=sys.stderr)
        try:
            record["name"] = name.description
        except:
            record["name"] = "Untitled Adventure"
        if not record["name"]:
            record["name"] = "Untitled Adventure"
        record["start"] = int(record["start"].timestamp()) * 1000
        record["stop"] = int(record["stop"].timestamp()) * 1000
        tasks.append(deepcopy(record))
        record.clear()
        # print("append tasks ", tasks, file=sys.stderr)
    
    # For the last record
    day["tasks"] = tasks
    # print("append day ", day, file=sys.stderr)
    records.append(deepcopy(day))
    print("records is ", records, file=sys.stderr)
    return render_template('index.html', records=records, username=user_name)

@app.route('/timer', methods=["GET", "POST"])
@login_required
def timer():
    """ Timer """
    if request.method == "POST":
        # access after finishing certain session
        record = json.loads(request.form.get("timerJSON"))
        if not record:
            return apology("Empty record returned", 403)
        # print("recieved timer", record, type(record), sep=" ", file=sys.stderr)
        for timer in record:
            # print(timer["startTime"], type(timer["startTime"]), timer["stopTime"], type(timer["stopTime"]), file=sys.stderr)
            # search matching task name in database, take the id
            # print("timer" , timerCount, "name is", timer.get("name"), sep=" ", file=sys.stderr)
            if timer.get("name"):
                task = Task.query.filter_by(user_id=login_session["user_id"] , description=timer.get("name")).first()
            else:
                task = Task.query.filter_by(user_id=login_session["user_id"] , description=None).first()
                if not task:
                    task = Task(description=None,  user_id=login_session["user_id"], interval=0)
                    db.session.add(task)
                    db.session.commit()
            # create new record of that id
            # print(task, task.description, file=sys.stderr)
            new_record = Record(task_id=task.id, user_id=login_session["user_id"], start=datetime.datetime.fromtimestamp(timer["startTime"] / 1e3), stop=datetime.datetime.fromtimestamp(timer["stopTime"] / 1e3))
            db.session.add(new_record)
        db.session.commit()            
        return redirect("/")
    else:
        # access from other page
        # print(request.args, file=sys.stderr)
        if not request.args:
            # print("no timer yet", file=sys.stderr)
            # get all saved tasks of this user from database
            tasks = Task.query.filter_by(user_id=login_session["user_id"]).all()
            tasksNew = []
            for task in tasks:
                if not task.description or not task.interval:
                    continue
                task = task.__dict__
                del task["_sa_instance_state"]
                tasksNew.append(task)
                # print(task, file=sys.stderr)
            # print("passing tasks", tasksNew, sep=" ", file=sys.stderr)


            user_name = User.query.filter_by(id=login_session["user_id"]).first()
            user_name = user_name.username
            return render_template('timer.html', tasks=tasksNew,username=user_name)
        elif request.args.get("task"):
            # access this route through task
            # print("access timer through", request.args.get("name"), fime=sys.stderr)
            # search matching task in database
            task = Task.query.filter_by(user_id=login_session["user_id"] , description=request.args.get("task")).first()
            if not task:
                # if not exist in database, create a new task 
                task = Task(description=request.args.get("task"), user_id=login_session["user_id"], interval=request.args.get("interval"))
                # print("created", task, file=sys.stderr)
                db.session.add(task)
                db.session.commit()

            # print(task, task.interval, task.description, file=sys.stderr)
            
            user_name = User.query.filter_by(id=login_session["user_id"]).first()
            user_name = user_name.username
            return render_template('timer.html', interval=task.interval, name=task.description,username=user_name)
            
        elif request.args.get("hour") or request.args.get("minute") or request.args.get("second"):
            # for anonymous timer
            # print("access anonymous timer and the time is ", request.args.get("hour") , request.args.get("minute") , request.args.get("second"), file=sys.stderr)
            interval = (int(request.args.get("hour")) * 3600 + int(request.args.get("minute")) * 60 + int(request.args.get("second"))) * 1000
            # print(interval, file=sys.stderr)


            
            user_name = User.query.filter_by(id=login_session["user_id"]).first()
            user_name = user_name.username
            return render_template('timer.html' , interval=interval,username=user_name)

@app.route("/stopwatch", methods=["GET", "POST"])
def stopwatch():
    """ Stopwatch """
    if request.method == "POST":
        # access after finishing certain session
        record = json.loads(request.form.get("SWJSON"))
        if not record:
            return apology("Empty record returned", 403)
        # print("recieved SW", record, type(record), sep=" ", file=sys.stderr)
        for SW in record:
            # print(SW["startTime"], type(SW["startTime"]), SW["stopTime"], type(SW["stopTime"]), file=sys.stderr)
            # search matching task name in database, take the id
            # print("SW" , SWCount, "name is", SW.get("name"), sep=" ", file=sys.stderr)
            if SW.get("name"):
                task = Task.query.filter_by(user_id=login_session["user_id"] , description=SW.get("name")).first()
            else:
                task = Task.query.filter_by(user_id=login_session["user_id"] , description=None).first()
                if not task:
                    task = Task(description=None,  user_id=login_session["user_id"], interval=0)
                    db.session.add(task)
                    db.session.commit()
            # create new record of that id
            # print(task, task.description, file=sys.stderr)
            new_record = Record(task_id=task.id, user_id=login_session["user_id"], start=datetime.datetime.fromtimestamp(SW["startTime"] / 1e3), stop=datetime.datetime.fromtimestamp(SW["stopTime"] / 1e3))
            db.session.add(new_record)
        db.session.commit()            
        return redirect("/")
    else:
        # access from other page
        # print(request.args, file=sys.stderr)
        if not request.args:
            # print("no SW yet", file=sys.stderr)
            # get all saved tasks of this user from database
            tasks = Task.query.filter_by(user_id=login_session["user_id"]).all()
            tasksNew = []
            for task in tasks:
                if not task.description:
                    continue
                task = task.__dict__
                del task["_sa_instance_state"]
                tasksNew.append(task)
                # print(task, file=sys.stderr)
            # print("passing tasks", tasksNew, sep=" ", file=sys.stderr)


            user_name = User.query.filter_by(id=login_session["user_id"]).first()
            user_name = user_name.username
            return render_template('stopwatch.html', tasks=tasksNew,username=user_name)
        elif request.args.get("task"):
            # access this route through task
            # print("access SW through", request.args.get("name"), fime=sys.stderr)
            # search matching task in database
            task = Task.query.filter_by(user_id=login_session["user_id"] , description=request.args.get("task")).first()
            if not task:
                # if not exist in database, create a new task 
                task = Task(description=request.args.get("task"), user_id=login_session["user_id"], interval=request.args.get("interval"))
                # print("created", task, file=sys.stderr)
                db.session.add(task)
                db.session.commit()

            print(task, task.description, file=sys.stderr)
            
            user_name = User.query.filter_by(id=login_session["user_id"]).first()
            user_name = user_name.username
            return render_template('stopwatch.html', SW=True, name=task.description,username=user_name)
        elif request.args.get("action"):
            user_name = User.query.filter_by(id=login_session["user_id"]).first()
            user_name = user_name.username
            return render_template("stopwatch.html", SW=True, username=user_name)
         

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    login_session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("Must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("Must provide password", 403)

        # Query database for username
        visitor = User.query.filter_by(username=request.form.get("username")).first_or_404()

        # print(visitor, visitor.id, visitor.hash, file=sys.stderr)

        # Ensure username exists and password is correct
        if not visitor or not check_password_hash(visitor.hash, request.form.get("password")):
            return apology("Invalid username and/or password", 403)

        # Add user to login_session
        login_session["user_id"] = visitor.id

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    login_session.clear()

    # Redirect user to login form
    return redirect("/")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)


        # Query database for existed username
        if User.query.filter_by(username=request.form.get("username")).first():
            # If username is already used
            return apology("user has registered", 403)
        else:
            registree = User(username=request.form.get("username"), hash=generate_password_hash(request.form.get("password")))
            db.session.add(registree)
            db.session.commit()
        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")



def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
