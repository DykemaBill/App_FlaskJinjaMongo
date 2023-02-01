# The 2 test users in the users.cfg file have the following starter password
## T3stUs3rP@ssword

# Import libraries
from flask import Flask, g, render_template, request, session, redirect, url_for
from datetime import timedelta, datetime
import bcrypt, re, os, sys, platform
import mgt.emailalert as emailalert
import mgt.config as config
import mgt.passmanage as passmanage

# Configuration files
config_folder = "config"
config_name = "settings"
config_file = os.path.join(config_folder, config_name + ".cfg")
users_name = "users"
users_file = os.path.join(config_folder, users_name + ".cfg")
orgs_name = "orgs"
orgs_file = os.path.join(config_folder, orgs_name + ".cfg")
log_folder = "logs"
log_name = "app_fjm"
log_file = os.path.join(log_folder, log_name + ".log")

# Read configuration
configuration = dict({})
def config_load():
    global configuration
    configuration = config.read_cfg(config_file)
config_load()

# Read users
users = list([])
def users_load():
    global users
    users = config.read_users(users_file)
users_load()

# Read organizations
orgs = list([])
def orgs_load():
    global orgs
    orgs = config.read_orgs(orgs_file)
orgs_load()

# Setup logging
logger = config.setup_log(log_file, configuration['logfilesize'][0], configuration['logfilesize'][1])

# Starting up
logger.info('****====****====****====****====****====**** App Starting ****====****====****====****====****====****')

# Config values write out to log
if configuration['error'] == True:
    print ("Unable to set config variables")
    logger.info('Problem reading ' + config_file + ', check your configuration file!')
else: # Config settings out to the log
    print ("Configuration files read")
    logger.info('    Log file size: ')
    logger.info('            Bytes: ' + str(configuration['logfilesize'][0]))
    logger.info('          Backups: ' + str(configuration['logfilesize'][1]))
    logger.info('  Email is set to: ' + configuration['email'])
    logger.info('   SMTP is set to: ' + configuration['smtp'])
    logger.info('   Team is set to: ' + configuration['team'])
    logger.info('   Logo is set to: ' + configuration['logo'])
    logger.info(' Logo size is set: ' + str(configuration['logosize'][0]) + ', ' + str(configuration['logosize'][1]))
    logger.info('   DB collections: ')
    for collection in configuration['db_coll']:
        logger.info('                   ' + collection)

# Orgs write out to log
if len(orgs) > 1:
    print ("Organization records read")
    logger.info('       Orgs found: ')
    for org_record in orgs:
        # Write organization to the log
        logger.info('                   ' + org_record['name'])
else:
    configuration['error'] = True
    print ("Unable to find any organizations")
    logger.info('Problem reading ' + orgs_file + ', check your organizations file!')

# Users write out to log
if len(users) > 1:
    print ("User records read")
    logger.info('      Users found: ')
    for user_record in users:
        # Find the organization name
        org_name = "None"
        for user_org in orgs:
            if user_org['_index'] == user_record['org']:
                org_name = user_org['name']
        # Write user and their organization to the log
        logger.info('                   ' + user_record['namelast'] + ', ' + user_record['namefirst'] + ' (' + user_record['login'] + ') - ' + org_name)
else:
    configuration['error'] = True
    print ("Unable to find any users")
    logger.info('Problem reading ' + users_file + ', check your users file!')

# Application start
fjm_app = Flask(__name__)

# Add secret key since session requires it
fjm_app.secret_key = 'blah secret thing here blah'
# Set the length of time someone stays logged in
fjm_app.permanent_session_lifetime = timedelta(hours=1)

# File upload settings
fjm_app.config['MAX_CONTENT_PATH'] = 50000000 # 50000000 equals 50MB

