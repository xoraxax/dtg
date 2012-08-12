DTG - Done Tasks Gone
=====================

Done Tasks Gone is a task management web application with a IMAP server for mobile users.
The IMAP server is optional and does not need to run on the same machine as the DTG webserver.

License
-------

AGPL v3 or later.

Installation
------------

 1. Install OpenSSL for Python, virtualenv, mercurial, and pip::

      sudo apt-get install python-pip python-openssl python-virtualenv mercurial ssl-cert

 2. Checkout the development version of DTG::

      hg clone https://bitbucket.org/xoraxax/dtg

 3. Change to the newly created directory::

      cd dtg

 4. Create an SSL certificate if you want to use the IMAP server::

      make-ssl-cert /usr/share/ssl-cert/ssleay.cnf dtgcert

 5. Create a virtual environment::

      virtualenv env

 6. Active the environment::

      . env/bin/activate

 7. Install the dependencies into the virtual environment::

      pip install -r reqs.txt

 8. Edit the files start_dtg.sh and start_imapd.sh to suit your needs. Note that
    dtgimapd needs the URL of website serving DTG as a first parameter and the
    hostname of the machine as the second parameter. You can get information about
    options by calling dtg/main.py or dtgimapd/imapserver.py with -h

 9. Create a new user::

      PYTHONPATH=. python dtg/main.py --add-user=admin

 10. Run::

      ./start_dtg.sh &

 11. Optionally, run::

      ./start_imapd.sh

 12. That's it!


Using the IMAP server
---------------------

You can connect to the IMAP server and need to supply a username that includes
your workspace name::

  admin#My Workspace

will give you the `My Workspace` workspace under the `admin` account. The
password is the same as the one in the web application.  You get an IMAP folder
per context. If you send a mail, the subject line will be used to create a task
(the first string before the first colon will be used as the context name).
Note that you do not need to send the mail to a specific mail address: it works
by intercepting the mail that would go to the SENT IMAP folder.

