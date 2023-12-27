var grpc = require("@grpc/grpc-js");
var services = require("./lib/donut_grpc_pb");
var message = require("./lib/donut_pb");
var any = require("./lib/google/protobuf/any_pb");
var wrappers=require("./lib/google/protobuf/wrappers_pb");

// var server = "localhost:50000"
var server ="104.152.208.28:50000"

var client = new services.DonutClient(server, grpc.credentials.createInsecure());

var request = new message.SearchRequest();

request.setQuery("{users{edges{node{id,createdAt,address}}}}");

client.search(request, (err, response) => {
    let code = response.getCode();
    let msg = response.getMsg();
    let data = response.getData();
    let value = data.unpack(wrappers.StringValue.deserializeBinary, data.getTypeName()).getValue();
    console.log(code, msg, value);

});

