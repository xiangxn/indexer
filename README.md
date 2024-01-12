# inscription-indexer

1. [install golang](https://go.dev/doc/install)
2. Install protobuf
    ```
    brew install protobuf
    ```
    or
    ```
    apt install protobuf
    ```
3. [install mongodb](https://docs.mongodb.com/manual/installation/)
4. get code
    ```
    git clone https://github.com/donut33-social/inscription-indexer.git

    cd inscription-indexer
    ```
5. create python venv
    ```
    python3 -m venv venv
    source ./venv/bin/activate
    ```
6. Install dependencies
    ```
    pip3 install -r requirements-dev.txt
    ```
7. Generate rpc related files
    ```
    ./buildrpc.sh
    ```
8. Add and Change setting 'config.json'
    ```
    {
        "grpc_port": "50000",
        "contracts": {
            "IPShare": "0xd9210830afDEe5C8e5120dCC7a0C4Fa23997Ef25",
            "Donut": "0xe86305b400E69ffFb5CF8Fce2a90659174777A79",
            "TwitterInscription": "0x59102Eb8eE1296c2793e3F8E59197683963Bff69"
        },
        "sync_cfg": {
            "chain_api": "https://mainnet.base.org/",
            "start_block": 8168584,
            "max_chunk_scan_size": 5000,
            "max_request_retries": 30,
            "request_interval_sec": 0.5,
            "request_retry_seconds": 3.0,
            "realtime_scan_interval_sec": 5
        },
        "mongo": {
            "host": "localhost",
            "port": 3001,
            "db": "donut-inscription"
        }
    }
    ```
9. Start services

    a. Start a service that synchronizes blockchain event data
    ```
    paver run sync
    ```
    b. Start a service that tests GraphQL
    ```
    paver run flask
    ```
    c. Start grpc service
    ```
    paver run grpc
    ```
    d. Start grpc to restful conversion service
    ```
    ./restful_proxy
    ```

10. New data development steps

    a. Add abi to the `center/abi` directory, the file name should keep the defined contract name

    b. Add the storage entity class in `center/database/models.py`

    c. Add the graphql query definition in `center/database/schema.py`

    d. Add an event handler in the `center/eventhandler/` directory, the file name must start with "mapping", and the event handler name must start with "handle"

        E.g: `handleCommunityCreated`, Among them, `CommunityCreated` is the event name defined by the contract

    e. Add the proto protocol used by grpc in the `center/protos/donut.proto` file

    f. Run `./buildrpc.sh` to regenerate grpc program related files