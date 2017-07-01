Development Notes
=================

Environment Setup
-----------------
.. code-block:: sh

   python3 -mvenv env
   env/bin/pip install -r requires/development.txt
   ./bootstrap

Running Tests
-------------
.. code-block:: sh

   env/bin/nosetests

Building Docs
-------------
.. code-block:: sh

   env/bin/python setup.py build_sphinx
