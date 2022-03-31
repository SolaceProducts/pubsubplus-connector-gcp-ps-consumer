# GCP Pub/Sub to Solace PubSub+ REST-Based Event Publishing Guide

This guide provides an example of how to use the Solace PubSub+ REST API to stream events from Google Pub/Sub to Solace PubSub+ event brokers.

Contents:
  * [Introduction](#introduction)
  * [Prerequisites](#prerequisites)
  * [Solution Overview](#solution-overview)
  * [Components and Interactions](#components-and-interactions)
    + [Connector Service in GCP Cloud Run](#connector-service-in-cloud-run)
    + [GCP Pub/Sub Push Delivery](#gcp-pubsub-push-delivery)
    + [PubSub+ Event Broker REST API for Inbound Messaging](#pubsub-event-broker-rest-api-for-inbound-messaging)
    + [Pub/Sub message contents to Solace Message Mapping](#pubsub-message-contents-to-solace-message-mapping)
    + [Solace PubSub+ Connection Details as GCP Secret](#solace-pubsub-connection-details-as-gcp-secret)
    + [PubSub+ REST API Client Authentication](#pubsub-rest-api-client-authentication)
      - [Basic Authentication](#basic-authentication)
      - [Client Certificate Authentication](#client-certificate-authentication)
      - [OAuth 2.0 Authentication](#oauth-20-authentication)
  * [Connector Implementation](#connector-implementation)
  * [Performance considerations](#performance-considerations)
  * [Quick Start](#quick-start)
  * [Troubleshooting](#troubleshooting)
    + [Cloud Run Logs](#cloud-run-logs)
    + [Connector Local Testing](#connector-local-testing)
  * [Contributing](#contributing)
  * [Authors](#authors)
  * [License](#license)
  * [Resources](#resources)


## Introduction

From the [many options to connect](https://www.solace.dev/), a growing number of third-party and cloud-native applications choose the Solace PubSub+ _REST API_ to stream events into the [PubSub+ event mesh](https://solace.com/solutions/initiative/event-mesh/). PubSub+ offers a flexible, inbound REST interface. This guide shows you how to make use of it as an example of publishing events from [Google Cloud Platform (GCP) Pub/Sub service](https://cloud.google.com/pubsub/docs/overview) to Solace PubSub+.

Users are encouraged to modify this quickstart to accommodate other approaches or even publishing from other cloud services.

## Prerequisites

This guide presumes that you have a basic understanding of:

* Solace PubSub+ event brokers [core messaging concepts](https://docs.solace.com/Basics/Core-Concepts.htm)
* Google Cloud Platform (GCP) [Cloud Pub/Sub](https://cloud.google.com/pubsub), [Cloud Run](https://cloud.google.com/run), and [Secret Manager](https://cloud.google.com/secret-manager) services
* Python programming language

## Solution Overview

The following diagram depicts the main components of the solution.

![alt text](/images/architecture.png "Overview")

_Cloud Pub/Sub_, _Cloud Run_ and _Secret Manager_ are GCP services running in Google Cloud Platform (GCP). _Solace PubSub+_ is shown here accessible through a public REST API service. PubSub+ may be an event broker in HA or non-HA deployment, or part of a larger PubSub+ event mesh.

Given an existing _Topic_ configured in Cloud Pub/Sub, a _Subscription_ is created to this topic which triggers the _Connector logic_ deployed as a service in Cloud Run. The Connector does the following task:
1. Checks the received Pub/Sub message
2. Gets the _Solace PubSub+ broker connection details_ that have been configured as a secret in the Secret Manager
3. Constructs an HTTP REST request, message body, and headers by mapping information from the received Pub/Sub message contents and taking into account the configured _Authentication method_ in PubSub+.
4. Sends the request to PubSub+ using the REST API. The REST API response indicates the success of getting the message into PubSub+.

Messages published to the Google Pub/Sub Topic are now being delivered to the PubSub+ event broker, and are available for consumption by any of its [supported APIs](https://solace.com/products/apis-protocols/) from any point of the event mesh.

## Components and Interactions

### Connector Service in Cloud Run

The Connector service deployed in Cloud Run, is implemented in Python v3.9 in this example. The same functionality can be adapted to any other programming language and used in Cloud Run. As alternatives, the Connector service could also be deployed in Google Cloud Functions or App Engine.

### GCP Pub/Sub Push Delivery

The Cloud Pub/Sub Subscription is set to use [Push delivery](https://cloud.google.com/pubsub/docs/push), which immediately calls the REST trigger URL of the Connector service when a message becomes available that matches the subscription.

It is recommended to configure the Connector service to "Require Authentication" when deploying in Cloud Run. This configuration uses OAuth 2.0 between Cloud Pub/Sub and Cloud Run with the authentication/authorization automatically handled within GCP.

> **Important**: If "Require Authentication" is set, the Google IAM Service Account used by the Subscription must include the role of `Cloud Run Invoker`.

### PubSub+ Event Broker REST API for Inbound Messaging

PubSub+ REST API clients are called "REST publishing clients" or "REST producers". They [publish events into a PubSub+ event broker](https://docs.solace.com/Open-APIs-Protocols/Using-REST.htm) using the REST API. The ingested events are converted to the same [internal message format](https://docs.solace.com/Basics/Message-What-Is.htm) as produced by any other API, and can also be consumed by any other supported API.

> **Note**: This guide uses [REST messaging mode](https://docs.solace.com/Open-APIs-Protocols/REST-get-start.htm#When) from the Solace REST API.

The following REST to Solace-specific HTTP message conversions apply:

| REST protocol element | Solace Message | Additional Reference in Solace Documentation|
|----------|:-------------:|------:|
| Request `host:port` | Maps to the PubSub+ `message-vpn` to be used for the message | [Solace PubSub+ Event Broker Message VPN Selection](https://docs.solace.com/RESTMessagingPrtl/Solace-Router-Interactions.htm#VPN-Selection)
| Request path: `/QUEUE/queue-name` or `/TOPIC/topic-string`| PubSub+ Queue or Topic destination for the message | [REST HTTP Client to Solace Event Broker HTTP Server](https://docs.solace.com/RESTMessagingPrtl/Solace-REST-Message-Encoding.htm#Messagin) |
| Authorization  HTTP header | May support client authentication depending on the authentication scheme used | [Client Authentication](https://docs.solace.com/RESTMessagingPrtl/Solace-Router-Interactions.htm#Client)
| Content-Type HTTP header | Determines a `text` or `binary` message type. Becomes available as a message attribute. | [HTTP Content-Type Mapping to Solace Message Types](https://docs.solace.com/RESTMessagingPrtl/Solace-REST-Message-Encoding.htm#_Ref393980206)
| Content-Encoding HTTP header | Must be `UTF-8` for  the `text` message type. Become available as a message attribute. | [HTTP Content-Type Mapping to Solace Message Types](https://docs.solace.com/RESTMessagingPrtl/Solace-REST-Message-Encoding.htm#_Ref393980206)
| Solace-specific HTTP headers | If a header is present, it can be used to set the corresponding Solace-specific message REST attribute or property. **Important:** if setting Solace Client Name, ensure it is unique across all messages otherwise it may result in contention. | [Solace-Specific HTTP Headers](https://docs.solace.com/RESTMessagingPrtl/Solace-REST-Message-Encoding.htm#_Toc426703633)
| REST request body| The message body (application data) |
| REST HTTP response | A 200 OK response is returned after the event broker successfully processed the request, otherwise an error code. For persistent messages, processing includes that they have been successfully stored on the event broker. | [HTTP Responses from Event Broker to REST HTTP Clients](https://docs.solace.com/RESTMessagingPrtl/Solace-REST-Status-Codes.htm#Producer-on-Post)

### Pub/Sub Message contents to Solace Message Mapping

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
> **Note**: A Pub/Sub "topic" is not available from the JSON object, only the subscription.

The sample Connector maps information from this JSON object to PubSub+ REST API Request parameters (see the previous section) so when ingested into PubSub+, the following Solace message is created:

| Pub/Sub JSON field | Solace Message Element |
|------------------|-------------|
| `message.attributes` | User `Property Map` of type `String` for each attribute present, example: `Key 'AA' (STRING) BB` |
| `message.data` |  Payload, base64-decoded from `message.data` |
| `message.messageId` | Application Message ID |
| `message.orderingKey` (if present) | User `Property Map` of type `String` |
| `message.publishTime` (RFC3339 encoded) | Timestamp (milliseconds since Epoch) |
| `subscription` | User `Property Map` of type `String`, key `google_pubsub_subscription` (full `subscription` string) |
|| Key `google_pubsub_project` (extracted from `projects` as part of `subscription`), example: `my-gcp-project-1234` |
|| Key `google_pubsub_subscriptionname` (extracted from `subscriptions` as part of `subscription`), example `my-topic-run-sub` |
|| Destination, created from subscription (in this example): PubSub+ topic `gcp/pubsub/my-topic-run-sub`

This an example of the resulting Solace message dump:
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

### Solace PubSub+ Connection Details as GCP Secret

The Connector service in Cloud Run accesses the PubSub+ event broker's REST Messaging service connection details from a secret, which is configured to be available through the `SOLACE_BROKER_CONNECTION` environment variable. This is a recommended security best practice because connection details include credentials to authenticate the Connector service, as a REST client to PubSub+.

We use a simple flat JSON structure for the connection details:
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
* `ServerCA` this is optional, if provided it is used to trust the specified Certificate Authority when connecting to the PubSub+ REST event broker; it is useful for self-signed server certificates. **Note**: Python TLS library tighter security requires that the broker name has to be in the "Subject Alternative Name" of the used certificate.
* `AuthScheme` defines the authentication scheme to use, for details see the [PubSub+ REST API Client authentication](#pubsub-rest-api-client-authentication) section below.
* Additional fields are specific to the `AuthScheme` used

Secrets can be set and updated through Secret Manager. Although the Connector service is configured to use the Secret with the tag "latest", it must be re-deployed to pick up changes if there has been any update to the Secret.

> **Important**: The Google IAM Service Account used by the Connector service in Cloud Run must include the role of `Secret Manager Secret Accessor`.

### PubSub+ REST API Client Authentication

The following authentication schemes are supported:
* Basic
* Client Certificate
* OAuth 2.0 (PubSub+ release 9.13.1 and later)

The PubSub+ Event Broker must be configured to use one of the above options for REST API clients. For more details refer to the [Solace documentation about Client Authentication](https://docs.solace.com/Overviews/Client-Authentication-Overview.htm).

#### Basic Authentication

This is based on a shared username and password that is configured in the broker. If using PubSub+ Cloud, it comes [preconfigured](https://docs.solace.com/Cloud/ght_select_correct_username_pw.htm) with basic authentication. Refer to the Solace documentation for [advanced configuration](https://docs.solace.com/Configuring-and-Managing/Configuring-Client-Authentication.htm#Basic).

Here, the connection secret contains following example information:
```json
{
  "Host": "https://myhost:9443",
  "AuthScheme": "basic",
  "Username": "myuser",
  "Password": "mypass"
}
```

Credentials are conveyed in the Authorization header of the REST request with 'username:password' encoded in base64, for example: `Authorization: Basic bXl1c2VyOm15cGFzcw==`

#### Client Certificate Authentication

Here the username is derived from the Common Name (CN) used in the TLS Client Certificate signed by a Certificate Authority that is also trusted by the broker. This username must be also provisioned in the PubSub+ event broker under Client Usernames and you should ensure that Client Certificate Authentication is enabled.

Refer to a [step-by-step configuration guide for PubSub+ Cloud](https://docs.solace.com/Cloud/ght_client_certs.htm?Highlight=Client%20Certificate%20authentication) or the [detailed general configuration guide in Solace documentation](https://docs.solace.com/Configuring-and-Managing/Configuring-Client-Authentication.htm#Client-Cert). 

The connection secret contains the Client Certificate, along with the Client Key, as in the following sample. Notice that line breaks have been replaced by `\n`:
```json
{
  "Host": "https:/myhost:9443",
  "AuthScheme": "client-cert",
  "ClientCert": "-----BEGIN CERTIFICATE-----\n+etc\n+etc\n+etc\n-----END CERTIFICATE-----",
  "ClientKey": "-----BEGIN PRIVATE KEY------\n+etc\n+etc\n+etc\n-----END PRIVATE KEY-----"
}
```

When you use Client Certificate authentication, no Authorization header is required in the REST request as the `SSLContext` object in the code takes care of using the provided client secret and key from the TLS connection setup.

#### OAuth 2.0 Authentication

Since the Connector service runs in GCP, this example shows how to conveniently use Google as OAuth provider. The connector can easily obtain [an identity token from the Cloud Run metadata server API](https://cloud.google.com/run/docs/securing/service-identity#fetching_identity_and_access_tokens_using_the_metadata_server) which returns a JWT Id-token associated with the identity of the Google IAM Service Account used by the Connector service (["SA2", as referenced later in this guide](#service-account-sa2)).

The OAuth token is conveyed in the authorization header of the REST request, for example:
```
Authorization: Bearer eyJhbGciOiifQ.2MDIyOTkyNzA5MDYwMjU0MzQ5In0.iNI3rPN5sxPOWkSCLJJ1AOhUKwWQyI
```
The connection secret can be provided as follows:
```json
{
  "Host": "https://myhost:9443",
  "AuthScheme": "oauth",
  "Audience": "myAudience"
}
```
where `Audience` and the `OAuth Client ID` in the OAuth profile configured on the event broker must be set to the same case-sensitive string.

The generated Google JWT contains:
```json
{
  "aud": "myAudience",
  "azp": "123456789",
  "email": "pubsub-solace-producer-run-sa@my-gcp-project-1234.iam.gserviceaccount.com",
  "email_verified": true,
  "exp": 1638980106,
  "iat": 1638976506,
  "iss": "https://accounts.google.com",
  "sub": "123456789"
}
```

Note: `azp` and `email` fields are the service account's ([SA2](#service-account-sa2)) "OAuth 2 Client ID" and "Email" properties, that can be looked up at the GCP IAM&Admin console, Service Accounts.

For the recommended [event broker OAuth access control configuration](https://docs.solace.com/Configuring-and-Managing/Configuring-Client-Authentication.htm#OAuth), provide following settings (leave everything else at default):

* [OAuth profile defined](https://docs.solace.com/Configuring-and-Managing/Configuring-Client-Authentication.htm#Managing-OAuth-Profiles) as follows:
  * [OAuth authentication enabled](https://docs.solace.com/Configuring-and-Managing/Configuring-Client-Authentication.htm#Enabling) (at the Message VPN level)
  * Set OAuth `Client ID` to the same case-sensitive string as `Audience` in the connection secret above. Note: Client Secret is not used here.
  * `OAuth Role` set as `Client`
  * `Issuer Identifier` set to `https://accounts.google.com`
  * `Discovery Endpoint`set `https://accounts.google.com/.well-known/openid-configuration`
  * `Username Claim Name`, that defines which claim from above JWT to be used to derive the Username. It can be set either to `azp` (meaning authorized party), the "OAuth 2 Client ID" associated to the Google service account used by the Connector service ([SA2](#service-account-sa2)); or `email`, which is the Email setting of the same service account. Note: the corresponding [Client Username must then be configured](https://docs.solace.com/Configuring-and-Managing/Configuring-Client-Usernames.htm) in the broker
  * `Validate Type` is enabled; and the `Required ID Token Type` is set to `JWT`

## Connector Implementation

The Python code implementing the Connector is available from the GitHub repo of this project: [`python-samples\run\gcp-pubsub-to-solace-pubsubplus\main.py`](python-samples/run/gcp-pubsub-to-solace-pubsubplus/main.py)
</br>

The Connector is essentially a REST server leveraging the Python Flask web framework. The sample extends the [Google Run "Hello World" application](https://cloud.google.com/run/docs/quickstarts/build-and-deploy/python) with functionality to demonstrate how to process and forward Cloud Pub/Sub messages to Solace PubSub+.

Processing is straightforward:
1. Received request is expected as a Pub/Sub message and checked for valid JSON format and to include valid contents, then payload is extracted
1. Outgoing PubSub+ REST message HTTP headers are prepared by appropriate mapping from Pub/Sub message metadata - see section [Pub/Sub message contents to Solace Message Mapping](#pubsub-message-contents-to-solace-message-mapping) in this guide.
1. The `get_conn_config()` function is defined to get and return the contents of the [connection secret](#solace-pubsub-connection-details-as-gcp-secret) injected as `SOLACE_BROKER_CONNECTION` environment variable
1. Authentication info is prepared depending on the authentication scheme obtained from the secret: for example an `Authentication` header may be added
1. An HTTPS connection is opened to Solace PubSub+ REST API and the prepared REST message including headers and payload is sent. This includes the request path which defines the destination of the Solace message. This sample sends the Solace message to a PubSub+ event topic that includes the name of the subscription: `gcp/pubsub/{subscription}`
1. REST response from PubSub+ is obtained and returned as the overall result of the processing

## Performance considerations

Using GCP Pub/Sub subscription default options message duplicates may happen, which will also be published to Solace PubSub+. The PubSub+ "ApplicationMessageId", taken from the guaranteed unique Pub/Sub message id, can be used to identify duplicates.

* To minimize duplicates there is an option to enable [Exactly once delivery](https://cloud.google.com/pubsub/docs/exactly-once-delivery#console) when creating the subscription. Note that this option was a pre-GA feature at the time of writing.

GCP Pub/Sub messages [may also be delivered out of order](https://cloud.google.com/pubsub/docs/subscriber#at-least-once-delivery) to the PubSub+ event broker.

* To minimize out-of-order and duplicate delivery at the same time, enable Pub/Sub [message ordering](https://cloud.google.com/pubsub/docs/ordering). Any messages having the same ordering key will be delivered exactly once and in order.

> **Note** ordering has an impact on maximum message rate: throughput is the highest with no ordering key used, followed by using multiple ordering keys (several groups of messages, each group with unique ordering key), and the lowest throughput is if all messages are using the same ordering key (all messages delivered sequentially).

To support ordering, following settings must also be enabled:
* The Pub/Sub subscription must have Message ordering enabled. Note that this cannot be changed for an existing subscription, create a new subscription if required.
* Use the same ordering key for messages sent to the Pub/Sub topic, as required.

It should be also noted that for simplicity, this quickstart leverages GCP Pub/Sub Push delivery. A GCP Pub/Sub Pull delivery approach may yield greater performance.

## Quick Start

This example demonstrates an end-to-end scenario using Basic authentication.

**Step 1: Access to Google Cloud and PubSub+ Event Broker Services**

Get access to:
* Solace PubSub+ Event Broker, or [sign up for a free PubSub+ Cloud account](https://docs.solace.com/Cloud/ggs_login.htm). Note that the broker must have TLS configured (comes automatically when using PubSub+ Cloud).
* GCP or [sign up for a free GCP account](https://console.cloud.google.com/freetrial/signup). Add appropriate permissions to your user if you encounter any restrictions to perform the next administration tasks. For development purposes the simplest option is if you user has account "Owner" or "Editor" rights.

[Enable GCP services](https://cloud.google.com/service-usage/docs/enable-disable), including "IAM", "Pub/Sub", "Secret Manger", "Cloud Run" and its dependency, the "Container Registry".

[Install Google Cloud SDK](https://cloud.google.com/sdk/docs/install#managing_an_installation) and [initialize it](https://cloud.google.com/sdk/docs/initializing). Ensure to use `gcloud` version `365.0.1` or later as older versions have limited support for the fully managed version of Cloud Run.

**Step 2: Setup Prerequisites**

Create the following in GCP:
* A [Pub/Sub topic](https://cloud.google.com/pubsub/docs/quickstart-console#create_a_topic) `my-topic` for which messages are  forwarded to a PubSub+ event broker.
* [IAM Service Account(s)](https://cloud.google.com/iam/docs/creating-managing-service-accounts#creating) - a common SA with both roles would suffice, separate SAs are recommended for better security:
  * SA1 to be used by Pub/Sub Subscription, with role `Cloud Run Invoker`; and
  * SA2 for the Connector service in Cloud Run, with role `Secret Manager Secret Accessor`<a name="service-account-sa2"></a>

For simplicity, we only create one SA `pubsub-solace-producer-run-sa` in this quickstart with both roles.

> **Note**: It may take several minutes for the service accounts and roles to become active.

**Step 3: Create a Secret with PubSub+ Connection Details**

[Create a secret](https://cloud.google.com/secret-manager/docs/creating-and-accessing-secrets#create) in Secret Manager providing a name `my-solace-rest-connection-secret` and following value (replace Host, Username and Password with your [PubSub+ event broker's REST connection details](https://docs.solace.com/Cloud/ggs_create_first_service.htm#find-service-details)):
```json
{
  "Host": "https://myhost:9443",
  "AuthScheme": "basic",
  "Username": "myuser",
  "Password": "mypass"
}
```

> **Note**: add `ServerCA` field if your server's certificate signing Certificate Authority is not a public provider, see [here](#solace-pubsub-connection-details-as-gcp-secret) for  more details.

**Step 4: Deploy the Connector in Cloud Run and Link It to the Secret**

This step involves building a container image from the Connector source code, then deploying it into Cloud Run with the service account (this refers to SA2) from Step 2 and the created secret from Step 3 assigned.

Run following in a shell, replacing `<PROJECT_ID>` and `<REGION>` from your GCP project and updating the `IMAGE_NAME` etc. artifact names if required.

```bash
# TODO: provide <PROJECT_ID> and <REGION>
export GOOGLE_CLOUD_PROJECT=<PROJECT_ID>
export GOOGLE_CLOUD_REGION=<REGION>
# TODO: update as required
export IMAGE_NAME=my-connector-image
export SERVICEACCOUNT_SA2_NAME=pubsub-solace-producer-run-sa
export SECRET_NAME=my-solace-rest-connection-secret
export RUN_SERVICE_NAME=gcp-solace-connector-service
# Get source from the GitHub repo
git clone https://github.com/SolaceProducts/pubsubplus-connector-gcp-ps-consumer.git
cd pubsubplus-connector-gcp-ps-consumer/python-samples/run/gcp-pubsub-to-solace-pubsubplus/
# Submit a build to GCP Container Registry using Google Cloud Build
gcloud builds submit --tag gcr.io/${GOOGLE_CLOUD_PROJECT}/${IMAGE_NAME}
# Deploy to Cloud Run
gcloud run deploy ${RUN_SERVICE_NAME} \
    --image gcr.io/${GOOGLE_CLOUD_PROJECT}/${IMAGE_NAME} \
    --no-allow-unauthenticated \
    --platform managed \
    --region ${GOOGLE_CLOUD_REGION} \
    --service-account=${SERVICEACCOUNT_SA2_NAME}@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com \
    --set-secrets=SOLACE_BROKER_CONNECTION=${SECRET_NAME}:latest
```

Notice the Connector service trigger URL printed on the console after the deployment has been created.

**Step 5: Create a push Subscription to the Topic and Link It to the Connector**

Follow the [instructions to create a Subscription](https://cloud.google.com/pubsub/docs/admin#creating_subscriptions), provide:
* Subscription ID (name), for example `my-topic-run-sub`
* Pub/Sub topic name `my-topic` which has been created in Step 2
* Select "Push" delivery type
* Set the Endpoint URL to the Connector service trigger URL from Step 4 (if needed you can look it up running `gcloud run services list`)
* Set checkbox to Enable Authentication
* Set the service account to `pubsub-solace-producer-run-sa` (This refers to SA1 in Step 2 if using separate service accounts)

With this the Subscription becomes active and the system is ready for testing!

**Step 6: Testing**

To watch messages arriving into PubSub+, use the "Try Me!" test service of the browser-based administration console to subscribe to messages to the `sinktest` topic. Behind the scenes, "Try Me!" uses the JavaScript WebSocket API.

   * If you are using PubSub+ Cloud for your messaging service, follow the instructions in [Trying Out Your Messaging Service](https://docs.solace.com/Cloud/ggs_tryme.htm). Tip: you may need to fix the "Establish Connection" details (where the Event Broker URL port should be 443, manually copy the Client Username and Password from the "Cluster Manager" "Connect" information).
   * If you are using an existing event broker, log into its [PubSub+ Broker Manager admin console](//docs.solace.com/Broker-Manager/PubSub-Manager-Overview.htm#mc-main-content) and follow the instructions in [How to Send and Receive Test Messages](https://docs.solace.com/Broker-Manager/PubSub-Manager-Overview.htm#Test-Messages).

In both cases, ensure to set the subscription to `gcp/pubsub/>`, which is a wildcard subscription to anything starting with `gcp/pubsub/` and would catch what the connector is publishing to.

Then publish a message to Google Pub/Sub `my-topic`, from [GCP Console](https://cloud.google.com/pubsub/docs/publisher#publishing_messages) or using the command line:
```
gcloud pubsub topics publish my-topic \
    --message="Hello World!"
```
Then see the message arriving in PubSub+:

![alt text](/images/testmsg-received.png "Message received")

**Deleting the deployment**

Delete following artifacts at the respective GCP console pages if no longer needed:
* Push Subscription
* Cloud Run Connector service
* Secret
* Service Account(s)
* Pub/Sub Topic

## Troubleshooting

### Cloud Run Logs

In case of issues, it is recommended to [check the logs in Cloud Run](https://cloud.google.com/run/docs/logging#viewing-logs-cloud-run). Ensure that you refresh to see the latest logs. If there is a failure the Subscription, it keeps re-delivering messages and it may be necessary to go to the Pub/Sub Subscription details to purge messages to stop re-delivery.

For more details on the Connector processing, change the level of logging to DEBUG in the Python script, rebuild the image and redeploy:
```
logging.basicConfig(level=logging.DEBUG)
```

### Connector Local Testing

While the connector code is ready for deployment into Cloud Run, it can be tested by running locally in a Python 3.9 or later environment:

```bash
# From project root
cd python-samples/run/gcp-pubsub-to-solace-pubsubplus
SOLACE_BROKER_CONNECTION="{ "Host": "https://myhost:9443", "AuthScheme": "basic", "Username": "user", "Password": "pass" }" \
  bash -c "python main.py"
```
This sets the `SOLACE_BROKER_CONNECTION` environmant variable, which is otherwise taken from the GCP Secret, and starts the Connector service listening at `127.0.0.1:8080` (you may need to adjust above command depdending on your OS environment).

Use a REST client tool such as curl or Postman to emulate a trigger message from Pub/Sub and verify the request makes it to your PubSub+ event broker.

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

Read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests to us.

## Authors

See the list of [contributors](../../graphs/contributors) who participated in this project.

## License

This project is licensed under the Apache License, Version 2.0. See the [LICENSE](LICENSE) file for details.

## Resources

For more information about Solace technology, see the following resources:

- The [Solace Developers website](https://www.solace.dev/)
- [Solace Documentation](https://docs.solace.com/)
- Understanding [Solace technology]( https://solace.com/products/tech/)
- Ask the [Solace Community]( https://solace.community/)
