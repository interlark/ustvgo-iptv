FROM python:3.8-slim-buster

RUN pip3 install ustvgo-iptv

CMD [ "ustvgo-iptv" ]
