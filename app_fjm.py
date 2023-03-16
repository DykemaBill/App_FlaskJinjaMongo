# Import libraries
from flask import Flask, g, render_template, request, session, redirect, url_for
from flask_pymongo import PyMongo # Needed for all MongoDB operations except deleting files
from datetime import timedelta, datetime
import bcrypt, re, os, sys, platform
from mgt.config import *
from mgt.passmanage import *
from mgt.emailalert import *

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
    configuration = read_cfg(config_file)
config_load()

# Users tracking
users_exist = False # Assumes no users exist

# Read users
users = list([])
def users_load():
    global users
    users = read_users(users_file)
users_load()

# Read organizations
orgs = list([])
def orgs_load():
    global orgs
    orgs = read_orgs(orgs_file)
orgs_load()

# Create log folder if it does not already exist
if not os.path.exists(log_file):
    os.mkdir(log_file)

# Setup logging
logger = setup_log(log_file, configuration['logfilesize'][0], configuration['logfilesize'][1])

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
    for collection in configuration['dbcoll']:
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
    users_exist = False
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

db_connection_error = True # Default to an error

# Create connection to database
db_inst = PyMongo(fjm_app, uri=configuration['dbconn'])

# Test and log connection
def db_test():
    global db_connection_error
    # MongoDB object, db_conn_type of mongodb for non-Atlas hosted
    if configuration['error'] == False:
        # Remove password for the log
        db_conn_host, db_conn_type, db_conn_remaining = str(configuration['dbconn']).split(":")
        db_conn_end = str(db_conn_remaining).split("@")[1]
        db_conn_log = db_conn_host + ":" + db_conn_type + ':[password]@' + db_conn_end
        try:
            # Test connection, will bomb if above connection did not work
            test_query = int(db_inst.db["not_real_collection"].count_documents({'not_real_record': "nothing_here"}))
            db_connection_error = False # Database connected if made it here
            logger.info('  Connected to DB: ' + db_conn_log)
        except:
            db_connection_error = True # Flag an error if we cannot connect to the database
            print("Database failed to connect!")
            logger.info('   Failed conn DB: ' + db_conn_log)
    else:
        # Configuration error, do not attempt to connect to database
        db_connection_error = True
        print("Database not connected because of problem opening " + config_file + ".")
        logger.info('Database not connected because of problem opening ' + config_file)
db_test()

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
    global users_exist # Will use this to decide if we have users yet
    # Set the session to be saved by end-user browser or API if it is capturing the session
    session.permanent = True
    # Reload all configuration files to capture any changes made
    config_load()
    users_load()
    # Users check
    if len(users) < 1:
        users_exist = False
        print ("Unable to find any users")
        logger.info('Problem reading ' + users_file + ', will assume we need to prompt to create one.')
    else:
        users_exist = True
    orgs_load()
    # Orgs check
    if len(orgs) < 1:
        configuration['error'] = True
        print ("Unable to find any organizations")
        logger.info('Problem reading ' + orgs_file + ', check your organizations file!')
    if configuration['error'] == False:
        # Check to see if the end user already has an existing session
        if 'user_id' in session and int(session['user_id']) != 999999999999 and users_exist: # User session exists and it is not a guest
            session_existing()
        else: # User is a new or existing guest
            session_new()
        return False
    else:
        return True

# Endpoint pre-processing
@fjm_app.before_request
def before_request():
    if db_connection_error == False:
        # Setup the session for the user
        failure = session_setup()
        if failure: # Returns true if there was a problem
            return render_template('error.html')
    else:
        return render_template('error.html')

# Endpoint root
@fjm_app.route('/')
def landingpage():
    logger.info(request.remote_addr + ' ==> Landing page (' + str(g.user['login']) + ' - ' + str(g.org['name']) + ')')
    if int(g.org['_index']) == 999999999999: # User is not assigned to an organization
        return render_template('landing.html', pagetitle="You must be assigned to an organization to have access", notnewinstall=users_exist)
    else:
        return render_template('landing.html', pagetitle="Collections", config_data=configuration)

