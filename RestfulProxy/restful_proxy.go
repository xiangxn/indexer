package main

import (
	"context"
	"flag"
	"fmt"
	"io/ioutil"
	"net/http"

	"github.com/buger/jsonparser"
	"github.com/golang/glog"
	"github.com/grpc-ecosystem/grpc-gateway/v2/runtime"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"

	gw "donutins" // Update
)

var (
	config, _       = ioutil.ReadFile("./config.json")
	grpc_port, _    = jsonparser.GetInt(config, "grpc_port")
	grpc_host, _    = jsonparser.GetString(config, "grpc_host")
	restful_port, _ = jsonparser.GetInt(config, "restful_port")
)

var (
	// command-line options:
	// gRPC server endpoint
	grpcServerEndpoint = flag.String("donut-endpoint", fmt.Sprintf("%s:%d", grpc_host, grpc_port), "gRPC server endpoint")
)

func CustomMatcher(key string) (string, bool) {
	switch key {
	case "Token":
		return key, true
	default:
		return runtime.DefaultHeaderMatcher(key)
	}
}

func run() error {
	ctx := context.Background()
	ctx, cancel := context.WithCancel(ctx)
	defer cancel()

	// Register gRPC server endpoint
	// Note: Make sure the gRPC server is running properly and accessible
	mux := runtime.NewServeMux(runtime.WithIncomingHeaderMatcher(CustomMatcher))
	opts := []grpc.DialOption{grpc.WithTransportCredentials(insecure.NewCredentials())}
	err := gw.RegisterDonutHandlerFromEndpoint(ctx, mux, *grpcServerEndpoint, opts)
	if err != nil {
		return err
	}

	port := fmt.Sprintf(":%d", restful_port)
	fmt.Println("start " + port)
	// Start HTTP server (and proxy calls to gRPC server endpoint)
	return http.ListenAndServe(port, mux)
}

func main() {
	flag.Parse()
	defer glog.Flush()

	if err := run(); err != nil {
		glog.Fatal(err)
	}
}
