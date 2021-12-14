# GCP Pub/Sub to Solace PubSub+ REST-Based Event Publishing Guide

This guide provides an example use of the Solace PubSub+ REST API to stream events from Google Pub/Sub to Solace PubSub+.

## Introduction

From the [many options to connect](https://www.solace.dev/), a growing number of third party and cloud-native applications choose the Solace PubSub+ _REST API_ to stream events into the [PubSub+ event mesh](https://solace.com/solutions/initiative/event-mesh/). PubSub+ offers a flexible inbound REST interface and this guide shows how to make use of it at the example of publishing events from [Google Cloud Platform (GCP) Pub/Sub service](https://cloud.google.com/pubsub/docs/overview) to Solace PubSub+.

## Assumptions

This guide assumes basic understanding of:

* Solace PubSub+ [core messaging concepts](https://docs.solace.com/Basics/Core-Concepts.htm)
* Google Cloud Platform (GCP) [Cloud Pub/Sub](https://cloud.google.com/pubsub), [Cloud Run](https://cloud.google.com/run) and [Secret Manager](https://cloud.google.com/secret-manager) services
* Python programming language

It is also assumed you have access to:
* Solace PubSub+ Event Broker, or [signed up for a free PubSub+ Cloud account](https://docs.solace.com/Cloud/ggs_login.htm)
* GCP with appropriate admin rights, or [signed up for a free GCP account](https://console.cloud.google.com/freetrial/signup)

## Solution overview

The following diagram depicts the main components of the solution.

![alt text](/images/architecture.png "Overview")

_Cloud Pub/Sub_, _Cloud Run_ and _Secret Manager_ are GCP services running in Google Cloud. _Solace PubSub+_ is shown here accessible through a public REST API service. PubSub+ may be a single event broker in HA or non-HA deployment or part of a larger PubSub+ Event Mesh.

Given an existing _Topic_ configured in Cloud Pub/Sub, a _Subscription_ is created to this topic which triggers the _Connector logic_ deployed in Cloud Run. The Connector (1) checks the received Pub/Sub message, (2) gets _Solace PubSub+ broker connection details_ that have been configured as a secret in Secret Manager, (3) constructs an HTTP REST Request, message body and headers also taking into account the configured _Authentication method_ at PubSub+, and (4) sends the Request to PubSub+ using the REST API. The REST API Response indicates the success of getting the message into PubSub+.

Messages published to the Google Pub/Sub Topic will now be delivered to the PubSub+ Event Broker and available for consumption by any of its [supported APIs](https://solace.com/products/apis-protocols/) from any point of the Event Mesh.

### Components and interactions

#### Connector service in GCP Cloud Run

The Connector service, deployed in Cloud Run, is implemented in Python v3.9 in this example. The same functionality can be adapted to any other programming language and used in Cloud Run. The Connector service could have also been deployed in Google Cloud Functions or App Engine as alternatives.

#### GCP Pub/Sub Push delivery

The Google Pub/Sub Subscription is set to use [Push delivery](https://cloud.google.com/pubsub/docs/push) which immediately calls the REST trigger URL of the Connector service when a message becomes available that matches the subscription.

It is recommended to deploy the Connector service in Google Run configured to "Require Authentication". This will use OAuth 2.0 between Pub/Sub and Run with authentication/authorization automatically handled within GCP.

> Important: If "Require Authentication" is set, the Google IAM Service Account used by the Subscription must include the role of `Cloud Run Invoker`.

#### Solace PubSub+ Connection details as GCP Secret

The Connector service in Cloud Run will access the PubSub+ event broker REST Messaging service connection details from a secret which is configured to be available through the `SOLACE_BROKER_CONNECTION` environment variable. This is recommended security best practice because connection details include credentials to authenticate the Connector service, as a REST client to PubSub+.

We will be using a simple flat JSON structure for the connection details:
```json
{
  "Host": "https://myhost:9443",
  "AuthScheme": "basic",
  :
  "field": "value",
  :
}
```
Where:
* `Host` provides the event broker REST service endpoint IP or FQDN including the port. Transport must be secure, using HTTPS
* `AuthScheme` defines the authentication scheme to use, see the [PubSub+ REST API Client authentication](#pubsub-rest-api-client-authentication) section below.
* Additional fields are specific to the `AuthScheme`

Secrets can be set and updated through Secret Manager and the Connector service will use the latest Secret configured.

> Important: The Google IAM Service Account to be used by the Connector service in Cloud Run must include the role of `Secret Manager Secret Accessor`.

#### PubSub+ Event Broker REST API for inbound messaging

PubSub+ REST API clients are called "REST publishing clients" or "REST producers". They [publish events into a PubSub+ event broker](https://docs.solace.com/Open-APIs-Protocols/Using-REST.htm) using the REST API. The ingested events will be converted to the same [internal message format](https://docs.solace.com/Basics/Message-What-Is.htm) as produced by any other API and can also be consumed by any other supported API.

> Note: this guide is using [REST messaging mode](https://docs.solace.com/Open-APIs-Protocols/REST-get-start.htm#When) of the Solace REST API.

The following REST to PubSub+ message conversions apply:

| REST protocol element | PubSub+ message | Additional Reference in Solace Documentation|
|----------|:-------------:|------:|
| Request `host:port` | Maps to the Solace `message-vpn` to be used for the message | [Solace PubSub+ Event Broker Message VPN Selection](https://docs.solace.com/RESTMessagingPrtl/Solace-Router-Interactions.htm#VPN-Selection)
| Request path: `/QUEUE/queue-name` or `/TOPIC/topic-string`| Solace Queue or Topic destination for the message | [REST HTTP Client to Solace Event Broker HTTP Server](https://docs.solace.com/RESTMessagingPrtl/Solace-REST-Message-Encoding.htm#Messagin) |
| Authorization  HTTP header | May support client authentication depending on the authentication scheme used | [Client Authentication](https://docs.solace.com/RESTMessagingPrtl/Solace-Router-Interactions.htm#Client)
| Content-Type HTTP header | Determines `text` or `binary` message type | [HTTP Content-Type Mapping to Solace Message Types](https://docs.solace.com/RESTMessagingPrtl/Solace-REST-Message-Encoding.htm#_Ref393980206)
| Solace-specific HTTP headers | If a header is present, it can be used to set the corresponding Solace message attribute or property | [Solace-Specific HTTP Headers](https://docs.solace.com/RESTMessagingPrtl/Solace-REST-Message-Encoding.htm#_Toc426703633)
| REST request body| The message body (application data) |
| REST HTTP response | For persistent messages, the 200 OK is returned after the message has been successfully stored on the event broker, otherwise an error code | [HTTP Responses from Event Broker to REST HTTP Clients](https://docs.solace.com/RESTMessagingPrtl/Solace-REST-Status-Codes.htm#Producer-on-Post)

#### PubSub+ REST API Client authentication

The following authentication schemes are supported:
* Basic
* Client Certificate
* OAuth 2.0 (PubSub+ release 9.13 and later)

The PubSub+ Event Broker must be configured to use one of the above options for REST API clients. For more details refer to the [Solace documentation about Client Authentication](https://docs.solace.com/Overviews/Client-Authentication-Overview.htm).

##### Basic authentication

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

Credentials are conveyed in the Authorization header, 'username:password' encoded in base64, for example: `Authorization: Basic bXl1c2VyOm15cGFzcw==`

##### Client Certificate authentication

Here the Username is derived from the Common Name (CN) used in the TLS Client Certificate signed by a Certificate Authority that is also trusted by the broker. This Username must be also provisioned in the broker.

Refer to a [step-by-step configuration guide for PubSub+ Cloud](https://docs.solace.com/Cloud/ght_client_certs.htm?Highlight=Client%20Certificate%20authentication) or the [detailed general configuration guide in Solace documentation](https://docs.solace.com/Configuring-and-Managing/Configuring-Client-Authentication.htm#Client-Cert). 

The connection secret shall contain the Client Certificate, along with the Client Key, as in the following sample. Notice that here line breaks have been replaced by `\n` or it is also acceptable to simply delete them:
```json
{
  "Host": "https://mr-1js1tiv17mwh.messaging.solace.cloud:9443",
  "AuthScheme": "client-cert",
  "ClientCert": "-----BEGIN CERTIFICATE-----\n+etc\n+etc\n+etc\n-----END CERTIFICATE-----",
  "ClientKey": "-----BEGIN PRIVATE KEY------\n+etc\n+etc\n+etc\n-----END PRIVATE KEY-----"
}
```

##### OAuth 2.0 authentication














### Using Solace REST

### Authentication
  § Basic, Client cert, Oauth 2.0
  § Secure storage of Credentials (Secrets)
  
### Transparency, target and header mapping

### Message Body Decoding and Adaptation

## Pre-requisites

### GCP setup

### Solace broker setup

## Quick Start example with Steps

Pre-requisites
- GCP project
- GCP Secrets Manager is [configured](https://cloud.google.com/secret-manager/docs/configuring-secret-manager)
- Create a service account
```
gcloud iam service-accounts create pubsub-solace-producer-run-sa
gcloud projects add-iam-policy-binding ${GOOGLE_CLOUD_PROJECT} \
     --member="serviceAccount:pubsub-solace-producer-run-sa@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com" \
     --role="roles/run.invoker" \
     --role="roles/secretmanager.secretAccessor"
```

1. Get a PubSub+ broker

* Easiest from Solace Cloud
* Obtain connection details

2. Provision connection details in GCP Secret Manager

Replace username, password and host details as required:
```bash
echo '{ "Username": "myuser", "Password": "mypass", "Host": "https://myhost:9443" }' \
    > my-solace-rest-connection.txt
gcloud secrets create my-solace-rest-connection-secret \
    --data-file="./my-solace-rest-connection.txt"
```

3. Deploy the adapter code in GCP Run

Build and submit container image, then deploy.

```
git clone https://github.com/SolaceDev/pubsubplus-connector-gcp-ps-consumer.git
cd pubsubplus-connector-gcp-ps-consumer/python-samples/run/gcp-pubsub-to-solace-pubsubplus/
# provide <PROJECT_ID> and <REGION>
export GOOGLE_CLOUD_PROJECT=<PROJECT_ID>
export GOOGLE_CLOUD_REGION=<REGION>
# Submit a build using Google Cloud Build
gcloud builds submit --tag gcr.io/${GOOGLE_CLOUD_PROJECT}/pubsub-solace-producer
# Deploy to Cloud Run
gcloud run deploy pubsub-solace-producer \
    --image gcr.io/${GOOGLE_CLOUD_PROJECT}/pubsub-solace-producer \
    --no-allow-unauthenticated \
    --platform managed \
    --region ${GOOGLE_CLOUD_REGION} \
    --service-account=pubsub-solace-producer-run-sa@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com
gcloud run services update pubsub-solace-producer \
    --set-secrets=SOLACE_BROKER_CONNECTION=my-solace-rest-connection-secret:latest \
    --platform managed \
    --region ${GOOGLE_CLOUD_REGION}

# With client cert auth
gcloud run deploy pubsub-solace-producer \
    --image gcr.io/${GOOGLE_CLOUD_PROJECT}/pubsub-solace-producer \
    --no-allow-unauthenticated \
    --platform managed \
    --region ${GOOGLE_CLOUD_REGION} \
    --service-account=pubsub-solace-producer-run-sa@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com
gcloud run services update pubsub-solace-producer \
    --set-secrets=SOLACE_BROKER_CONNECTION=my-solace-rest-connection-secret:latest \
    --platform managed \
    --region ${GOOGLE_CLOUD_REGION}

```

4. Create topic in GCP Pub/Sub

Note: if you encounter policy constraints, refer to https://cloud.google.com/pubsub/docs/admin#organization_policy

```bash
gcloud pubsub schemas create test-avro-schema \
        --type=AVRO \
        -- definition='{"type":"record","name":"Avro","fields":[{"name":"StringField","type":"string"},{"name":"FloatField","type":"float"},{"name":"BooleanField","type":"boolean"}]}'
gcloud pubsub topics create topic-with-avro-schema \
        --message-encoding=JSON \
        --schema=test-avro-schema
```

3. Create Subscription in GCP

```
# Determine the run service endpoint
gcloud run services list
gcloud pubsub subscriptions create topic-with-avro-schema-run-sub \
    --topic=topic-with-avro-schema \
    --push-endpoint=https://pubsub-solace-producer-imlb6ykhsq-ue.a.run.app \
    --push-auth-service-account=pubsub-solace-producer-run-sa@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com

gcloud pubsub subscriptions create topic-binary-with-avro-schema-run-sub \
    --topic=topic-binary-with-avro-schema \
    --push-endpoint=https://pubsub-solace-producer-imlb6ykhsq-ue.a.run.app \
    --push-auth-service-account=pubsub-solace-producer-run-sa@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com

```

5. Send message to Pub/Sub

```
gcloud pubsub topics publish topic-with-avro-schema \
    --message='{"StringField": "Shine Test", "FloatField": 2.1415, "BooleanField": false}'
```

---------------------
Client Certificate authentication

Follow https://docs.solace.com/Cloud/ght_client_certs.htm






4. Deploy Function

