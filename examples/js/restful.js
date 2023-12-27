var graphql = require("graphql-request");

const query = graphql.gql`{users{edges{node{id,createdAt,address}}}}`;

// graphql.request('http://127.0.0.1:8081/v1/common/search', query).then((data) => console.log(data.value));
graphql.request('http://104.152.208.28:8081/v1/common/search', query).then((data) => console.log(data.value));