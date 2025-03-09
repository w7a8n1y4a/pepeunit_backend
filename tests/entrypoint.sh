#!/bin/bash

rm -rf tmp/*.lock
gunicorn app.main:app -b 0.0.0.0:8555 --workers=4 -k uvicorn.workers.UvicornWorker --log-level=info