import database

import json
import sys
import os
import sqlite3
import string
import random
from datetime import datetime
from flask import Flask, session, request
from flask_jwt_extended import create_access_token, JWTManager
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.exceptions import HTTPException
from datetime import timedelta

SQLALCHEMY_DATABASE_URI = 'sqlite:///database.db'

app = Flask(__name__)
CORS(app)
app.config['JWT_SECRET_KEY'] = 'please-remember-to-change-me'
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_POOL_RECYCLE'] = 299
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
jwt = JWTManager(app)
database.db.init_app(app)
database.db.app = app

#=============================RESPONSES====================================
HOMEPAGE = json.dumps({'render': 'home'})
WELCOME = json.dumps({'render': 'welcome'})
LOGIN = json.dumps({'render': 'login'})
SIGNUP = json.dumps({'render': 'signup'})
SIGNUP_ERROR = json.dumps({'error': 'signup_error'})
INVALID_CREDENTIALS = json.dumps({'error': 'invalid_credentials'})
USERNAME_ERROR = json.dumps({'error': 'username_unavailable'})
EMAIL_ERROR = json.dumps({'error': 'email_unavailable'})
PASSWORD_ERROR = json.dumps({'error': 'password_error'})
EMPTY_ERROR = json.dumps({'error': 'empty_fields'})
SUCCESS = json.dumps({'success': True})
ERROR = json.dumps({'success': False})

#==============================ACCESS-CONNECTIONS======================
tokens = []
users = []
# TODO Token refresh timer

#==============================AUTHENTICATION=========================
@app.route('/', methods=['POST'])
def welcome():
    access_token = request.json['access_token']
    if access_token in tokens and access_token != "None":
        while True:
            user_data = ''
            for index, token in enumerate(tokens):
                if token == access_token:
                    user_data = database.get_user_data_from_id(users[index])
            if user_data != None and user_data != '': break
        return json.dumps({'user_data': user_data})
    return json.dumps({'state': 'logout'})

#==============================LOGIN===================================
@app.route('/login', methods=['POST'])
def login():
    username = request.json['username'].lower()
    password = request.json['password']
    remember = request.json['remember']
    if database.credentials_valid(username, password):
        while True:
            if remember == True:
                access_token = create_access_token(identity=username)
            else:
                access_token = "None"
            user_data = database.get_user_data(username)
            if user_data != None and access_token != None: 
                tokens.append(access_token)
                users.append(database.get_user_id(username))
                break
        response = json.dumps({'access_token': access_token, 'user_data': user_data})
        return response
    return INVALID_CREDENTIALS

#============================SIGNUP=====================================
@app.route('/signup', methods=['POST'])
def signup():
    username = request.json['username'].lower()
    password = request.json['password']
    email = request.json['email']
    invitation_code = request.json['invitationCode']
    if username == '' or password == '' or email == '':
        return EMPTY_ERROR
    if database.username_exists(username) or len(username) < 8 or len(username) > 25:
        return USERNAME_ERROR
    elif database.email_exists(email):
        return EMAIL_ERROR
    elif len(password) < 8 or len(password) > 25:
        return PASSWORD_ERROR
    else:
        while True:
            database.add_user(username, password, email, invitation_code) # TODO add invitation code here!!!
            # TODO add check to know if commit was successful===========================================
            access_token = create_access_token(identity=username)
            user_data = database.get_user_data(username)
            if user_data != None and access_token != None: 
                tokens.append(access_token)
                users.append(database.get_user_id(username))
                break
        response = {'access_token': access_token, 'user_data': user_data}
        return response
    return SIGNUP_ERROR

#==========================CHANGE-PASSWORD=======================================
@app.route('/password', methods=['POST'])
def password():
    username = request.json['username'].lower()
    password = request.json['password']
    new = request.json['new']
    if database.credentials_valid(username, password):
        if len(new) >= 8 and len(new) <= 25:
            database.change_user_password(username, new)
            return SUCCESS
        return PASSWORD_ERROR
    return INVALID_CREDENTIALS

#========================RETURN-MANUAL============================================
@app.route('/guide', methods=['GET'])
def guide():
    try:
        file = open('assets/guide.json')
        guide = json.load(file)
        return guide
    except:
        return ERROR

#=========================LOGOUT===============================================
@app.route('/logout', methods=['POST'])
def logout():
    access_token = request.json['access_token']
    for index, token in enumerate(tokens):
        if access_token == token:
            tokens.remove(index)
            users.remove(index)
    return SUCCESS

#=========================TASKS================================================
@app.route('/tasks', methods=['POST'])
def task():
    function = request.json['function']
    if function == 'get':
        username = request.json['username'].lower()
        tasks = database.get_user_tasks(username)
        return json.dumps({'tasks': tasks})
    elif function == 'add':
        username = request.json['username'].lower()
        social = request.json['social']
        if database.add_task(username, social) == 0:
            return ERROR
        else:
            return SUCCESS
    elif function == 'update':
        id = request.json['id']
        database.update_task(id, 1)
        return SUCCESS

#=======================FEED==================================================
feed_stack = []
start_time = datetime.now()
wait = random.randint(1, 59)

@app.route('/feed', methods=['GET'])
def feed():
    global start_time, wait
    if len(feed_stack) == 0:
        for i in range(0, 6):
            # Create random username and level
            username = random.choice(string.ascii_letters) + random.randint(7, 14)*"*" + random.choice(string.ascii_letters)
            upgraded_to = random.randint(2, 6)
            feed_stack.append([username, upgraded_to])
        return json.dumps({'feed': feed_stack})
    elif (start_time - datetime.now()).total_seconds() >= wait:
        stack.pop()
        start_time = datetime.now()
        wait = random.randint(1, 19)
        # Create new feed
        username = random.choice(string.ascii_letters) + random.randint(7, 19)*"*" + random.choice(string.ascii_letters)
        upgraded_to = random.randint(2, 6)
        feed_stack.append([username, upgraded_to])
        stack.append()
        return json.dumps({'feed': feed_stack})
    return json.dumps({'feed': feed_stack})

#========================LEVEL-UPGRADE========================================
@app.route('/upgrade', methods=['POST'])
def upgrade():
    username = request.json['username']
    level = request.json['level']
    if database.upgrade_user(username, level) == 1:
        return SUCCESS
    return ERROR


#=============================ERROR============================================
@app.errorhandler(Exception)
def handle_error(e):
    code = 500
    if isinstance(e, HTTPException):
        return json.dumps({'error': str(e), 'code': e.code})
'''
@app.errordatabase(500)
'''
