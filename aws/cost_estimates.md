# Cost Estimates and Pricing Assumptions

## Architecture and Services

The Smart Storage Tier Recommender uses a fully serverless architecture on AWS, completely avoiding fixed costs associated with instances (EC2) or relational databases (RDS). The core services are S3, Lambda, DynamoDB, API Gateway, Cognito, CloudFront, CloudWatch, SNS, IAM, and AWS Budgets.

## Pricing Assumptions (Monthly)
*Assumes Free Tier is applicable where possible.*

1. **Amazon S3**
   - Assuming 100 GB of Medical Images
   - Base Standard Storage: $0.023/GB = $2.30/month
   - Using the smart tiering: 
     - 20% Standard: $0.46
     - 30% Standard-IA: $0.375
     - 30% Glacier Flexible: $0.108
     - 20% Deep Archive: $0.02
     - Data Retrieval Cost (estimated 5 GB total): ~$0.05
   - Total Estimated S3 Cost: ~$1.01/month (Savings of ~56%)

2. **AWS Lambda**
   - Free Tier: 1M free requests and 400,000 GB-seconds per month
   - Expected usage: ~10,000 invocations (inference + API)
   - Estimated Cost: $0.00 (within Free Tier)

3. **Amazon DynamoDB**
   - Free Tier: 25 GB of data, 25 WCU, 25 RCU
   - Expected usage: <1 GB of metadata and embeddings, low throughput
   - Estimated Cost: $0.00 (within Free Tier)

4. **Amazon API Gateway**
   - Free Tier: 1M API calls per month for 12 months
   - Expected usage: ~5,000 API calls
   - Estimated Cost: $0.00 (within Free Tier)

5. **Amazon Cognito**
   - Free Tier: 50,000 MAUs
   - Expected usage: < 50 users (medical staff/admins)
   - Estimated Cost: $0.00 (within Free Tier)

6. **CloudWatch & SNS**
   - Free Tier: 10 Custom Metrics, 1M API Requests, 1,000 email notifications
   - Expected usage: 2 Custom metrics, <100 emails
   - Estimated Cost: $0.00 (within Free Tier)

## Projected Monthly Cost
**Total Expected Monthly Cost**: **~$1.01** (Primarily S3 Storage costs)

Compared to storing all 100GB in S3 Standard ($2.30), the smart tiering yields substantial cost savings while maintaining immediate access for high-probability scans.
