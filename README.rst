searx-stats2
============

Statistics on `searx <https://asciimoo.github.io/searx/>`__ instances

Rewrite in Python of the `first version <https://github.com/pointhi/searx_stats>`__ (written in PHP)

WARNING : Work in progress.

Licence: GNU AGPLv3+

Installation
~~~~~~~~~~~~

-  use Python 3
-  clone source:
   ``git clone https://github.com/dalf/searx-stats2.git && cd searx-stats2``
-  install dependencies: ``pip install -r requirements.txt``
-  edit your
   `searx_stats2/settings.py <https://github.com/dalf/searx-stats2/blob/master/searx_stats2/settings.py>`__
   (set your ``SECRET_KEY``, and you may want to configure the database : https://docs.djangoproject.com/en/1.9/ref/settings/#databases )
-  run ``./manage.py migrate``
-  run ``python createsuperuser`` to create the superuser   
-  run ``./manage installtasks`` to setup a cron task to update the instances status. Alternative use ``./manage runtask update`` to update manually
-  run ``./manage runserver`` to start the application
