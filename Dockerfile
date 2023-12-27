FROM golang:1.18

COPY . /data-center
WORKDIR /data-center

ENV PATH="/usr/local/go/bin:/root/go/bin:${PATH}"
ENV GOROOT="/usr/local/go"
ENV PROTOBUF="/usr/include"

# install protobuf+python3
RUN apt-get update \
    && apt-get install -y git libprotobuf-dev protobuf-compiler python3 python3-pip \
    && pip3 install -r requirements-dev.txt \
    && rm -rf /data-center/*