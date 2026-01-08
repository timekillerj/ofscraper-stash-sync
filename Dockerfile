FROM python:3.14.2-slim

WORKDIR /app

COPY . /app

RUN pip install -r /app/requirements.txt

ENV PATH="$PATH:/app"

CMD ['/app/ofscraper-stash-sync', '-c', '/configs/config.ini']