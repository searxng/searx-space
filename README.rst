searx-stats2
============


Installation
~~~~~~~~~~~~

-  use Python 3
-  clone source:
   ``git clone https://github.com/dalf/searx-stats2.git && cd searx-stats2``
-  install dependencies: ``pip install requirements.txt``
-  edit your
   `searx_stats2/settings.py <https://github.com/dalf/searx-stats2/blob/master/searx_stats2/settings.py>`__
   (set your ``SECRET_KEY``!)
-  run ``./manage installtasks`` to setup a cron task to update the instances status. Alternative use ``./manage runtask update`` to update manually
-  run ``./manage runserver`` to start the application

