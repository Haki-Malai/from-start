import sys
import os
import json
import random
import string
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(25), unique=True)
    password = db.Column(db.String(512))
    email = db.Column(db.String(50), unique=True)
    confirmedEmail = db.Column(db.Boolean, default=False)
    created = db.Column(db.Date)
    level = db.Column(db.Integer, default=1)
    lastActive = db.Column(db.DateTime)
    invitationCode = db.Column(db.String(10), unique=True)
    invitationCommision = db.Column(db.Float(10), default=0)
    invitedFrom = db.Column(db.String(10), default='NOBODY')
    taskProfit = db.Column(db.Float(10), default=0)
    picUrl = db.Column(db.String(10), default='none')
    balance = db.Column(db.Float, default=0)

    def __init__(self, username, email, password, invitationCode, invitedFrom='NOBODY'):
        self.username = username
        self.email = email
        self.password = generate_password_hash(password)
        self.created = created=datetime.now()
        self.lastActive = created=datetime.now()
        self.invitationCode = invitationCode
        self.invitedFrom = invitedFrom

    def __repr__(self):
        return '<User %r>' % self.username
    
    def validate_password(self, password):
        return check_password_hash(self.password, password)

    def get_paid_for_job(self, amount):
        self.balance += amount
        self.taskProfit += amount
        # Give 2% to the invitor
        invitor_amount = amount*0.02
        user = User.query(invitationCode=self.invitedFrom).first()
        user.get_paid_for_job(invitor_amount)
        db.session.commit()

    def get_json(self):
        return json.dumps({
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'confirmedEmail': self.confirmedEmail,
            'created': self.created,
            'level': self.level,
            'lastActive': self.lastActive,
            'invitationCode': self.invitationCode,
            'invitedFrom': self.invitationCode,
            'invitationCommision': self.invitationCommision,
            'picUrl': self.picUrl,
            'balance': self.balance,
            'taskProfit': self.taskProfit,
            'tasks': get_user_tasks(self.username)
        }, indent=4, default=str, sort_keys=True)

class Task(db.Model):
    __tablename__ = "task"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    social = db.Column(db.Integer)
    status = db.Column(db.Integer)
    created = db.Column(db.DateTime)
    duration = db.Column(db.Integer)
    requirements = db.Column(db.Integer)
    link = db.Column(db.String(64))
    submited = db.Column(db.DateTime, default=None)

    def __init__(self, user_id, social, link, hours=0):
        self.user_id = user_id
        self.social = social
        self.status = 0
        self.created = datetime.now()
        self.duration = hours
        self.requirements = 1
        self.link = link
        self.submited = None

    def __repr__(self):
        return '<Task %r>' % self.id

    def get_json(self):
        return json.dumps({
            'id': self.id,
            'user_id': self.user_id,
            'social': self.social,
            'status': self.status,
            'created': self.created,
            'duration': self.duration,
            'requirements': self.requirements,
            'link': self.link,
            'submited': self.submited,
        }, indent=4, default=str, sort_keys=True)

def change_user_password(username, password):
    user = User.query.filter_by(username=username).first()
    user.password = generate_password_hash(password)
    db.session.commit()

def get_user_data(username):
    return User.query.filter_by(username=username).first().get_json()

def get_user_data_from_id(id):
    return User.query.filter_by(id=id).first().get_json()

def get_user_id(username):
    return User.query.filter_by(username=username).first().id

def credentials_valid(username, password):
    user = User.query.filter_by(username=username).first()
    if user:
        return user.validate_password(password)
    return False

def username_exists(username):
    return User.query.filter_by(username=username).first()

def email_exists(email):
    return User.query.filter_by(email=email).first()

def add_user(username, password, email, invitation_code='00000000'):
    user = User(username=username, password=password, email=email, invitationCode=create_random_code(), invitedFrom=invitation_code)

    db.session.add(user)
    db.session.commit()

def add_task(username, social, hours=3):
    # Check if user is privileged to another task
    user = User.query.filter_by(username=username).first()
    today_done = len(get_user_tasks(username))
    if (user.level == 1 and today_done == 3) or \
           (user.level == 2 and today_done == 5) or \
           (user.level == 3 and today_done == 8) or \
           (user.level == 4 and today_done == 15) or \
           (user.level == 5 and today_done == 22) or \
           (user.level == 6 and today_done == 60):
        return 0
    else:
        task = Task(user_id=user.id, social=social, hours=hours, link='https://www.facebook.com')
        db.session.add(task)
        db.session.commit()
        return 1
    
def get_user_tasks(username):
    user = User.query.filter_by(username=username).first()
    tasks = Task.query.filter_by(user_id=user.id).all()
    daily_tasks = []

    # Query tasks where the created datetime is bigger than yesterday 
    yesterday = datetime.now() - timedelta(days = 1)
    last_week = datetime.now() - timedelta(days = 7)
    last_3_hours = datetime.now() - timedelta(seconds=15)#hours = 3) # TODO custom timeout threshold
    random_past_time = datetime.now() - timedelta(seconds=15)#hours = random.randint(0, 9)) 
    final_tasks = []

    # Delete very old tasks
    for task in Task.query.filter(Task.user_id == user.id, Task.created < last_week).all():
        task.delete()
        db.session.commit()

    # Update to timeout timeouted tasks
    for task in Task.query.filter(Task.user_id == user.id, Task.created < last_3_hours, Task.status == 0).all():
        update_task(task.id, 3)

    # Update to finished and pay user
    for task in Task.query.filter(Task.user_id == user.id, Task.status == 1, Task.submited < random_past_time).all():
        update_task(task.id, 2)
        user_to_pay = User.query.filter(User.id == task.user_id).first()
        if user_to_pay.level == 1:
            amount = 0.5
        elif user_to_pay.level == 2:
            amount = 0.8
        elif user_to_pay.level == 3:
            amount = 1.5
        elif user_to_pay.level == 4:
            amount = 1.7
        elif user_to_pay.level == 5:
            amount = 2
        elif user_to_pay.level == 6:
            amount = 2.3
        user_to_pay.taskProfit = user_to_pay.taskProfit + amount
        user_to_pay.balance = user_to_pay.balance + amount
        db.session.commit()

    # Return tasks from last 24h
    for task in Task.query.filter(Task.user_id == user.id, Task.created > yesterday).all():
        final_tasks.append(json.dumps(task.get_json()))
    return final_tasks

def upgrade_user(username, level):
    user = User.query.filter_by(username=username).first()
    print(level)
    if level <= 6 and level > 1 and level > user.level:
        user.level = level
        db.session.commit()
        return 1
    return 0

def init_db():
    db.create_all()
    user = User('useruser', 'user@user.com', '12345678', '1234567890')
    db.session.add(user)
    db.session.commit()

def delete_task(id):
    Task.query.filter_by(id=id).delete()
    db.session.commit()

def update_task(id, status):
    Task.query.filter_by(id=id).first().status = status
    Task.query.filter_by(id=id).first().submited = datetime.now()
    db.session.commit()

def create_random_code():
    chars=string.ascii_uppercase + string.digits
    size = 10
    code = ''.join(random.choice(chars) for _ in range(size))
    while User.query.filter_by(invitationCode=code).first():
        code = ''.join(random.choice(chars) for _ in range(size))
    return code

#def approve and pay task TODO TODO TODO

def timeout_task(id):
    task = Task.query.filter_by(id=id)
    if task.status == 0:
        task.delete()
        db.session.commit()