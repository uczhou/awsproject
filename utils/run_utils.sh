#! /bin/bash

cd /home/ubuntu/utils

/home/ubuntu/.virtualenvs/mpcs/bin/python results_archive.py &

/home/ubuntu/.virtualenvs/mpcs/bin/python results_notify.py &

/home/ubuntu/.virtualenvs/mpcs/bin/python archive_restore.py &