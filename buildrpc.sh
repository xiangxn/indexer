#!/bin/bash
if [ "$GOROOT" == "" ];then
    GOROOT="$HOME/go"
fi

if [ "$GOBIN" == "" ];then
    GOBIN="$HOME/go/bin"
fi

if [ "$PROTOBUF" == "" ];then
    PROTOBUF="/usr/local/include"
fi

echo "GOROOT: $GOROOT"
echo "GOBIN: $GOBIN"
echo "PROTOBUF: $PROTOBUF"

if [ ! -d "./RestfulProxy/donutins/" ];then
    mkdir ./RestfulProxy/donutins
fi

if [ ! -d "./include/" ];then
    mkdir ./include
fi

if [ ! -d "./center/rpc/" ];then
    mkdir -p ./center/rpc
fi

GOOGLE_API="./include/googleapis"
TOOL_FILE="$HOME/go/bin/protoc-gen-go"
echo "准备依赖文件......"

# https://goproxy.cn
# https://mirrors.aliyun.com/goproxy/
# https://goproxy.io

if [ ! -f $TOOL_FILE ];then
    go install github.com/grpc-ecosystem/grpc-gateway/v2/protoc-gen-grpc-gateway@latest
    go install github.com/grpc-ecosystem/grpc-gateway/v2/protoc-gen-openapiv2@latest
    go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
    go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest
fi

if [ ! -d $GOOGLE_API ];then
    pushd ./include
    git clone https://github.com/googleapis/googleapis.git
    popd -1
fi

echo "编译Python的GRPC......"

python3 -m grpc_tools.protoc -I=./center/protos \
    -I=$GOOGLE_API \
    -I=$PROTOBUF \
    --python_out=./center/rpc \
    --grpc_python_out=./center/rpc \
    ./center/protos/donut.proto \
    ./center/protos/donut_bot.proto \
    $PROTOBUF/google/protobuf/any.proto \
    $PROTOBUF/google/protobuf/wrappers.proto

echo "编译Go的GRPC......"

python3 -m grpc_tools.protoc -I ./center/protos \
    -I $GOOGLE_API \
    --go_out ./RestfulProxy/donutins --go_opt paths=source_relative \
    --go-grpc_out ./RestfulProxy/donutins --go-grpc_opt paths=source_relative \
    --grpc-gateway_out ./RestfulProxy/donutins \
    --grpc-gateway_opt logtostderr=true \
    --grpc-gateway_opt paths=source_relative \
    ./center/protos/donut.proto

pushd ./RestfulProxy
go mod tidy
echo "编译restful_proxy......"
go build -o ../restful_proxy  ./restful_proxy.go
popd -1

