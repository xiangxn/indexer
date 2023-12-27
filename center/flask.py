from flask import Flask
from flask_graphql import GraphQLView
import mongoengine
from center.database.schema import schema

app = Flask(__name__)
app.debug = True
app.add_url_rule('/graphql', view_func=GraphQLView.as_view(
    'graphql',
    schema=schema,
    graphiql=True,
))

# Optional, for adding batch query support (used in Apollo-Client)
# app.add_url_rule('/graphql/batch', view_func=GraphQLView.as_view('graphql', schema=schema, batch=True))


def flask_run(config):
    mongoengine.connect(db=config['mongo']['db'], host=config['mongo']['host'])
    mongoengine.connect(db=config['mongo']['log'], host=config['mongo']['host'], alias="event_logs")
    app.run(host="0.0.0.0", port=config['graphql_port'])
