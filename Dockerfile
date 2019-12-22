#Multistage build.  Keep git out of the final container
FROM python:2.7-alpine AS builder

RUN apk add --no-cache git
WORKDIR /app
RUN git clone --single-branch --branch repeater https://github.com/mgroseman/io-client-python.git

### Final image
FROM python:2.7-alpine

COPY --from=builder /app /app
RUN cd /app/io-client-python && python setup.py install
COPY . /app/mqtt-repeater
WORKDIR /app/mqtt-repeater
CMD ./mqtt_repeater.py
