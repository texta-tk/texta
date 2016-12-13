.. _installation:

Installation
====================

.. note::

    Installation instructions are currently only for Debian based Linux distributions and tested on Ubuntu.

Downloading
-----------
    
TEXTA can be downloaded from Git repository. If you are missing *git*, you can download it with

.. code-block:: bash

    sudo apt-get -y install git
    

.. code-block:: bash

    git clone https://github.com/ekt68/texta.git


This generates a directory called *texta*, which contains the code base.
    
Resolving system-wide dependencies
----------------------------------
First lets update our aptitude's package list to get the most up-to-date software versions.

.. code-block:: bash

    sudo apt-get update
    
To compile some of the Python libraries, we need the Python header files, which are included in *python-dev* package.
    
.. code-block:: bash

    sudo apt-get -y install python-dev
    
For speeding up *gensim* and *scipy* modules, we have to download the following libraries.

.. code-block:: bash

    sudo apt-get -y install build-essential manpages-dev
    sudo apt-get install libblas-dev liblapack-dev libatlas-base-dev gfortran    

    
Resolving Python dependencies
-----------------------------

Since TEXTA is a Python application, it is highly recommended to use some sort of virtual Python environment.
Python stores its libraries globally and if some other Python applications are installed after TEXTA which use some of the same libraries, the
conflicting libraries may have changed to incompatible versions for TEXTA.
We recommend `Anaconda <https://www.continuum.io/downloads>`_ and it is referenced in the following code snippets
by *conda*. `Virtualenv <https://virtualenv.pypa.io/en/stable/>`_ is fine as well, but it doesn't have the libraries precompiled.

To create a new *Anaconda* environment called *texta* that uses Python 2.7, we issue the command

.. code-block:: bash

    conda create --name texta python=2.7
    
After we have created the environment, we have to activate it. Activating an environment changes the current terminal session's paths to switch
the original Python's executables to that of the isolated environment's.

.. code-block:: bash

    source activate texta
    
Now that we have our Python sandbox, we need to install the necessary dependencies. 

.. code-block:: bash

    pip install requests
    pip install numpy
    pip install cython #needed for fast gensim
    pip install scipy
    pip install sklearn
    pip install gensim
    pip install django
    pip install estnltk
    pip install pathlib
    

Elasticsearch
-------------

TEXTA uses `Elasticsearch <https://www.elastic.co/products/elasticsearch>`_ to store and query data. Elasticsearch allows full-text indexing,
meaning that not only can we query by specific columns, but we can also query documents using specific words or phrases in a column.

Elasticsearch behaves like a RESTful server, which accepts queries with JSON data. The server can either run locally or remotely.
Small datasets can be maintained on personal computer, while gigabytes of data should preferably be kept on a remote server. It is vital to
configure Elasticsearch's address if remote approach is used.

In Elasticsearch terminology a database is called an index and table is called either mapping or type.
    
Final touches
-------------

All that is left is to synchronize database state by running

.. code-block:: bash

    python manage.py makemigrations
    python manage.py migrate
    
and create a superuser for TEXTA to assign application permissions

.. code-block:: bash

    python manage.py createsuperuser
    

Running TEXTA
-------------

To start TEXTA on localhost:8000, it suffices to run

.. code-block:: bash

    python manage.py runserver
    
If we want to run on some other network interface or port, we can specify it via IP-port pair.

.. code-block:: bash

    python manage.py runserver localhost:80
    python manage.py runserver 0.0.0.0:8080
    