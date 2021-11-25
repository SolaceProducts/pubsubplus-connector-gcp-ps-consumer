# Copyright 2019 Google, LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# [START cloudrun_pubsub_server_setup]
# [START run_pubsub_server_setup]
import http.client
import base64
import os
import json

from flask import Flask, request


app = Flask(__name__)
# [END run_pubsub_server_setup]
# [END cloudrun_pubsub_server_setup]


# [START cloudrun_pubsub_handler]
# [START run_pubsub_handler]
@app.route("/", methods=["POST"])
def index():
    envelope = request.get_json()
    if not envelope:
        msg = "no Pub/Sub message received"
        print(f"error: {msg}")
        return f"Bad Request: {msg}", 400

    if not isinstance(envelope, dict) or "message" not in envelope:
        msg = "invalid Pub/Sub message format"
        print(f"error: {msg}")
        return f"Bad Request: {msg}", 400

    pubsub_message = envelope["message"]

    payload = "World"
    if isinstance(pubsub_message, dict) and "data" in pubsub_message:
        payload = base64.b64decode(pubsub_message["data"]).decode("utf-8").strip()

    print(f"Hello {payload}!")
    print(envelope)
    print(request)

    # Send request to Solace PubSub+

    def get_cred_config() -> dict[str, str]:
        secret = os.environ.get("SOLACE_BROKER_CONNECTION")
        print(secret)
        if secret:
            return secret

    secret = get_cred_config()
    print(secret)

    host = 'mr-1js1tiv17mwh.messaging.solace.cloud:9443'
    path = '/TOPIC/a/b/c'
    method = 'POST'
    username = 'solace-cloud-client'
    password = '1e5gblgcn8609aq8emq3q2id4l'
    auth = 'Basic ' + base64.b64encode(bytes(username + ':' + password, 'utf-8')).decode("ascii")
    headers = {
        "Authorization": auth
    }

    try:
        conn = http.client.HTTPSConnection(host, timeout=10 )
        conn.request("POST", path, payload, headers)
        response = conn.getresponse()
        # data = response.read().decode('utf-8')
        print(f"Got Solace response {response.status}")
        return ("", response.status)
    except:
        return ("Request Timeout", 408)
    finally:
        conn.close()




# [END run_pubsub_handler]
# [END cloudrun_pubsub_handler]


if __name__ == "__main__":
    PORT = int(os.getenv("PORT")) if os.getenv("PORT") else 8080

    # This is used when running locally. Gunicorn is used to run the
    # application on Cloud Run. See entrypoint in Dockerfile.
    app.run(host="127.0.0.1", port=PORT, debug=True)