# Collections page listing records
@fjm_app.route('/colls')
def collspage():
    # Page records to show parameters
    page_start = request.args.get('start', default = 1, type = int)
    if (page_start < 1):
        page_start = 1
    page_records = request.args.get('records', default = g.user['pagerecords'], type = int)
    page_total = 0
    page_dims = dict({'start': page_start, 'records': page_records, 'total': page_total})
    # End-user filter selections
    filter_number = request.args.get('num', default = 999999999999, type = int)
    filter_name = request.args.get('name', default = "", type = str)
    filter_owner = request.args.get('owner', default = 999999999999, type = int)
    filter_org = request.args.get('org', default = 999999999999, type = int)
    # Build filter
    query_filter = dict({})
    if (filter_number != 999999999999):
        query_filter['record_number'] = filter_number
    if (filter_name != ""):
        query_filter['record_name'] = filter_name
    if (filter_owner != 999999999999):
        query_filter['record_user'] = filter_owner
    if (filter_org != 999999999999):
        query_filter['record_org'] = filter_org
    # Page
    page_title = "Records"
    if users_exist == False: # No users exist, will need to prompt to create one
        logger.info(request.remote_addr + ' ==> No users exist yet, prompting to create admin account )')
        return redirect(url_for('loginnewpage'))
    if int(session['user_id']) == 999999999999: # User is a guest
        logger.info(request.remote_addr + ' ==> Collections listing page access error (' + str(g.user['login']) + ')')
        # Put a delay in for denial-of service attacks
        # time.sleep(5)
        return redirect(url_for('loginpage', requestingurl=request.full_path))
    if g.user['admin'] == False and int(g.org['_index']) == 999999999999: # User is not admin or in an org
        logger.info(request.remote_addr + ' ==> Collections page org error for collection ' + filter_name + '(' + str(g.user['login']) + ')')
        return render_template('collections.html', pagetitle="Please have your admin assign you to your organization", org_records=orgs, user_records=users, pagedims=page_dims)
    else: # User is valid and in an organization
        # Collection name argument passed
        data_coll = request.args.get('data', default = "", type = str)
        if (data_coll == ""):
            logger.info(request.remote_addr + ' ==> Collection name not passed (' + str(g.user['login']) + ' - ' + str(g.org['name']) + ')')
            page_title = "You must pass a collection name"
            # Show page error
            return render_template('collections.html', pagetitle=page_title, pagedims=page_dims)
        page_title = "Records for collection: " + str(data_coll)
        # Setup sort
        record_sort = tuple([('record_name', 1)])
        # Create list to collect records
        record_list = []
        # Read all records
        logger.info(request.remote_addr + ' ==> Record listing page (' + str(g.user['login']) + ' - ' + str(g.org['name']) + ')')
        try: # Get the list of records
            if int(filter_number) == 999999999999: # Find all records visible to this user
                if (g.user['admin'] == True): # User is admin, get all records
                    query_run = query_filter
                else: # User is org admin or user, in the page non-org admins will not see links for records they do not own
                    # Override user and organization filter to just the user
                    query_filter['record_org'] = int(g.org['_index'])
                    query_run = query_filter
                # Record count
                page_total = int(db_inst.db[data_coll].count_documents(query_run))
                if (page_start >= page_total):
                    page_start = page_total
                # Query
                record_list = list(db_inst.db[data_coll].find(query_run).sort(record_sort).skip(page_start-1).limit(page_records))
            else: # Find just the record requested
                record_number = filter_number
                page_total = 1
                page_start = 1
                page_title = "Record filtered"
                if (g.user['admin'] == True): # User is admin, get the record no matter who it is tied to
                    record_list.append(dict(db_inst.db[data_coll].find_one({'record_number': int(record_number)})))
                elif (g.user['orgadmin'] == True): # User is org admin, get the record if tied to the user's org
                    record_list.append(dict(db_inst.db[data_coll].find_one({'record_number': int(record_number), 'record_org': int(g.org['_index'])})))
                else: # Get record if it is owned by the user
                    record_list.append(dict(db_inst.db[data_coll].find_one({'record_number': int(record_number), 'record_user': int(g.user['_index'])})))
        except: # Error if failed
            logger.info(request.remote_addr + ' ==> Database error reading records (' + str(g.user['login']) + ' - ' + str(g.org['name']) + ')')
            page_title = "No access to record or it does not exist"
        # Update total number of records and start based on the query
        page_dims['total'] = page_total
        page_dims['start'] = page_start
        if len(record_list) > 0: # Render page with records
            return render_template('collections.html', pagetitle=page_title, recordlist=record_list, org_records=orgs, user_records=users, pagedims=page_dims)
        else: # Render page without records
            page_title = "No Records"
            return render_template('collections.html', pagetitle=page_title, org_records=orgs, user_records=users, pagedims=page_dims)