# Existing user session
def session_existing():
    # Find the session user ID
    user_session = [user_record for user_record in users if user_record['_index'] == session['user_id']][0]
    org_session = {'_index': 999999999999, 'name': 'None'} # Organization default
    # Find the user organization
    for org_record in orgs:
        if int(org_record['_index']) == int(user_session['org']) and org_record['name'] != "_deleted": # Set organization
            org_session = org_record
    # Set global variables for user
    g.user = user_session
    g.org = org_session
    # Set global variables to be used in web pages
    g.logo = configuration['logo']
    g.logosize = configuration['logosize']
    g.team = configuration['team']
    g.email = configuration['email']

# New user session
def session_new():
     # Setup guest variables
    user_guest = {"_index": 999999999999, "login": "guest", "password": "nopass", "admin": False, "approved": False, "orgadmin": False, "org": 999999999999, "pagerecords": 5}
    org_session = {'_index': 999999999999, 'name': 'None'} # Organization default
    if 'user_id' not in session:
        # Create guest login session
        session['user_id'] = int(user_guest['_index'])
    # Set global variables for guest
    g.user = user_guest
    g.org = org_session
    # Set global variables to be used in web pages
    g.logo = configuration['logo']
    g.logosize = configuration['logosize']
    g.team = configuration['team']
    g.email = configuration['email']

# Setup user session from browser or API
def session_setup():
    # Set the session to be saved by client in browser or API client if it is capturing the session
    session.permanent = True
    # Reload all configuration files to capture any changes made
    config_load()
    users_load()
    # Users check
    if len(users) < 1:
        configuration['error'] = True
        print ("Unable to find any users")
        logger.info('Problem reading ' + users_file + ', check your users file!')
    orgs_load()
    # Orgs check
    if len(orgs) < 1:
        configuration['error'] = True
        print ("Unable to find any organizations")
        logger.info('Problem reading ' + orgs_file + ', check your organizations file!')
    if configuration['error'] == False:
        # Check to see if the end user already has an existing session
        if 'user_id' in session and int(session['user_id']) != 999999999999: # User session exists and it is not a guest
            session_existing()
        else: # User is a new or existing guest
            session_new()
        return False
    else:
        return True

# Endpoint pre-processing
@fjm_app.before_request
def before_request():
    # Setup the session for the user
    failure = session_setup()
    if failure: # Returns true if there was a problem
        return render_template('error.html')

# Endpoint root
@fjm_app.route('/')
def landing():
    logger.info(request.remote_addr + ' ==> Landing page (' + str(g.user['login']) + ' - ' + str(g.org['name']) + ')')
    if int(g.org['_index']) == 999999999999: # User is not assigned to an organization
        return render_template('landing.html', pagetitle="You must be assigned to an orgnization to have access")
    else:
        return render_template('landing.html')
            
# Logs page
@fjm_app.route('/status')
def status():
    if int(session['user_id']) == 999999999999: # User is a guest
        # Put a delay in to slow denial-of-service attacks
        # time.sleep(5)
        logger.info(request.remote_addr + ' ==> Status page denied (' + str(g.user['login']) + ')')
        return redirect(url_for('loginpage', requestingurl=request.full_path))
    elif int(g.org['_index']) == 999999999999: # User is not assigned to an organization
        logger.info(request.remote_addr + ' ==> Status page denied for no organization (' + str(g.user['login']) + ')')
        return redirect(url_for('landing'))
    if g.user['admin'] == False: # User is not an admin
        # Show server status page access error
        logger.info(request.remote_addr + ' ==> Status page denied for none admin (' + str(g.user['login']) + ' - ' + str(g.org['name']) + ')')
        return render_template('status.html', pagetitle="You must be admin to view this page")
    running_python = sys.version.split('\n')
    running_host = platform.node()
    running_os = platform.system()
    running_hardware = platform.machine()
    try:
        with open(log_file, 'r') as logging_file:
            log_data = logging_file.read()
    except IOError:
        print('Problem opening ' + log_file + ', check to make sure your log file location is valid.')
        log_data = "Unable to read log file " + log_file
    logger.info(request.remote_addr + ' ==> Status page (' + str(g.user['login']) + ' - ' + str(g.org['name']) + ')')
    return render_template('status.html', running_python=running_python, running_host=running_host, running_os=running_os, running_hardware=running_hardware, config_data=configuration, log_data=log_data)

