DTG - Done Tasks Gone
=====================

Done Tasks Gone is a task management web application with an offline mode for mobile users.

License
-------

AGPL v3 or later.

Test site
---------

Go to `tasks.alexanderweb.de <http://tasks.alexanderweb.de>`_ to try DTG. The username and the
password are both `test`.

Installation
------------

 1. Install Python 2.7, virtualenv, mercurial, and pip::

      sudo apt-get install python-pip python-virtualenv mercurial python-dev

 2. Checkout the development version of DTG::

      hg clone https://bitbucket.org/xoraxax/dtg

 3. Change to the newly created directory::

      cd dtg

 4. Create a virtual environment using Python 2.7::

      virtualenv --system-site-packages env

 5. Active the environment::

      . env/bin/activate

 6. Install the dependencies into the virtual environment::

      pip install -r reqs.txt

 7. Edit the file start_dtg.sh to suit your needs. You can get information about
    options by calling::

      PYTHONPATH=. python2 dtg/main.py -h

 8. Create a new user::

      PYTHONPATH=. python2 dtg/main.py --add-user=admin

 9. Run::

      ./start_dtg.sh &

 10. That's it!