# Collection page listing fields from one record
@fjm_app.route('/coll', methods=['GET', 'POST'])
def collpage():
    # Page record parameters
    # End-user filter selections
    filter_number = request.args.get('num', default = 999999999999, type = int)
    # Build filter
    query_filter = dict({})
    if (filter_number != 999999999999):
        query_filter['record_number'] = filter_number
    # Page
    page_title = "Record"
    if users_exist == False: # No users exist, will need to prompt to create one
        logger.info(request.remote_addr + ' ==> No users exist yet, prompting to create admin account )')
        return redirect(url_for('loginnewpage'))
    if int(session['user_id']) == 999999999999: # User is a guest
        logger.info(request.remote_addr + ' ==> Collection page access error for ' + filter_number + ' (' + str(g.user['login']) + ')')
        # Prompt to login
        return redirect(url_for('loginpage', requestingurl=request.full_path))
    if g.user['admin'] == False and int(g.org['_index']) == 999999999999: # User is not admin or in an org
        logger.info(request.remote_addr + ' ==> Collection page access error for ' + filter_number + ' (' + str(g.user['login']) + ')')
        page_title = "You must be in an organization to see records"
        # Show page error
        return render_template('collection.html', pagetitle=page_title)
    else:
        # Collection name argument passed
        data_coll = request.args.get('data', default = "", type = str)
        if (data_coll == ""):
            logger.info(request.remote_addr + ' ==> Collection name not passed (' + str(g.user['login']) + ' - ' + str(g.org['name']) + ')')
            page_title = "You must pass a collection name"
            # Show page error
            return render_template('collection.html', pagetitle=page_title)
        if request.method == 'POST':
            # Current time
            nowIs = datetime.now().strftime("_%Y%m%d-%H%M%S%f")
            # Process new record after form is filled out and a POST request happens
            record_new = True
            record_user = 999999999999
            record_org = 999999999999
            try: # Existing record
                record_number = int(request.form['record_number'])
                record_new = False
                record_user = int(request.form['record_user'])
                record_org = int(request.form['record_org'])
            except: # New record
                record_number = int(datetime.now().strftime("%Y%m%d%H%M%S") + str(session['user_id']).zfill(4))
                record_new = True
                record_user = int(g.user['_index'])
                record_org = int(g.org['_index'])
            # Get remaining record fields
            try:
                record_name = request.form['record_name']
            except:
                record_name = "Name error"

            record_message = ""

            record_file_version = "None"
            if 'record_file' in request.files:
                # File object
                record_file = request.files['record_file']
                if record_file:
                    # Name to use to reference the file with time in to avoid duplicates
                    record_file_name, record_file_extension = os.path.splitext(record_file.filename)
                    record_file_clean = re.sub('[^A-Za-z0-9]+', '', record_file_name)
                    if (record_file_clean == ""):
                        record_file_clean = "Doc"
                    record_file_version = record_file_clean + nowIs + record_file_extension
                    document_number = int(datetime.now().strftime("%Y%m%d%H%M%S") + str(session['user_id']).zfill(4))
                    try:
                        # Write file object to database
                        db_inst.save_file(record_file_version, record_file)
                        record_message = "Document added"
                        # Create new document record
                        db_inst.db[data_coll].insert_one({'document_number': document_number, 'document_record': record_number, 'document_file': record_file_version, 'document_name': record_file.filename})
                        logger.info(request.remote_addr + ' ==> Document ' + str(document_number) + ' stored (' + str(g.user['login']) + ' - ' + str(g.org['name']) + ')')
                        record_message = "Document stored"
                    except:
                        logger.info(request.remote_addr + ' ==> Database error adding document (' + str(g.user['login']) + ' - ' + str(g.org['name']) + ')')
                        record_message = "Document not added, database error"
            document_records = []
            try: # Read document record
                document_records = list(db_inst.db[data_coll].find({'document_record': int(record_number) }))
            except: # Error if failed
                logger.info(request.remote_addr + ' ==> Database error reading document record for confirmation page (' + str(g.user['login']) + ' - ' + str(g.org['name']) + ')')
                document_records.append({'document_number': 999999999999, 'document_record': 999999999999, 'document_file': "None"})
                page_title = "Database error reading document record"

            # Write new record info to log
            new_record_details = {
                "record_number": record_number,
                "record_name": record_name,
                "record_user": record_user,
                "record_org": record_org
            }

            if record_new:
                try:
                    # Create new record in database collection
                    db_inst.db[data_coll].insert_one({'record_number': int(record_number), 'record_name': record_name, 'record_user': int(record_user), 'record_org': int(record_org)})
                    record_message = "Record added to collection: " + str(data_coll)
                    logger.info(request.remote_addr + ' ==> New record (' + str(g.user['login']) + ' - ' + str(g.org['name']) + '): ' + str(new_record_details))
                except:
                    logger.info(request.remote_addr + ' ==> Database error adding new record (' + str(g.user['login']) + ' - ' + str(g.org['name']) + ')')
                    record_message = "Record not added, database error for collection: " + str(data_coll)
            else:
                if g.user['admin'] == True or int(g.user['_index']) == record_user or (int(g.user['org']) == record_org and g.user['orgadmin'] == True): # User is admin, record owner, or record org admin
                    try:
                        # Modify existing record details in database collection
                        db_inst.db[data_coll].replace_one({'record_number': int(record_number) },{'record_number': int(record_number), 'record_name': record_name, 'record_user': int(record_user), 'record_org': int(record_org)})
                        record_message = "Record modified in collection: " + str(data_coll)
                        logger.info(request.remote_addr + ' ==> Modified record (' + str(g.user['login']) + ' - ' + str(g.org['name']) + '): ' + str(new_record_details))
                    except:
                        logger.info(request.remote_addr + ' ==> Database error modifying record (' + str(g.user['login']) + ' - ' + str(g.org['name']) + ')')
                        record_message = "Record not modified, database error for collection: " + str(data_coll)
                else:
                    logger.info(request.remote_addr + ' ==> Denied access to modify record (' + str(g.user['login']) + ' - ' + str(g.org['name']) + ')')
                    record_message = "Record not modified error"
                    new_record_details = ({'record_number': 999999999999, 'record_name': "Blocked...", 'record_user': 999999999999, 'record_org': 999999999999})
                    document_records.append({'document_number': 999999999999, 'document_record': 999999999999, 'document_file': "Blocked..."})

            # Confirm new record
            return render_template('collection.html', pagetitle=record_message, recorddetails=new_record_details, recorddocuments=document_records, org_records=orgs, user_records=users)

        else: # GET request
            # Show individual record page
            page_title = "Record"
            if int(filter_number) == 999999999999: # New record
                logger.info(request.remote_addr + ' ==> New record page (' + str(g.user['login']) + ' - ' + str(g.org['name']) + ')')
                page_title = "Create a new record in collection: " + str(data_coll)
                return render_template('collection.html', pagetitle=page_title, org_records=orgs, user_records=users)
            else: # Existing record
                record_number = filter_number
                new_record = {}
                try: # Read record
                    new_record = dict(db_inst.db[data_coll].find_one({'record_number': int(record_number) }))
                except: # Error if failed
                    logger.info(request.remote_addr + ' ==> Database error reading record (' + str(g.user['login']) + ' - ' + str(g.org['name']) + ')')
                    new_record = ({'record_number': 999999999999, 'record_name': "Name error", 'record_user': 999999999999, 'record_org': 999999999999})
                    page_title = "Database error reading record"
                document_records = []
                if g.user['admin'] == True or int(g.user['_index']) == int(new_record['record_user']) or (int(g.user['org']) == int(new_record['record_org']) and g.user['orgadmin'] == True): # User is admin, record owner, or record org admin
                    try: # Read document record
                        document_records = list(db_inst.db[data_coll].find({'document_record': int(record_number) }))
                    except: # Error if failed
                        logger.info(request.remote_addr + ' ==> Database error reading document record (' + str(g.user['login']) + ' - ' + str(g.org['name']) + ')')
                        document_records.append({'document_number': 999999999999, 'document_record': 999999999999, 'document_file': "None"})
                        page_title = "Database error reading document record"
                    logger.info(request.remote_addr + ' ==> Existing record page (' + str(g.user['login']) + ' - ' + str(g.org['name']) + ')')
                else: # Denied access to record
                    logger.info(request.remote_addr + ' ==> Denied access to record (' + str(g.user['login']) + ' - ' + str(g.org['name']) + ')')
                    new_record = ({'record_number': 999999999999, 'record_name': "Blocked...", 'record_user': 999999999999, 'record_org': 999999999999})
                    document_records.append({'document_number': 999999999999, 'document_record': 999999999999, 'document_file': "Blocked..."})
                    page_title = "Record Access Error"
                return render_template('collection.html', pagetitle=page_title, recordedit=new_record, recorddocuments=document_records, org_records=orgs, user_records=users)

