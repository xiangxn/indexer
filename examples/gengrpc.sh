#!/bin/bash

GOOGLE_API="../include/googleapis"

if [ ! -d "./js/lib/" ];then
    mkdir -p ./js/lib
fi

./node_modules/.bin/grpc_tools_node_protoc \
    --js_out=import_style=commonjs,binary:./js/lib \
    --grpc_out=grpc_js:./js/lib \
    --plugin=protoc-gen-grpc=./node_modules/.bin/grpc_tools_node_protoc_plugin \
    -I=../center/protos \
    -I=$GOOGLE_API \
    -I=$PROTOBUF \
    ../center/protos/donut.proto \
    $PROTOBUF/google/protobuf/any.proto \
    $PROTOBUF/google/protobuf/wrappers.proto \
    $GOOGLE_API/google/api/annotations.proto \
    $GOOGLE_API/google/api/http.proto