# Login page
@fjm_app.route('/login', methods=['GET', 'POST'])
def loginpage():
    # Put a delay in to slow brute-force attacks
    # time.sleep(5)
    if request.method == 'POST':
        # Clear any previous login session
        session.pop('user_id', None)
        # Process login after form is filled out and a POST request happens
        try:
            user_request_login = request.form['user_login']
            user_request_pass = request.form['user_pass']
            user_returnto = request.form['returnto']
        except:
            user_request_login = "None"
            user_request_pass = "None"
            user_returnto = ""
        # Look to see if this is a valid user
        user_check = [user_record for user_record in users if user_record['login'] == user_request_login]
        if not user_check:
            # Non-existent user login
            logger.info(request.remote_addr + ' ==> Login failed, ' + user_request_login + ' does not exist')
            return render_template('login.html', pagetitle="User does not exist, try again")
        else:
            # Get stored password
            password_stored = user_check[0]['password']
            # Get the salt from first 29 characters of password stored
            password_stored_salt_decoded = password_stored[:29]
            # Convert the previously used salt to a byte
            password_stored_salt = password_stored_salt_decoded.encode("utf-8")
            # Hash the entered password with previously used salt
            password_entered = passmanage.passhash(user_request_pass, password_stored_salt)
            # Correct password
            if password_entered == password_stored:
                # Check to make sure user is approved
                user_approved = [user_record for user_record in users if user_record['login'] == user_request_login and user_record['approved'] == True]
                if not user_approved:
                    # Login successful, but user not approved
                    logger.info(request.remote_addr + ' ==> Login successful, but not approved (' + str(g.user['login']) + ')')
                    return render_template('login.html', pagetitle="Login successful, but not approved, check with your administrator")
                else:
                    # Set session to logged in user
                    session['user_id'] = int(user_check[0]['_index'])
                    # Set global variables for user
                    g.user = user_check[0]
                    # Redirect sucessfully logged in user to configuration page
                    logger.info(request.remote_addr + ' ==> Login successful (' + str(g.user['login']) + ')')
                    if len(user_returnto) > 0: # Check to see what page URL was looking for
                        return redirect(user_returnto) # Go to calling page for login
                    else:
                        return redirect(url_for('landing')) # No calling page for login
            else: # Incorrect password
                logger.info(request.remote_addr + ' ==> Login failed, bad password (' + str(g.user['login']) + ' - ' + str(g.org['name']) + ')')
                return render_template('login.html', pagetitle="Incorrect password, try again")
    else:
        # Show login page on initial GET request
        logger.info(request.remote_addr + ' ==> Login page (' + str(g.user['login']) + ' - ' + str(g.org['name']) + ')')
        forwardurl = ""
        if 'requestingurl' in request.args: # Pass from URL if supplied
            forwardurl = request.args['requestingurl']
        return render_template('login.html', pagetitle="Please login", returnto=forwardurl)

# Logout page
@fjm_app.route('/logout')
def logoutpage():
    logger.info(request.remote_addr + ' ==> Logout page (' + str(g.user['login']) + ' - ' + str(g.org['name']) + ')')
    # Clear login session
    session.pop('user_id', None)
    # Setup guest variables
    user_guest = {"_index": 999999999999, "login": "guest", "password": "nopass", "org": 999999999999}
    # Create guest login session
    session['user_id'] = int(user_guest['_index'])
    # Set global variables for guest
    g.user = user_guest
    return render_template('login.html', pagetitle="You have successfully logged out")

