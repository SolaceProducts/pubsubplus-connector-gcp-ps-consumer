# gcp-pubsub-to-solace-pubsubplus for GCP Run sample
#
# Copyright 2021 Solace Corporation. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Module contains a sample implementation of a connctor that forwards messages form GCP Pub/Sub to Solace PubSub+

# Adjust to set PubSub+ broker destination
SOLACE_DESTINATION_TYPE = "TOPIC"    # Options are TOPIC or QUEUE
SOLACE_DESTINATION_NAME = "gcp/pubsub"  # The broker destination topic or queue name (queue must exist on the broker)
SOLACE_TOPIC_APPEND_SUBSCRIPTIONNAME = True # Append subscription name to above destination, e.g.: gcp/pubsub/my-subscription

import http.client
import requests
import base64
import os
import json
from google.api_core.datetime_helpers import to_milliseconds, from_rfc3339
from flask import Flask, request
import ssl

app = Flask(__name__)
# Handle trigger from Pub/Sub subscription
@app.route("/", methods=["POST"])
def index():
  #
  # Process and verify Pub/Sub message
  #

  # Verify Pub/Sub message contents
  #print(f"Received request: {request}")
  envelope = request.get_json()
  if not envelope:
    msg = "no Pub/Sub message received"
    print(f"error: {msg}")
    return f"Bad Request: {msg}", 400
  #print(f"Envelope: {envelope}")

  if not isinstance(envelope, dict) or "message" not in envelope:
    msg = "invalid Pub/Sub message format"
    print(f"error: {msg}")
    return f"Bad Request: {msg}", 400
  pubsub_message = envelope["message"]

  if not isinstance(pubsub_message, dict) or "data" not in pubsub_message:
    msg = "no payload in Pub/Sub message"
    print(f"error: {msg}")
    return f"Bad Request: {msg}", 400
  payload = base64.b64decode(pubsub_message["data"]).decode("utf-8").strip()
  print(f"Decoded Pub/Sub payload: {payload}")

  #
  # Format and forward message to Solace PubSub+
  #

  # Header settings. Refer to https://docs.solace.com/RESTMessagingPrtl/Solace-REST-Message-Encoding.htm
  # In this example following properties don't take values from the Pub/Sub message:
  SOLACE_CLIENT_NAME = "TestGooglePubSubClient" # This is actually not a message property but identifies the REST client
  SOLACE_TIME_TO_LIVE_MS = "604800000"  # Represents 1 week
  SOLACE_DMQ_ELIGIBLE = "true"          # Relevant to Queue destinations
  SOLACE_DELIVERY_MODE = "Persistent"   # Always recommended otherwise PubSub+ REST request is returned with 200 result before the message is persisted
  try:
    content_type = "application/octet-stream" if (pubsub_message["attributes"]["googclient_schemaencoding"] == "BINARY") else request.headers.get('Content-Type')
    content_encoding = "UTF-8" if (request.headers.get('Content-Encoding') == None) else request.headers.get('Content-Encoding')
    subscription = envelope["subscription"]
    project = subscription.split("/")[1]
    subscription_name = subscription.split("/")[3]
    headers = {
      #"Authorization": auth,
      "Solace-Client-Name": SOLACE_CLIENT_NAME,
      "Solace-Message-ID": pubsub_message["messageId"],
      "Solace-Delivery-Mode": SOLACE_DELIVERY_MODE,
      "Solace-Time-To-Live-In-ms": SOLACE_TIME_TO_LIVE_MS,
      "Solace-DMQ-Eligible": SOLACE_DMQ_ELIGIBLE,
      "Solace-Timestamp": to_milliseconds(from_rfc3339(pubsub_message["publishTime"])),
      "Content-Type": content_type,
      "Content-Encoding": content_encoding,
      "Solace-User-Property-google_pubsub_subscription": subscription,
      "Solace-User-Property-google_pubsub_project": project,
      "Solace-User-Property-google_pubsub_subscriptionname": subscription_name
    }
    # Additional headers
    if "orderingKey" in pubsub_message:
      headers["Solace-User-Property-orderingKey"] = pubsub_message["orderingKey"]
    attributes = pubsub_message["attributes"]
    for key in attributes:
        headers[f"Solace-User-Property-{key}"] = attributes[key]
  except:
    msg = "Error parsing Pub/Sub headers"
    print(f"error: {msg}")
    return f"Bad Request: {msg}", 400

  # Determine PubSub+ event broker connection details
  # Making use of env set from GCP Secret
  # SOLACE_BROKER_CONNECTION env example: {"Host":"https://myhost:9443","AuthScheme":"basic","Username":"myuser","Password":"mypass"}
  def get_conn_config() -> dict[str, str]:
    secret = os.environ.get("SOLACE_BROKER_CONNECTION")
    return secret
  try:
    mysecret = get_conn_config()
    pubsubplus_connection = json.loads(mysecret)
    host = pubsubplus_connection["Host"]
    if "https://" in host:    # This sample requires TLS (HTTPS) used but removes https:// from the host if present
      host = host.split("https://")[1]
    context = ssl.SSLContext(ssl.PROTOCOL_SSLv23) # Create SSL context for all cases
    # Prepare authentication info depending on the auth scheme
    auth_scheme = pubsubplus_connection["AuthScheme"]
    print(f"Determined {auth_scheme} authentication scheme")
    if auth_scheme == "basic":
      username = pubsubplus_connection["Username"]
      password = pubsubplus_connection["Password"]
      # Add Authorization header
      headers["Authorization"] = "Basic " + base64.b64encode(bytes(username + ":" + password, "utf-8")).decode("ascii")
    elif auth_scheme == "client-cert":
      client_cert = pubsubplus_connection["ClientCert"]
      client_key = pubsubplus_connection["ClientKey"]
      # Define the client certificate settings for https connection
      open("client.crt", "w").write(client_cert)  # must save, there is no way to pass a string to load_cert_chain() below
      open("client.key", "w").write(client_key)
      context.load_cert_chain(certfile="client.crt", keyfile="client.key")
    elif auth_scheme == "oauth":
      # Get id-token from the Cloud Run metadata server
      audience = pubsubplus_connection["Audience"]
      oauth_token = requests.get(f"http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity?audience={audience}",
                    headers={'Metadata-Flavor': 'Google'}).text
      # Add Authorization header
      headers["Authorization"] = f"Bearer {oauth_token}"
    else:
      print(f"Found unsupported authentication scheme: {auth_scheme}")
  except:
    msg = "Error parsing PubSub+ event broker connection details from SOLACE_BROKER_CONNECTION env variable"
    print(f"error: {msg}")
    return f"Service Unavailable: {msg}", 503

  # Send REST message to PubSub+ event broker, get response and return that
  try:
    # First determine destination
    path = f"/{SOLACE_DESTINATION_TYPE}/{SOLACE_DESTINATION_NAME}"
    if SOLACE_TOPIC_APPEND_SUBSCRIPTIONNAME:
      path += f"/{subscription_name}"         # Add subscription_name to the topic
    conn = http.client.HTTPSConnection(host, timeout=10, context = context )
    print(f"Sending message to {path}")
    conn.request("POST", path, payload, headers)
    response = conn.getresponse()
    print(f"Got Solace PubSub+ response {response.status}")
    return ("", response.status)
  except:
    msg = "Error sending message to PubSub+ event event broker REST API"
    print(f"error: {msg}")
    return f"Unexpected error: {msg}", 400
  finally:
    conn.close()

if __name__ == "__main__":
  PORT = int(os.getenv("PORT")) if os.getenv("PORT") else 8080

  # This is used when running locally. Gunicorn is used to run the
  # application on Cloud Run. See entrypoint in Dockerfile.
  #
  # Sample REST test message:
  # POST http://127.0.0.1:8080
  # {
  #   "message": {
  #     "attributes": {
  #       "AA": "BB",
  #       "CC": "DD",
  #       "EE": "FF",
  #       "googclient_schemaencoding": "JSON"
  #     },
  #     "data": "eyJTdHJpbmdGaWVsZCI6ICJTaGluZSBUZXN0IiwgIkZsb2F0RmllbGQiOiAyLjE0MTUsICJCb29sZWFuRmllbGQiOiBmYWxzZX0=",
  #     "messageId": "3470081450253332",
  #     "message_id": "3470081450253332",
  #     "orderingKey": "QWERTY",
  #     "publishTime": "2021-12-02T20:20:53.37Z",
  #     "publish_time": "2021-12-02T20:20:53.37Z"
  #   },
  #   "subscription": "projects/my-gcp-project-1234/subscriptions/my-topic-run-sub"
  # }
  #
  app.run(host="127.0.0.1", port=PORT, debug=True)

