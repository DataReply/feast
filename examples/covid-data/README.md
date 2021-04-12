# Feature Store
There are two types of features: 
1. Offline Features
1. Online Features

## General
### Benefits
1. Faster Development
   * It could be simple as running the following:<br> 
   df = feature_store.get(“transaction_volume”).filter_by (transaction_id)
1. Smooth model deployment in production
1. Increased model accuracy
1. Better Collaboration
   * Feature stores bridge that gap and enable everyone to share their work and avoid duplication
1. Track lineage and address regulatory compliance

<br>
Data pipeline before using feature store: <br>

![](/examples/covid-data/images/Picture1.png)

Data pipeline after using feature store: <br>

![](/examples/covid-data/images/Picture2.png)

### Do you need a Feature Store?
You can <b>consider not using</b> a feature store if:
* You’re only training a very small number of models 
* You’re still building a proof of concept
* Your team is very small

## Feature Store vs Data Warehouse
The main architectural difference between a data warehouse and a feature store is that the data warehouse is typically a single columnar database, while the feature store is typically implemented as two databases:
* An <b>offline feature store</b> for serving large batches of features to:
   1. Create train / test datasets 
   1. Create batch applications scoring models using those batches of features
* An <b>online feature store</b> for serving a single row of features (a feature vector) to be used as input features for an online model for an individual prediction.

### Main differences:
* Feature Data Should be Validated before Ingestion
* Time Travel

### Conclusion
Data warehouses can be used to store pre-computed features, but they do not provide much more functionality beyond that for ML pipelines. When Data Scientists need to create train/test data using Python or when online features (for serving features to online models) are needed at low latency, you need a feature store.

## Comparing and contrasting Feast and Amazon SageMaker Feature Store
### Open Source Feature Stores Comparison
![](/examples/covid-data/images/Picture3.png)

<br>

You can find this comparison and other details about open source projects regarding feature stores by visiting: https://www.featurestore.org/

<br>

### Feast vs Amazon SageMaker Feature Store

  <b>| Feast | Amazon SageMaker Feature Store</b>
--|-------|-------------------------------
<b>Open Source</b> | Apache V2 | -
<b>Offline Store</b> | BigQuery | S3
<b>Online Store</b>| BigTable / Redis| Redis / DynamoDB (Not mentioned)
<b>Metadata</b>| DB Tables| -
<b>Feature Engineering</b>|Apache Beam, Python, Apache Spark, and so on| Amazon EMR, AWS Glue, and SageMaker Processing
<b>Supported Platforms</b>|GCP, Azure, AWS, On Premises|AWS
<b>Time Travel</b>|SQL Join|-
<b>Training Data</b>|Streamed to Models|-

<br>

### Cons of SageMaker Feature Store
Amazon SageMaker Feature Store was launched at re:Invent on December 1, 2020. Amazon SageMaker Feature Store is a fully managed, purpose-built repository to securely store, update, retrieve, and share ML features.

1. <b>Maximize the utility of all of your data assets (batch, streaming, and real-time</b>
   * SageMaker Feature Store does not provide tooling to define transformations on real-time or streaming data. <br>
SageMaker will make it easier for your data scientists to consume batch sources when they can reuse features built by other data scientists.

1. <b>Make data scientist self-sufficient</b>
   * To build production data pipelines, data scientists need to combine three loosely integrated tools: SageMaker Pipelines, SageMaker Data Wrangler, and SageMaker Feature Store. Unfortunately these tools only support batch data sources, meaning you’ll still need data engineers and external pipelines to incorporate streaming or real-time data. 
1. <b>Provide easy-to-access and accurate historical data</b>
   * SageMaker does not provide a utility to join historical data from different sources.
1. Enable effective governance
   * SageMaker doesn’t provide intelligent handling of feature versions, meaning keeping track of your features over time will be challenging. <br> SageMaker Feature Store does not cover the entire feature lifecycle, but it does make important strides to making it easier to manage your data for ML in SageMaker.

<br>

![](/examples/covid-data/images/Picture4.jpg)

<br>

## Digging into the details of the offline data storage, the partitioning, and retrieval process

The end to end flow is represented on the picture below. 
* <b>Feast Core</b> – it’s essentially a registry which stores specifications of features, collections of features which we call feature table, and entities which are keys into those feature tables.
* <b>Feast Serving</b> – it provides features in real-time with low latency and mainly used by model serving for running real time predictions. Feast Serving relies on the Online Feature Store, where Redis and Cassandra are used.
<br>

![](/examples/covid-data/images/Picture5.png)
![](/examples/covid-data/images/Picture6.png)
![](/examples/covid-data/images/Picture7.png)
![](/examples/covid-data/images/Picture8.png)
![](/examples/covid-data/images/Picture9.png)