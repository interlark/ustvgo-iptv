FROM python:3.8-slim-buster

COPY channels.json setup.cfg setup.py __init__.py ustvgo_iptv.py ./
RUN pip install --no-cache-dir -U pip
RUN pip install --no-cache-dir -e .
ENTRYPOINT ["ustvgo-iptv"]
