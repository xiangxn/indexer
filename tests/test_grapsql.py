import sys
sys.path.append('../center')
import pytest
import json
import mongoengine
import graphene

parametrize = pytest.mark.parametrize


class TestGrapSQL(object):

    def test_filter_by_reference(self):
        from center.database.schema import Query

        query = '''
        {
            userOperationHistories(community: "0x6098d24e2b6C58ea726E6112763A5c8D4D97abe3") {
                edges {
                node {
                    id
                    community {
                    id
                    }
                    timestamp
                }
                }
            }
        }

        '''
        mongoengine.connect(db="donut_center", host="localhost", port=3001)

        schema = graphene.Schema(query=Query)
        result = schema.execute(query)
        print(json.dumps(result.data))
