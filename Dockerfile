FROM python:3.9

WORKDIR /scoreboard
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY ./matrix ./matrix
WORKDIR /scoreboard/matrix/
RUN make build-python PYTHON="$(command -v python3)" && make install-python PYTHON="$(command -v python3)"

WORKDIR /scoreboard
COPY ./assets ./assets
COPY ./cache ./cache
COPY scoreboard.py .

CMD ["python", "scoreboard.py"]