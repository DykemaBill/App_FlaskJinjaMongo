# Import libraries
import sys, json, time
import logging, logging.handlers

# Read configuration
def read_cfg(config_file):
    # Set default configuration variables
    support_team = "needtosetteamname"
    support_email = "needtosetinconfig@nowhere.com"
    smtp_server = "mail.nowhere.com"
    web_logo = "needtosetinconfig"
    web_logosize = list([ 100, 100 ]) # This is width and height
    logfilesize = list([ 10000, 9 ]) # 10000 is 10k, 9 is 10 total copies
    support_team = "Company"
    config_error = True
    data_folders = list([ "data", "incoming", "processing", "completed", 1000000, 6 ]) # 1MB upload default, 6 org decimal places
    decryption_key = "notsetyet" # Used to decrypt any stored passwords

    # Defaults
    config_values = dict({'error': config_error, 'email': support_email, 'smtp': smtp_server, 'logfilesize': logfilesize,
     'logo': web_logo, 'logosize':  web_logosize, 'team': support_team, 'decryptionkey': decryption_key})

    # Read configuration file
    try:
        with open(config_file, 'r') as config_contents:
            cfg_data = json.loads(config_contents.read())

            # Read log file settings
            logfilesize.clear()
            logfilesize.append(cfg_data['logfilesize'][0])
            logfilesize.append(cfg_data['logfilesize'][1])

            # Read logo settings
            web_logo = cfg_data['logo']
            web_logosize.clear()
            web_logosize.append(cfg_data['logosize'][0])
            web_logosize.append(cfg_data['logosize'][1])

            # Read team description
            support_team = cfg_data['team']

            # Read support email address
            support_email = cfg_data['email']

            # Read SMTP server name
            smtp_server = cfg_data['smtp']

            # Configuration values
            config_error = False
            config_values = dict({'error': config_error, 'email': support_email, 'smtp': smtp_server, 'logfilesize': logfilesize,
             'logo': web_logo, 'logosize':  web_logosize, 'team': support_team})

    except IOError as file_error:
        print('Problem opening ' + config_file + ', error received is: ' + str(file_error))
        config_error = True

    return config_values

# Read users
def read_users(users_file):
    # Users list
    user_accounts = list([])
    # Read users file
    try:
        with open(users_file, 'r') as users_contents:
            users_data = json.loads(users_contents.read())

            # Read users
            for dataread_user in users_data['users']:
                user_accounts.append(dataread_user)

    except IOError as file_error:
        print('Problem opening ' + users_file + ', error received is: ' + str(file_error))

    return user_accounts

# Backup users
def backup_users(users_file):
    users = read_users(users_file)
    datetime = time.strftime("%Y-%m-%d_%H%M%S")
    try:
        with open(users_file + '_' + datetime + '_old.cfg', 'w') as users_contents:
            json.dump(users, users_contents, indent=4)
        return True
    except IOError:
        print('Problem creating ' + users_file + '_' + datetime + ', check to make sure your filesystem is not write protected.')
        return False

# New user
def new_user(users_file, newuser):
    users = read_users(users_file)
    users.append(newuser)
    usersupdate_content = {'users': users}
    try:
        with open(users_file, 'w') as users_contents:
            json.dump(usersupdate_content, users_contents, indent=4)
        return True
    except IOError:
        print('Problem creating ' + users_file + ', check to make sure your filesystem is not write protected.')
        return False

# Modify user
def modify_user(users_file, moduser):
    users = read_users(users_file)
    # Replace updated login
    dataupdate_jsonedit = []
    for dataupdate_existinglogin in users:
        # Add all logins until we come to the one that was modified
        if int(dataupdate_existinglogin['_index']) < int(moduser['_index']):
            dataupdate_jsonedit.append(dataupdate_existinglogin)
        # This is the modified login
        elif int(dataupdate_existinglogin['_index']) == int(moduser['_index']):
            dataupdate_jsonedit.append(moduser)
        # This is after the modified login
        # If we already found the modified login, save the rest like normal
        else:
            dataupdate_jsonedit.append(dataupdate_existinglogin)
    # Assemble updated users file
    usersupdate_content = {'users': dataupdate_jsonedit}
    try:
        with open(users_file, 'w') as users_contents:
            json.dump(usersupdate_content, users_contents, indent=4)
        return True
    except IOError:
        print('Problem creating ' + users_file + ', check to make sure your filesystem is not write protected.')
        return False

# Read organizations
def read_orgs(orgs_file):
    # Organizations list
    org_details = list([])
    # Read organization file
    try:
        with open(orgs_file, 'r') as orgs_contents:
            orgs_data = json.loads(orgs_contents.read())

            # Read organizations
            for dataread_org in orgs_data['orgs']:
                org_details.append(dataread_org)

    except IOError as file_error:
        print('Problem opening ' + orgs_file + ', error received is: ' + str(file_error))

    return org_details

# Logger setup
def setup_log(log_file, log_size, log_backups):
    # Start logger with desired output level
    logger = logging.getLogger('Logger')
    logger.setLevel(logging.INFO)
    # Setup log handler to manage size and total copies
    handler = logging.handlers.RotatingFileHandler(log_file, maxBytes=log_size, backupCount=log_backups)
    # Setup formatter to prefix each entry with date/time 
    formatter = logging.Formatter("%(asctime)s - %(message)s")
    # Add formatter
    handler.setFormatter(formatter)
    # Add handler
    logger.addHandler(handler)

    return logger

# Get command line arguments
if __name__ == "__main__":
    if (len(sys.argv) == 3) and ((sys.argv[1] == "--cfg") or (sys.argv[1] == "--users")):
        if sys.argv[1] == "--cfg":
            config_file_name = sys.argv[2]
            print ("Config file:", config_file_name)
            configuration = dict([])
            configuration = read_cfg(config_file_name)
            print ("Returned configuration: " + str(configuration))
        if sys.argv[1] == "--users":
            users_file_name = sys.argv[2]
            print ("Users file:", users_file_name)
            users = list({})
            users = read_users(users_file_name)
            print ("Returned users: " + str(users))
    else:
        print ("Syntax:")
        print ("        " + sys.argv[0] + " --cfg 'config file name'")
        print ("        " + sys.argv[0] + " --users 'users file name'")