# Login create page
@fjm_app.route('/loginnew', methods=['GET', 'POST'])
def loginnewpage():
    if request.method == 'POST':
        # Process new login after form is filled out and a POST request happens
        try:
            user_request_login = request.form['user_login'].lower()
            user_request_pass = request.form['user_pass']
            user_request_namelast = request.form['user_namelast']
            user_request_namefirst = request.form['user_namefirst']
            user_request_email = request.form['user_email']
        except:
            user_request_login = "None"
            user_request_pass = "None"
            user_request_namelast = "Name error"
            user_request_namefirst = "Name error"
            user_request_email = "Email error"

        logger.info(request.remote_addr + ' ==> Login create request ' + user_request_login + ", " + user_request_namefirst + " " + user_request_namelast + ", " + user_request_email)
        
        # Look to see if a user with the same login already exists
        user_check = [user_record for user_record in users if user_record['login'].lower() == user_request_login]
        user_approved = False
        user_admin = False
        user_org = 999999999999
        user_orgadmin = False
        user_pagerecords = 5
        user_darkmode = False
        user_alert = True
        user_new_message = "but not approved!"
        if user_check:
            # Login is already in use
            logger.info(request.remote_addr + ' ==> Login name ' + user_request_login + ' already exists')
            return render_template('loginnew.html', pagetitle="Login name not available, try again")
        else: # Login not in use already
            if users: # There are existing users
                # Find index to use for new user
                user_last = users[-1]
                user_last_index = user_last['_index']
                user_index = user_last_index + 1
            else: # There are no users yet
                user_index = 0
                user_approved = True
                user_admin = True
                user_new_message = "first user automatically approved!"
            # Generate a one-time salt for this password in byte format
            pass_salt = bcrypt.gensalt()
            # Hash password
            user_pass_hash = passmanage.passhash(user_request_pass, pass_salt)

            # Write the new user for the users file
            dataupdate_newuser = {
                "_index": user_index,
                "admin": user_admin,
                "approved": user_approved,
                "darkmode": user_darkmode,
                "email": user_request_email,
                "alert": user_alert,
                "login": user_request_login,
                "namefirst": user_request_namefirst,
                "namelast": user_request_namelast,
                "org": user_org,
                "orgadmin": user_orgadmin,
                "pagerecords": user_pagerecords,
                "password": user_pass_hash
            }

            # Create backup of users file
            backup_users_attempt = config.backup_users(users_file)
            if backup_users_attempt == False:
                logger.info(request.remote_addr + ' ==> Problem creating backup of ' + users_file + ', check to make sure your filesystem is not write protected.')

            # Add new user
            new_user_attempt = config.new_user(users_file, dataupdate_newuser)
            if new_user_attempt == False:
                logger.info(request.remote_addr + ' ==> Problem adding new user ' + dataupdate_newuser['login'] + ', check to make sure your filesystem is not write protected.')
            else:
                # Write user info to log without encoded password
                dataupdate_newuser_log = {
                    "_index": user_index,
                    "approved": user_approved,
                    "admin": user_admin,
                    "login": user_request_login,
                    "password": "*******",
                    "namelast": user_request_namelast,
                    "namefirst": user_request_namefirst,
                    "email": user_request_email,
                    "alert": user_alert,
                    "org": user_org,
                    "orgadmin": user_orgadmin,
                    "pagerecords": user_pagerecords,
                    "darkmode": user_darkmode
                }
                logger.info(request.remote_addr + ' ==> Added user: ' + str(dataupdate_newuser_log))

            # Reload users configuration file
            users_load()

            # Let user know they are added and whether they are approved or not
            return render_template('login.html', pagetitle="New user " + user_request_login + " added, " + user_new_message)

    else:
        # Show login create page on initial GET request
        logger.info(request.remote_addr + ' ==> Login create page (' + str(g.user['login']) + ' - ' + str(g.org['name']) + ')')
        # Clear login session
        session.pop('user_id', None)
        # Setup guest variables
        user_guest = {"_index": 999999999999, "login": "guest", "password": "nopass", "org": 999999999999}
        # Create guest login session
        session['user_id'] = int(user_guest['_index'])
        # Set global variables for guest
        g.user = user_guest
        return render_template('loginnew.html', pagetitle="Create a new login")

