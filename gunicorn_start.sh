#!/bin/bash

# Name of the application
NAME="matchminer_patient_app"
# Directory where the application code is located
FLASKDIR=/path/to/your/matchminer-patient
# User and group to run the application as
USER=your_linux_user
GROUP=your_linux_group
# Number of Gunicorn worker processes
NUM_WORKERS=3
# The host and port Gunicorn will bind to (should be a local socket in production)
# We use a Unix socket for secure and fast communication with Nginx.
BIND_SOCK=unix:$FLASKDIR/gunicorn.sock
# The WSGI module to run
WSGI_MODULE=wsgi:app

echo "Starting $NAME as `whoami`"

# Activate the virtual environment
cd $FLASKDIR
source venv/bin/activate

# Set environment variables if you are using a .env file
export $(cat .env | xargs)

# Create the run directory if it doesn't exist
RUNDIR=$(dirname $BIND_SOCK)
test -d $RUNDIR || mkdir -p $RUNDIR

# Start Gunicorn
exec gunicorn ${WSGI_MODULE} \
  --name $NAME \
  --workers $NUM_WORKERS \
  --user=$USER --group=$GROUP \
  --bind=$BIND_SOCK \
  --log-level=info \
  --log-file=- 