# Logs page
@fjm_app.route('/status')
def statuspage():
    if users_exist == False: # No users exist, will need to prompt to create one
        logger.info(request.remote_addr + ' ==> No users exist yet, prompting to create admin account )')
        return redirect(url_for('loginnewpage'))
    if int(session['user_id']) == 999999999999: # User is a guest
        # Put a delay in to slow denial-of-service attacks
        # time.sleep(5)
        logger.info(request.remote_addr + ' ==> Status page denied (' + str(g.user['login']) + ')')
        return redirect(url_for('loginpage', requestingurl=request.full_path))
    elif int(g.org['_index']) == 999999999999: # User is not assigned to an organization
        logger.info(request.remote_addr + ' ==> Status page denied for no organization (' + str(g.user['login']) + ')')
        return redirect(url_for('landingpage'))
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
    return render_template('status.html', pagetitle="Status", running_python=running_python, running_host=running_host, running_os=running_os, running_hardware=running_hardware, config_data=configuration, log_data=log_data)

# Login page
@fjm_app.route('/login', methods=['GET', 'POST'])
def loginpage():
    if users_exist == False: # No users exist, will need to prompt to create one
        logger.info(request.remote_addr + ' ==> No users exist yet, prompting to create admin account )')
        return redirect(url_for('loginnewpage'))
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
            password_entered = passhash(user_request_pass, password_stored_salt)
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
                        return redirect(url_for('landingpage')) # No calling page for login
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
    if users_exist == False: # No users exist, will need to prompt to create one
        logger.info(request.remote_addr + ' ==> No users exist yet, prompting to create admin account )')
        return redirect(url_for('loginnewpage'))
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
        user_orgadmin = False
        user_pagerecords = 5
        user_darkmode = False
        user_alert = True
        if users_exist:
            user_new_message = "but not approved!"
            user_approved = False
            user_admin = False
            user_org = 999999999999
        else: # Must be first user, adding as admin
            user_new_message = "as adminstrator since it is the first user!"
            user_approved = True
            user_admin = True
            user_org = 0
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
                user_new_message = "first user automatically approved as admin!"
            # Generate a one-time salt for this password in byte format
            pass_salt = bcrypt.gensalt()
            # Hash password
            user_pass_hash = passhash(user_request_pass, pass_salt)

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
            backup_users_attempt = backup_users(users_file)
            if backup_users_attempt == False:
                logger.info(request.remote_addr + ' ==> Problem creating backup of ' + users_file + ', check to make sure your filesystem is not write protected.')

            # Add new user
            new_user_attempt = new_user(users_file, dataupdate_newuser)
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
def loginpasswordpage():
    if users_exist == False: # No users exist, will need to prompt to create one
        logger.info(request.remote_addr + ' ==> No users exist yet, prompting to create admin account )')
        return redirect(url_for('loginnewpage'))
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
            password_old_entered = passhash(user_request_passold, password_salt)
            # Correct old password
            if password_old_entered == g.user['password']:
                # Change password to new one
                g.user['password'] = passhash(user_request_passnew, password_salt)
                
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
                backup_users_attempt = backup_users(users_file)
                if backup_users_attempt == False:
                    logger.info(request.remote_addr + ' ==> Problem creating backup of ' + users_file + ', check to make sure your filesystem is not write protected.')

                # Replace updated login
                mod_user_attempt = modify_user(users_file, dataupdate_userchanged)
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
                return redirect(url_for('landingpage'))
            else: # Incorrect password
                logger.info(request.remote_addr + ' ==> Old password for ' + str(g.user['login']) + ' - ' + str(g.org['name']) + ' not correct')
                return render_template('loginpassword.html', pagetitle="Old password not correct")
        else:
            # Show login password change page on initial GET request
            logger.info(request.remote_addr + ' ==> Login password change page (' + str(g.user['login']) + ' - ' + str(g.org['name']) + ')')
            return render_template('loginpassword.html', pagetitle="Change your password")

