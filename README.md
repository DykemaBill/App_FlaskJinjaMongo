# App_FlaskJinjaMongo
Application build with Python Flask/Jinja2 and MongoDB

# To-Do's for the author
-   Build a simple version of the application - DONE
-   If no user exists, prompt user to create one at login - DONE
-   Implement record deleting - DONE
-   Installation directions in README - DONE
-   Active Directory authenication option - 
-   Security testing (orgs, admin, orgadmin) - 
-   CSS class renames and remove unused - 
-   Refactor primary Flask entry code file - 
-   Document handling with records - 
-   User management page - 
-   User forgot password option - 

# Bugs that need to be fixed
-   Password hash not working - FIXED

# Future ideas
-   If app starts without database connection, have a Flask auto-reload on a timer while still displaying error page

# Development Startup (Windows, macOS, Linux)

0.  For each option, first do this (requires you have Docker Desktop installed and running):

    ```
    cd [parent folder you want to install under]
    git clone https://github.com/DykemaBill/App_FlaskJinjaMongo.git
    cd App_FlaskJinjaMongo
    pipenv shell
    docker compose up -d
    pip install -r requirements.txt
    ```

1.  Flask standard option number 1:

    ```
    flask run
    ```

2.  Flask standard option number 2:

    ```
    python app_fjm.py
    ```

2.  Wrapper that NGINX/uWSGI will use if you later follow the below production install:

    ```
    python wsgi.py
    ```

# Production Install and Setup (Linux)

1.  MongoDB
    1.  Have your MongoDB server and/or Docker container running in a production location
    2.  Use a login and password different than what is supplied in the docker-compose.yml file
    3.  You will need to change the ```"db_conn"``` configuration in the ```config/settings.cfg``` file to match your MongoDB installation after installing App_FlaskJinjaMongo
1.  Python / Git
    1.  Install Python 3.10 or newer if not already installed
        1.  You will need to modify the repo ```Pipfile``` to match your installed version after your clone it
    2.  Install Python pipenv:

        ```
        pip3 install pipenv
        ```

    3.  Install the latest version of Git if not already installed
2.  uWSGI
    1.  Add an account to the system for this application to run under
        1.  Recommend creating a user called ```flask``` and using an existing group such as ```www-data```
    2.  Create a folder where uWSGI can send logs:

        ```
        mkdir /var/log/uwsgi
        chown -R flask:www-data /var/log/uwsgi
        ```

        1.  If you use a different log location, you will need to modify the repo ```wsgi.ini``` file
    3.  Install uWSGI:

        ```
        pip3 install uwsgi
        ```

4.  Flask application
    1.  Install this application on an external (non-root) filesystem:

        ```
        mkdir /[mountpath]/app
        cd /[mountpath]/app
        git clone https://github.com/DykemaBill/App_FlaskJinjaMongo.git
        chown -R flask:www-data /[mountpath]/app/App_FlaskJinjaMongo
        su - flask
        cd /[mountpath]/app/App_FlaskJinjaMongo
        pipenv shell
        pip3 install -r requirements.txt
        deactivate
        exit
        ```

    2.  Setup a service (showing configuration for Ubuntu)
        1.  Create a configuration file

            ```
            touch /etc/systemd/system/App_FlaskJinjaMongo.service
            ```

        2.  Put the following in this file (replace mountpath and mypipenvlocation)

            ```
            [Unit]
            Description=uWSGI instance to serve App_FlaskJinjaMongo
            After=network.target

            [Service]
            User=flask
            Group=www-data
            WorkingDirectory=/mountpath/app/App_FlaskJinjaMongo
            Environment="PATH=/var/app/.local/share/virtualenvs/mypipenvlocation/bin"
            ExecStart=/var/app/.local/share/virtualenvs/mypipenvlocation/bin/uwsgi --ini wsgi.ini

            [Install]
            WantedBy=multi-user.target
            ```

5.  NGINX
    1.  Setup a site
        1.  Create a configuration file

            ```
            touch /etc/nginx/sites-available/App_FlaskJinjaMongo
            ln -s /etc/nginx/sites-available/App_FlaskJinjaMongo /etc/nginx/sites-enabled
            ```

        2.  Put the following in this file (replace flask.myservername.mytld, cert file locations and mountpath)

            ```
            server {
                listen 80;
                server_name flask.myservername.mytld;
                return 301 https://$server_name$request_uri;
            }

            server {
                listen 443 ssl;
                server_name flask.myservername.mytld;

                ssl_certificate /sslcertlocation/certfile.crt; 
                ssl_certificate_key /sslcertlocation/certkey.key;

                location / {
                    include uwsgi_params;
                    uwsgi_pass unix:/mountpath/app/App_FlaskJinjaMongo/wsgi.sock;
                }
            }
            ```

    2.  Set NGINX and Flask startup to be active (showing configuration for Ubuntu)

        ```
        systemctl start App_FlaskJinjaMongo
        systemctl enable App_FlaskJinjaMongo
        systemctl status App_FlaskJinjaMongo
        nginx -t
        systemctl restart nginx
        ufw allow 'Nginx Full'
        ```
