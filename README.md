# GCP Pub/Sub to Solace PubSub+ REST-Based Event Publishing Guide

This guide provides an example use of the Solace PubSub+ REST API to stream events from Google Pub/Sub to Solace PubSub+.

Contents:
  * [Introduction](#introduction)
  * [Assumptions](#assumptions)
  * [Solution overview](#solution-overview)
  * [Components and interactions](#components-and-interactions)
    + [Connector service in GCP Cloud Run](#connector-service-in-gcp-cloud-run)
    + [GCP Pub/Sub Push delivery](#gcp-pub-sub-push-delivery)
    + [PubSub+ Event Broker REST API for inbound messaging](#pubsub-event-broker-rest-api-for-inbound-messaging)
    + [Pub/Sub message contents to PubSub+ message mapping](#pub-sub-message-contents-to-pubsub-message-mapping)
    + [Solace PubSub+ Connection details as GCP Secret](#solace-pubsub-connection-details-as-gcp-secret)
    + [PubSub+ REST API Client authentication](#pubsub-rest-api-client-authentication)
      - [Basic authentication](#basic-authentication)
      - [Client Certificate authentication](#client-certificate-authentication)
      - [OAuth 2.0 authentication](#oauth-20-authentication)
  * [Connector implementation](#connector-implementation)
  * [Quick Start](#quick-start)
  * [Troubleshooting](#troubleshooting)
    + [Cloud Run logs](#cloud-run-logs)
    + [Connector local testing](#connector-local-testing)
  * [Contributing](#contributing)
  * [Authors](#authors)
  * [License](#license)
  * [Resources](#resources)


## Introduction

From the [many options to connect](https://www.solace.dev/), a growing number of third party and cloud-native applications choose the Solace PubSub+ _REST API_ to stream events into the [PubSub+ event mesh](https://solace.com/solutions/initiative/event-mesh/). PubSub+ offers a flexible inbound REST interface and this guide shows how to make use of it at the example of publishing events from [Google Cloud Platform (GCP) Pub/Sub service](https://cloud.google.com/pubsub/docs/overview) to Solace PubSub+.

## Assumptions

This guide assumes basic understanding of:

* Solace PubSub+ [core messaging concepts](https://docs.solace.com/Basics/Core-Concepts.htm)
* Google Cloud Platform (GCP) [Cloud Pub/Sub](https://cloud.google.com/pubsub), [Cloud Run](https://cloud.google.com/run) and [Secret Manager](https://cloud.google.com/secret-manager) services
* Python programming language

## Solution overview

The following diagram depicts the main components of the solution.

![alt text](/images/architecture.png "Overview")

_Cloud Pub/Sub_, _Cloud Run_ and _Secret Manager_ are GCP services running in Google Cloud. _Solace PubSub+_ is shown here accessible through a public REST API service. PubSub+ may be a single event broker in HA or non-HA deployment or part of a larger PubSub+ Event Mesh.

Given an existing _Topic_ configured in Cloud Pub/Sub, a _Subscription_ is created to this topic which triggers the _Connector logic_ deployed as a service in Cloud Run. The Connector (1) checks the received Pub/Sub message, (2) gets _Solace PubSub+ broker connection details_ that have been configured as a secret in Secret Manager, (3) constructs an HTTP REST Request, message body and headers by mapping information from the received Pub/Sub message contents and taking into account the configured _Authentication method_ at PubSub+, and (4) sends the Request to PubSub+ using the REST API. The REST API Response indicates the success of getting the message into PubSub+.

Messages published to the Google Pub/Sub Topic will now be delivered to the PubSub+ Event Broker and available for consumption by any of its [supported APIs](https://solace.com/products/apis-protocols/) from any point of the Event Mesh.

## Components and interactions

### Connector service in GCP Cloud Run

The Connector service, deployed in Cloud Run, is implemented in Python v3.9 in this example. The same functionality can be adapted to any other programming language and used in Cloud Run. The Connector service could have also been deployed in Google Cloud Functions or App Engine as alternatives.

### GCP Pub/Sub Push delivery

The Google Pub/Sub Subscription is set to use [Push delivery](https://cloud.google.com/pubsub/docs/push) which immediately calls the REST trigger URL of the Connector service when a message becomes available that matches the subscription.

It is recommended to configure the Connector service configured to "Require Authentication" when deploying in Google Run. This will use OAuth 2.0 between Pub/Sub and Run with authentication/authorization automatically handled within GCP.

> Important: If "Require Authentication" is set, the Google IAM Service Account used by the Subscription must include the role of `Cloud Run Invoker`.

### PubSub+ Event Broker REST API for inbound messaging

PubSub+ REST API clients are called "REST publishing clients" or "REST producers". They [publish events into a PubSub+ event broker](https://docs.solace.com/Open-APIs-Protocols/Using-REST.htm) using the REST API. The ingested events will be converted to the same [internal message format](https://docs.solace.com/Basics/Message-What-Is.htm) as produced by any other API and can also be consumed by any other supported API.

> Note: this guide is using [REST messaging mode](https://docs.solace.com/Open-APIs-Protocols/REST-get-start.htm#When) of the Solace REST API.

The following REST to PubSub+ message conversions apply:

| REST protocol element | PubSub+ message | Additional Reference in Solace Documentation|
|----------|:-------------:|------:|
| Request `host:port` | Maps to the Solace `message-vpn` to be used for the message | [Solace PubSub+ Event Broker Message VPN Selection](https://docs.solace.com/RESTMessagingPrtl/Solace-Router-Interactions.htm#VPN-Selection)
| Request path: `/QUEUE/queue-name` or `/TOPIC/topic-string`| Solace Queue or Topic destination for the message | [REST HTTP Client to Solace Event Broker HTTP Server](https://docs.solace.com/RESTMessagingPrtl/Solace-REST-Message-Encoding.htm#Messagin) |
| Authorization  HTTP header | May support client authentication depending on the authentication scheme used | [Client Authentication](https://docs.solace.com/RESTMessagingPrtl/Solace-Router-Interactions.htm#Client)
| Content-Type HTTP header | Determines `text` or `binary` message type. Will become available as message attribute. | [HTTP Content-Type Mapping to Solace Message Types](https://docs.solace.com/RESTMessagingPrtl/Solace-REST-Message-Encoding.htm#_Ref393980206)
| Content-Encoding HTTP header | Must be `UTF-8` for `text` message type. Will become available as message attribute. | [HTTP Content-Type Mapping to Solace Message Types](https://docs.solace.com/RESTMessagingPrtl/Solace-REST-Message-Encoding.htm#_Ref393980206)
| Solace-specific HTTP headers | If a header is present, it can be used to set the corresponding PubSub+ message attribute or property | [Solace-Specific HTTP Headers](https://docs.solace.com/RESTMessagingPrtl/Solace-REST-Message-Encoding.htm#_Toc426703633)
| REST request body| The message body (application data) |
| REST HTTP response | For persistent messages, the 200 OK is returned after the message has been successfully stored on the event broker, otherwise an error code | [HTTP Responses from Event Broker to REST HTTP Clients](https://docs.solace.com/RESTMessagingPrtl/Solace-REST-Status-Codes.htm#Producer-on-Post)

### Pub/Sub message contents to PubSub+ message mapping

The received Pub/Sub message becomes available to the Connector service as a JSON object with following example message contents:

```json
{
  "message": {
    "attributes": {
      "AA": "BB",
      "CC": "DD",
      "EE": "FF",
      "googclient_schemaencoding": "JSON"
    },
    "data": "eyJTdHJpbmdGaWVsZCI6ICCb29s...ZWFuRmllbGQiOiBmYWxzZX0=",
    "messageId": "12345",
    "message_id": "12345",
    "orderingKey": "QWERTY",
    "publishTime": "2021-12-02T20:20:53.37Z",
    "publish_time": "2021-12-02T20:20:53.37Z"
  },
  "subscription": "projects/my-gcp-project-1234/subscriptions/my-topic-run-sub"
}
```
> Note: it seems that the Pub/Sub "topic" is not available from the JSON object, only the subscription.

The sample Connector will map information from this JSON object to PubSub+ REST API Request parameters (see previous section) so when ingested into PubSub+ the following PubSub+ message is created:

| Pub/Sub JSON field | PubSub+ message element |
|------------------|-------------|
| `message.attributes` | User Property Map of type String for each attribute present, example: `Key 'AA' (STRING) BB` |
| `message.data` |  Payload, base64-decoded from `message.data` |
| `message.messageId` | Message ID |
| `message.orderingKey` (if present) | User Property Map of type String |
| `message.publishTime` (RFC3339 encoded) | Timestamp (milliseconds since Epoch) |
| `subscription` | User Property Map of type String, key `google_pubsub_subscription` (full `subscription` string) |
|| Key `google_pubsub_project` (extracted from `projects` as part of `subscription`), example: `my-gcp-project-1234` |
|| Key `google_pubsub_subscriptionname` (extracted from `subscriptions` as part of `subscription`), example `my-topic-run-sub` |
|| Destination, created from subscription (in this example): PubSub+ topic `gcp/pubsub/my-topic-run-sub`

This an example of the resulting PubSub+ message dump:
```
^^^^^^^^^^^^^^^^^^ Start Message ^^^^^^^^^^^^^^^^^^^^^^^^^^^
Destination:                            Topic 'gcp/pubsub/my-topic-run-sub'
ApplicationMessageId:                   12345
HTTP Content Type:                      application/json
HTTP Content Encoding:                  UTF-8
SenderTimestamp:                        1638476453370 (Thu Dec 02 2021 15:20:53)
Class Of Service:                       COS_1
DeliveryMode:                           DIRECT
Message Id:                             1
TimeToLive:                             604800000
DMQ Eligible
User Property Map:
  Key 'google_pubsub_subscription' (STRING) projects/my-gcp-project-1234/subscriptions/my-topic-run-sub
  Key 'google_pubsub_project' (STRING) my-gcp-project-1234
  Key 'google_pubsub_subscriptionname' (STRING) my-topic-run-sub
  Key 'orderingKey' (STRING) QWERTY
  Key 'AA' (STRING) BB
  Key 'CC' (STRING) DD
  Key 'EE' (STRING) FF
  Key 'googclient_schemaencoding' (STRING) JSON
Binary Attachment:                      len=74
  7b 22 53 74 72 69 6e 67  46 69 65 6c 64 22 3a 20      {"String   Field":
  22 53 68 69 6e 65 20 54  65 73 74 22 2c 20 22 46      "Shine T   est", "F
  6c 6f 61 74 46 69 65 6c  64 22 3a 20 32 2e 31 34      loatFiel   d": 2.14
  31 35 2c 20 22 42 6f 6f  6c 65 61 6e 46 69 65 6c      15, "Boo   leanFiel
  64 22 3a 20 66 61 6c 73  65 7d                        d": fals   e}

^^^^^^^^^^^^^^^^^^ End Message ^^^^^^^^^^^^^^^^^^^^^^^^^^^
```

### Solace PubSub+ Connection details as GCP Secret

The Connector service in Cloud Run will access the PubSub+ event broker REST Messaging service connection details from a secret which is configured to be available through the `SOLACE_BROKER_CONNECTION` environment variable. This is recommended security best practice because connection details include credentials to authenticate the Connector service, as a REST client to PubSub+.

We will be using a simple flat JSON structure for the connection details:
```json
{
  "Host": "https://myhost:9443",
  "ServerCA": "-----BEGIN CERTIFICATE-----\n+etc\n+etc\n+etc\n-----END CERTIFICATE-----",
  "AuthScheme": "basic",
  :
  "field": "value",
  :
}
```
Where:
* `Host` provides the event broker REST service endpoint IP or FQDN including the port. Transport must be secure, using HTTPS
* Optional `ServerCA`: if provided it will be used to trust the specified Certificate Authority when connecting to the PubSub+ REST server, useful for self-signed server certificates
* `AuthScheme` defines the authentication scheme to use, for details see the [PubSub+ REST API Client authentication](#pubsub-rest-api-client-authentication) section below.
* Additional fields are specific to the `AuthScheme` used

Secrets can be set and updated through Secret Manager and the Connector service will use the "latest" Secret configured.

> Important: The Google IAM Service Account used by the Connector service in Cloud Run must include the role of `Secret Manager Secret Accessor`.

### PubSub+ REST API Client authentication

The following authentication schemes are supported:
* Basic
* Client Certificate
* OAuth 2.0 (PubSub+ release 9.13 and later)

The PubSub+ Event Broker must be configured to use one of the above options for REST API clients. For more details refer to the [Solace documentation about Client Authentication](https://docs.solace.com/Overviews/Client-Authentication-Overview.htm).

#### Basic authentication

This is based on a shared Username and Password that is configured in the broker. If using PubSub+ Cloud, it comes [preconfigured](https://docs.solace.com/Cloud/ght_select_correct_username_pw.htm) with Basic authentication. Refer to the Solace documentation for [advanced configuration](https://docs.solace.com/Configuring-and-Managing/Configuring-Client-Authentication.htm#Basic).

The connection secret shall contain following example information:
```json
{
  "Host": "https://myhost:9443",
  "AuthScheme": "basic",
  "Username": "myuser",
  "Password": "mypass"
}
```

Credentials are conveyed in the Authorization header of the REST request with 'username:password' encoded in base64, for example: `Authorization: Basic bXl1c2VyOm15cGFzcw==`

#### Client Certificate authentication

Here the Username is derived from the Common Name (CN) used in the TLS Client Certificate signed by a Certificate Authority that is also trusted by the broker. This Username must be also provisioned in the broker under Client Usernames and it shall be ensured that Client Certificate authentication is enabled.

Refer to a [step-by-step configuration guide for PubSub+ Cloud](https://docs.solace.com/Cloud/ght_client_certs.htm?Highlight=Client%20Certificate%20authentication) or the [detailed general configuration guide in Solace documentation](https://docs.solace.com/Configuring-and-Managing/Configuring-Client-Authentication.htm#Client-Cert). 

The connection secret shall contain the Client Certificate, along with the Client Key, as in the following sample. Notice that line breaks have been replaced by `\n`:
```json
{
  "Host": "https:/myhost:9443",
  "AuthScheme": "client-cert",
  "ClientCert": "-----BEGIN CERTIFICATE-----\n+etc\n+etc\n+etc\n-----END CERTIFICATE-----",
  "ClientKey": "-----BEGIN PRIVATE KEY------\n+etc\n+etc\n+etc\n-----END PRIVATE KEY-----"
}
```

Using Client Certificate authentication no Authorization header is required in the REST request, the `SSLContext` object in the code will take care of using the provided client secret and key at TLS connection setup.

#### OAuth 2.0 authentication

Since the Connector service runs in GCP, this example will conveniently use Google as OAuth provider. An identity token can be [easily obtained from the Cloud Run metadata server](https://cloud.google.com/run/docs/securing/service-identity#fetching_identity_and_access_tokens_using_the_metadata_server) which returns a JWT Id-token associated with the identity of the Google IAM Service Account used by the Connector service.

The OAuth token will be conveyed in the Authorization header of the REST request, for example:
```
Authorization: Bearer eyJhbGciOiifQ.2MDIyOTkyNzA5MDYwMjU0MzQ5In0.iNI3rPN5sxPOWkSCLJJ1AOhUKwWQyI
```
The connection secret shall be provided as follows:
```json
{
  "Host": "https://myhost:9443",
  "AuthScheme": "oauth",
  "Audience": "myaudience"
}
```
where Audience is the `OAuth Client ID` in the OAuth profile configured on the broker.

The generated Google JWT will contain:
```json
{
  "aud": "myaudience",
  "azp": "123456789",
  "email": "my-service-account-name@my-gcp-project-1234.iam.gserviceaccount.com",
  "email_verified": true,
  "exp": 1638980106,
  "iat": 1638976506,
  "iss": "https://accounts.google.com",
  "sub": "123456789"
}
```
The recommended broker configuration is:
* OAuth authentication enabled
* OAuth profile defined as follows:
* `OAuth Role` set as `Client`
* Ensure that `OAuth Client ID` and `Audience` in the connection secret above are the same
* `Issuer Identifier` set to `https://accounts.google.com`
* `Discovery Endpoint`set `https://accounts.google.com/.well-known/openid-configuration`
* `Username Claim Name`, that defines which claim from above JWT to be used to derive the Username. It can be set either to `azp` (meaning authorized party), the "OAuth 2 Client ID" associated to the Google service account used; or `email`, which is the Email setting of the same service account. The corresponding Client Username must then be configured in the broker
* `Required ID Token Type`is set to `JWT`; and
* Validate Type is enabled.

## Connector implementation

The Python code implementing the Connector is available from the GitHub repo of this project: [`python-samples\run\gcp-pubsub-to-solace-pubsubplus\main.py`](python-samples/run/gcp-pubsub-to-solace-pubsubplus/main.py)
</br>

The Connector is essentially a REST server leveraging the Python Flask web framework. The sample extends the [Google Run "Hello World" application](https://cloud.google.com/run/docs/quickstarts/build-and-deploy/python) with functionality to demonstrate how to process and forward Cloud Pub/Sub messages to Solace PubSub+.

Processing is straightforward:
1. Received request is expected as a Pub/Sub message and checked for valid JSON format and to include valid contents, then payload is extracted
1. Outgoing PubSub+ REST message HTTP headers are prepared by appropriate mapping from Pub/Sub message metadata - see section [Pub/Sub message contents to PubSub+ message mapping](#pubsub-message-contents-to-pubsub-message-mapping) in this guide.
1. The `get_conn_config()` function is defined to get and return the contents of the [connection secret](#solace-pubsub-connection-details-as-gcp-secret) injected as `SOLACE_BROKER_CONNECTION` environment variable
1. Authentication info is prepared depending on the authentication scheme obtained from the secret: for example an `Authentication` header may be added
1. An HTTPS connection is opened to Solace PubSub+ REST API and the prepared REST message including headers and payload is sent. This includes the request path which defines the destination of the PubSub+ message. This sample will send it to a PubSub+ event topic that includes the name of the PubSub subscription: `gcp/pubsub/{subscription}`
1. REST response from PubSub+ is obtained and returned as the overall result of the processing

## Quick Start

This example demonstrates an end-to-end scenario using Basic authentication.

**Step 1: Access to Google Cloud and PubSub+ services**

Get access to:
* Solace PubSub+ Event Broker, or [sign up for a free PubSub+ Cloud account](https://docs.solace.com/Cloud/ggs_login.htm). Note that the broker must have TLS configured (comes automatically when using ).
* GCP or [sign up for a free GCP account](https://console.cloud.google.com/freetrial/signup). Add appropriate permissions to your user if you encounter any restrictions to perform the next administration tasks. For development purposes the simplest option is if you user has account "Owner" or "Editor" rights.

[Enable GCP services](https://cloud.google.com/service-usage/docs/enable-disable), including "IAM", "Pub/Sub", "Secret Manger", "Cloud Run" and its dependency, the "Container Registry".

[Install Google Cloud SDK](https://cloud.google.com/sdk/docs/install#managing_an_installation) and [initialize it](https://cloud.google.com/sdk/docs/initializing).

**Step 2: Setup prerequisites**

Create followings in GCP:
* A [Pub/Sub topic](https://cloud.google.com/pubsub/docs/quickstart-console#create_a_topic) `my-topic` for which messages will be forwarded to Solace PubSub+.
* [IAM Service Account(s)](https://cloud.google.com/iam/docs/creating-managing-service-accounts#creating) - a common SA with both roles would suffice, separate SAs are recommended for better security:
  * SA to be used by Pub/Sub Subscription, with role `Cloud Run Invoker`; and
  * SA for the Connector service in Cloud Run, with role `Secret Manager Secret Accessor`

For simplicity we will only create one SA `pubsub-solace-producer-run-sa` in this quickstart with both roles.

> Note: it may take several minutes for the service accounts and roles to become active.

**Step 3: Create a Secret with PubSub+ connection details**

[Create a secret](https://cloud.google.com/secret-manager/docs/creating-and-accessing-secrets#create) in Secret Manager providing a name `my-solace-rest-connection-secret` and following value (replace Host, Username and Password with your [PubSub+ event broker's REST connection details](https://docs.solace.com/Cloud/ggs_create_first_service.htm#find-service-details)):
```json
{
  "Host": "https://myhost:9443",
  "AuthScheme": "basic",
  "Username": "myuser",
  "Password": "mypass"
}
```

Note: add `ServerCA` field if your server's certificate signing Certificate Authority is not a public provider, see [here](#solace-pubsub-connection-details-as-gcp-secret) for  more details.

**Step 4: Deploy the Connector in Cloud Run and link it to the Secret**

This step involves building a container image from the Connector source code, then deploying it into Cloud Run with the service account from Step 2 and the created secret from Step 3 assigned.

Run following in a shell, replacing `<PROJECT_ID>` and `<REGION>` from your GCP project.

```bash
# TODO: provide <PROJECT_ID> and <REGION>
export GOOGLE_CLOUD_PROJECT=<PROJECT_ID>
export GOOGLE_CLOUD_REGION=<REGION>
# Get source from the GitHub repo
git clone https://github.com/SolaceProducts/pubsubplus-connector-gcp-ps-consumer.git
cd pubsubplus-connector-gcp-ps-consumer/python-samples/run/gcp-pubsub-to-solace-pubsubplus/
# Submit a build to GCP Container Registry using Google Cloud Build
gcloud builds submit --tag gcr.io/${GOOGLE_CLOUD_PROJECT}/pubsub-solace-producer
# Deploy to Cloud Run
gcloud run deploy gcp-solace-connector-service \
    --image gcr.io/${GOOGLE_CLOUD_PROJECT}/pubsub-solace-producer \
    --no-allow-unauthenticated \
    --platform managed \
    --region ${GOOGLE_CLOUD_REGION} \
    --service-account=pubsub-solace-producer-run-sa@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com \
    --set-secrets=SOLACE_BROKER_CONNECTION=my-solace-rest-connection-secret:latest
```

Notice the Connector service trigger URL printed on the console after the deployment has been created.

**Step 5: Create a push Subscription to the Topic and link it to the Connector**

Follow the [instructions to create a Subscription](https://cloud.google.com/pubsub/docs/admin#creating_subscriptions), provide:
* Subscription ID (name), for example `my-topic-run-sub`
* Pub/Sub topic name `my-topic` which has been created in Step 2
* Select "Push" delivery type
* Set the Endpoint URL to the Connector service trigger URL from Step 4 (if needed you can look it up running `gcloud run services list`)
* Set checkbox to Enable Authentication
* Set the service account to `pubsub-solace-producer-run-sa`

With this the Subscription becomes active and the system is ready for testing!

**Step 6: Testing**

To watch messages arriving into PubSub+, use the "Try Me!" test service of the browser-based administration console to subscribe to messages to the `sinktest` topic. Behind the scenes, "Try Me!" uses the JavaScript WebSocket API.

   * If you are using PubSub+ Cloud for your messaging service, follow the instructions in [Trying Out Your Messaging Service](https://docs.solace.com/Solace-Cloud/ggs_tryme.htm). Hint: you may need to fix the "Establish Connection" details (Broker URL port shall be 443, manually copy Client Username and Password from the "Cluster Manager" "Connect" info)
   * If you are using an existing event broker, log into its [PubSub+ Manager admin console](//docs.solace.com/Solace-PubSub-Manager/PubSub-Manager-Overview.htm#mc-main-content) and follow the instructions in [How to Send and Receive Test Messages](https://docs.solace.com/Solace-PubSub-Manager/PubSub-Manager-Overview.htm#Test-Messages).

In both cases ensure to set the subscription to `gcp/pubsub/>`, which is a wildcard subscription to anything starting with `gcp/pubsub/` and shall catch what the connector is publishing to.

Then publish a message to Google Pub/Sub `my-topic`, from [GCP Console](https://cloud.google.com/pubsub/docs/publisher#publishing_messages) or using the command line:
```
gcloud pubsub topics publish my-topic \
    --message="Hello World!" --attribute=KEY1=VAL1,KEY2=VAL2
```
... and watch the message arriving in PubSub+




## Troubleshooting

### Cloud Run logs

In case of issues it is recommended to [check the logs in Cloud Run](https://cloud.google.com/run/docs/logging#viewing-logs-cloud-run). Ensure to refresh to see the latest logs. If there is a failure the Subscription will keep re-delivering messages and it may be necessary to go to the Pub/Sub Subscription details and purge messages to stop that.

For more details on the Connector processing change the level of logging to DEBUG in the Python script and redeploy:
```
logging.basicConfig(level=logging.DEBUG)
```

### Connector local testing

While the connector code  is ready for deployment into Cloud Run, it can be also tested by running locally in a Python 3.9 or later environment:

```bash
# From project root
cd python-samples/run/gcp-pubsub-to-solace-pubsubplus
SOLACE_BROKER_CONNECTION="{ "Host": "https://myhost:9443", "AuthScheme": "basic", "Username": "user", "Password": "pass" }" \
  bash -c "python main.py"
```
This will set the SOLACE_BROKER_CONNECTION environmant variable, which is otherwise taken from the GCP Secret, and start the Connector service listening at `127.0.0.1:8080`. (You may need to adjust above command to your OS environment)

Use a REST client tool such as Curl or Postman to emulate a trigger message from Pub/Sub and verify the request makes it to your PubSub+ event broker.

```
POST http://127.0.0.1:8080
{
  "message": {
    "attributes": {
      "AA": "BB",
      "CC": "DD",
      "EE": "FF",
      "googclient_schemaencoding": "JSON"
    },
    "data": "eyJTdHJpbmdGaWVsZCI6ICJTaGluZSBUZXN0IiwgIkZsb2F0RmllbGQiOiAyLjE0MTUsICJCb29sZWFuRmllbGQiOiBmYWxzZX0=",
    "messageId": "3470081450253332",
    "message_id": "3470081450253332",
    "orderingKey": "QWERTY",
    "publishTime": "2021-12-02T20:20:53.37Z",
    "publish_time": "2021-12-02T20:20:53.37Z"
  },
  "subscription": "projects/my-gcp-project-1234/subscriptions/my-topic-run-sub"
}
```


## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct, and the process for submitting pull requests to us.

## Authors

See the list of [contributors](../../graphs/contributors) who participated in this project.

## License

This project is licensed under the Apache License, Version 2.0. See the [LICENSE](LICENSE) file for details.

## Resources

For more information about Solace technology in general, please visit these resources:

- The [Solace Developers website](https://www.solace.dev/)
- [Solace Documentation](https://docs.solace.com/)
- Understanding [Solace technology]( https://solace.com/products/tech/)
- Ask the [Solace Community]( https://solace.community/)