# User darkmode settings TODO: NEXT CHANGE THIS ROUTE AND ADD RECORDS PER PAGE
@fjm_app.route('/darkmode')
def darkmodeset():
    if users_exist == False: # No users exist, will need to prompt to create one
        logger.info(request.remote_addr + ' ==> No users exist yet, prompting to create admin account )')
        return redirect(url_for('loginnewpage'))
    if int(session['user_id']) == 999999999999: # User is a guest
        return redirect(url_for('loginpage', requestingurl=request.full_path))
    else:
        # Toggle darkmode setting
        if g.user['darkmode']:
            g.user['darkmode'] = False
        else:
            g.user['darkmode'] = True

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
        backup_users_attempt = backup_users(users_file)
        if backup_users_attempt == False:
            logger.info(request.remote_addr + ' ==> Problem creating backup of ' + users_file + ', check to make sure your filesystem is not write protected.')

        # Replace updated login
        mod_user_attempt = modify_user(users_file, dataupdate_userchanged)
        if mod_user_attempt == False:
            logger.info(request.remote_addr + ' ==> Problem modifying password for user ' + dataupdate_userchanged['login'] + ', check to make sure your filesystem is not write protected.')
        else:
            # Write user info to log without encoded password
            logger.info(request.remote_addr + ' ==> Darkmode setting changed (' + str(g.user['login']) + ' - ' + str(g.org['name']) + ')')

        # Return to page where darkmode change request came from
        forwardurl = "/" # Default to main page
        if 'requestingurl' in request.args: # Pass from URL if supplied
            forwardurl = request.args['requestingurl']
        return redirect(forwardurl)

# Place holder
@fjm_app.route('/notused')
def placeholderpage():
    if users_exist == False: # No users exist, will need to prompt to create one
        logger.info(request.remote_addr + ' ==> No users exist yet, prompting to create admin account )')
        return redirect(url_for('loginnewpage'))
    if int(session['user_id']) == 999999999999: # User is a guest
        logger.info(request.remote_addr + ' ==> Place holder page access error (' + str(g.user['login']) + ')')
        # Put a delay in for denial-of service attacks
        # time.sleep(5)
        return redirect(url_for('loginpage', requestingurl=request.full_path))
    logger.info(request.remote_addr + ' ==> Place holder page (' + str(g.user['login']) + ' - ' + str(g.org['name']) + ')')
    # Place holder page
    return render_template('placeholder.html', pagetitle="Flask / Jinja2 / MongoDB")

# Run in debug mode if started from CLI (http://localhost:5000)
if __name__ == '__main__':
    fjm_app.run(debug=True)