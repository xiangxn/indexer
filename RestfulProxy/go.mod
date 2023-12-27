module restful_proxy

go 1.17

require (
	github.com/buger/jsonparser v1.1.1
	github.com/golang/glog v1.0.0
	github.com/grpc-ecosystem/grpc-gateway/v2 v2.8.0
	google.golang.org/grpc v1.45.0
	donut v0.0.1
)

require (
	github.com/golang/protobuf v1.5.2 // indirect
	golang.org/x/net v0.0.0-20220127200216-cd36cc0744dd // indirect
	golang.org/x/sys v0.0.0-20211216021012-1d35b9e2eb4e // indirect
	golang.org/x/text v0.3.7 // indirect
	google.golang.org/genproto v0.0.0-20220314164441-57ef72a4c106 // indirect
	google.golang.org/protobuf v1.27.1 // indirect
)

replace donut v0.0.1 => ./donut
