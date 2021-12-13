# GCP Pub/Sub to Solace PubSub+ REST-Based Event Publishing Guide

## Solution overview

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