# Login password change
@fjm_app.route('/loginpassword', methods=['GET', 'POST'])
def loginpassword():
    if int(session['user_id']) == 999999999999: # User is a guest
        return redirect(url_for('loginpage', requestingurl=request.full_path))
    else:
        if request.method == 'POST':
            # Process password change form when a POST request happens
            try:
                user_request_passold = request.form['user_pass_old']
                user_request_passnew = request.form['user_pass_new']
            except:
                user_request_passold = "NoOld"
                user_request_passnew = "NoNew"
            # Salt is first 29 characters of the stored password
            password_salt_encoded = g.user['password'][:29]
            # Convert the stored salt to a byte
            password_salt = password_salt_encoded.encode("utf-8")
            # Hash the old password entered with the salt
            password_old_entered = passmanage.passhash(user_request_passold, password_salt)
            # Correct old password
            if password_old_entered == g.user['password']:
                # Change password to new one
                g.user['password'] = passmanage.passhash(user_request_passnew, password_salt)
                
                # Write the login information for the config file
                dataupdate_userchanged = {
                    "_index": g.user['_index'],
                    "approved": g.user['approved'],
                    "admin": g.user['admin'],
                    "login": g.user['login'],
                    "password": g.user['password'],
                    "namelast": g.user['namelast'],
                    "namefirst": g.user['namefirst'],
                    "email": g.user['email'],
                    "alert": g.user['alert'],
                    "org": g.user['org'],
                    "orgadmin": g.user['orgadmin'],
                    "pagerecords": g.user['pagerecords'],
                    "darkmode": g.user['darkmode']
                }

                # Create backup of users file
                backup_users_attempt = config.backup_users(users_file)
                if backup_users_attempt == False:
                    logger.info(request.remote_addr + ' ==> Problem creating backup of ' + users_file + ', check to make sure your filesystem is not write protected.')

                # Replace updated login
                mod_user_attempt = config.modify_user(users_file, dataupdate_userchanged)
                if mod_user_attempt == False:
                    logger.info(request.remote_addr + ' ==> Problem modifying password for user ' + dataupdate_userchanged['login'] + ', check to make sure your filesystem is not write protected.')
                else:
                    # Write user info to log without encoded password
                    dataupdate_login_log = {
                        "_index": g.user['_index'],
                        "approved": g.user['approved'],
                        "admin": g.user['admin'],
                        "login": g.user['login'],
                        "password": "*******",
                        "namelast": g.user['namelast'],
                        "namefirst": g.user['namefirst'],
                        "email": g.user['email'],
                        "alert": g.user['alert'],
                        "org": g.user['org'],
                        "orgadmin": g.user['orgadmin'],
                        "pagerecords": g.user['pagerecords'],
                        "darkmode": g.user['darkmode']
                    }
                    logger.info(request.remote_addr + ' ==> Modified user: ' + str(dataupdate_login_log))

                # Redirect sucessfully changed to main page
                return redirect(url_for('landing'))
            else: # Incorrect password
                logger.info(request.remote_addr + ' ==> Old password for ' + str(g.user['login']) + ' - ' + str(g.org['name']) + ' not correct')
                return render_template('loginpassword.html', pagetitle="Old password not correct")
        else:
            # Show login password change page on initial GET request
            logger.info(request.remote_addr + ' ==> Login password change page (' + str(g.user['login']) + ' - ' + str(g.org['name']) + ')')
            return render_template('loginpassword.html', pagetitle="Change your password")

# Darkmode setting
@fjm_app.route('/darkmode')
def darkmode():
    logger.info(request.remote_addr + ' ==> Darkmode change (' + str(g.user['login']) + ' - ' + str(g.org['name']) + ')')
    # Place holder page
    return render_template('placeholder.html')

# Run in debug mode if started from CLI (http://localhost:5000)
if __name__ == '__main__':
    fjm_app.run(debug=True)