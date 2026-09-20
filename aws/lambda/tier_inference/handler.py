import json
import os
import urllib.parse
import boto3
import logging
from datetime import datetime, timezone
import math

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
cloudwatch = boto3.client('cloudwatch')
sns = boto3.client('sns')

# Environment variables
TABLE_NAME = os.environ.get('TABLE_NAME', 'ScanFeatures')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN', '')
MODEL_PATH = os.environ.get('MODEL_PATH', '/opt/model/model.pkl')

table = dynamodb.Table(TABLE_NAME)

def load_model():
    """Load machine learning model."""
    try:
        import joblib
        if os.path.exists(MODEL_PATH):
            return joblib.load(MODEL_PATH)
        else:
            logger.warning(f"Model not found at {MODEL_PATH}. Using mock model.")
            return None
    except Exception as e:
        logger.error(f"Error loading model: {str(e)}")
        return None

model = load_model()

def expected_cost(tier, size_bytes, prob_access):
    """
    Calculate expected monthly cost for a given tier incorporating:
    - Storage cost with 128KB minimum and 40KB Glacier metadata overhead
    - Retrieval fees
    - Tag-filtered transition request fees
    - Clinical safety penalty for retrieval latency
    """
    gb = size_bytes / (1024 ** 3)
    
    # Ensure minimum object sizes are met
    size_ia_gb = max(size_bytes, 128 * 1024) / (1024 ** 3)
    size_glacier_gb = max(size_bytes + 40 * 1024, 128 * 1024) / (1024 ** 3)
    
    # Clinical penalty (scales with access latency to protect against wrong archiving)
    clinical_penalties = {
        'STANDARD': 0.0,
        'STANDARD_IA': 0.002,
        'GLACIER': 0.008,
        'DEEP_ARCHIVE': 0.020
    }
    
    # Transition fees per object
    transition_fees = {
        'STANDARD': 0.0,
        'STANDARD_IA': 0.01 / 1000.0,
        'GLACIER': 0.03 / 1000.0,
        'DEEP_ARCHIVE': 0.05 / 1000.0
    }
    
    storage_cost = 0.0
    retrieval_cost = 0.0
    
    if tier == 'STANDARD':
        storage_cost = 0.023 * gb
    elif tier == 'STANDARD_IA':
        storage_cost = 0.0125 * size_ia_gb
        retrieval_cost = prob_access * 0.01 * gb
    elif tier == 'GLACIER':
        storage_cost = 0.0036 * size_glacier_gb
        retrieval_cost = prob_access * 0.01 * gb
    elif tier == 'DEEP_ARCHIVE':
        storage_cost = 0.00099 * size_glacier_gb
        retrieval_cost = prob_access * (0.02 * gb + 0.0001)
        
    penalty = prob_access * clinical_penalties.get(tier, 0.0)
    transition = transition_fees.get(tier, 0.0)
    
    return storage_cost + retrieval_cost + penalty + transition

def predict_tier(metadata, embedding):
    """
    Predict storage tier based on metadata and embedding.
    """
    # Dummy mock model logic
    prob_access = 0.5
    if model:
        # Assuming model.predict_proba returns probability of access
        import numpy as np
        # Feature vector construction (simplified)
        features = [
            metadata.get('patient_age', 50),
            metadata.get('follow_up_number', 0)
        ]
        if embedding:
            features.extend(embedding[:10]) # use first 10 dims
        else:
            features.extend([0.0]*10)
        
        try:
            # Predict
            prob_access = float(model.predict_proba([features])[0][1])
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            prob_access = 0.5 # fallback

    # Stage 2: Cost rule
    size_bytes = int(metadata.get('object_size_bytes', 1024 * 1024 * 50)) # Default 50MB
    
    tiers = ['STANDARD', 'STANDARD_IA', 'GLACIER', 'DEEP_ARCHIVE']
    costs = {t: expected_cost(t, size_bytes, prob_access) for t in tiers}
    
    best_tier = min(costs, key=costs.get)
    
    return {
        'class': best_tier,
        'probability': prob_access,
        'reason': f"Lowest expected cost: ${costs[best_tier]:.6f}",
        'costs': costs
    }

def lambda_handler(event, context):
    logger.info(f"Received event: {json.dumps(event)}")
    
    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        key = urllib.parse.unquote_plus(record['s3']['object']['key'])
        size = record['s3']['object']['size']
        
        scan_id = key.split('/')[-1].split('.')[0]
        logger.info(f"Processing scan_id: {scan_id} from bucket: {bucket}")
        
        try:
            # Fetch metadata from DynamoDB
            response = table.get_item(Key={'scan_id': scan_id})
            if 'Item' not in response:
                logger.warning(f"Metadata not found for scan_id: {scan_id}. Using default.")
                item = {
                    'scan_id': scan_id,
                    'object_size_bytes': size
                }
            else:
                item = response['Item']
                
            embedding = item.get('embedding', [])
            if not embedding:
                logger.warning(f"No embedding found for {scan_id}, predicting from metadata only.")
                
            # Update object size if not present
            item['object_size_bytes'] = size
            
            # Predict Tier
            prediction = predict_tier(item, embedding)
            chosen_tier = prediction['class']
            
            # Write S3 object tag
            s3_client.put_object_tagging(
                Bucket=bucket,
                Key=key,
                Tagging={
                    'TagSet': [
                        {
                            'Key': 'tier',
                            'Value': chosen_tier
                        }
                    ]
                }
            )
            
            # Write decision record to DynamoDB
            timestamp = datetime.now(timezone.utc).isoformat()
            table.update_item(
                Key={'scan_id': scan_id},
                UpdateExpression="set predicted_class=:c, probability=:p, reason=:r, decision_timestamp=:t, object_size_bytes=:s",
                ExpressionAttributeValues={
                    ':c': chosen_tier,
                    ':p': str(prediction['probability']),
                    ':r': prediction['reason'],
                    ':t': timestamp,
                    ':s': size
                }
            )
            
            # Emit CloudWatch custom metric
            cloudwatch.put_metric_data(
                Namespace='SmartStorage',
                MetricData=[
                    {
                        'MetricName': 'TierAssigned',
                        'Dimensions': [
                            {'Name': 'Tier', 'Value': chosen_tier}
                        ],
                        'Value': 1,
                        'Unit': 'Count'
                    }
                ]
            )
            
            # Check if wrongly archived
            if chosen_tier in ['GLACIER', 'DEEP_ARCHIVE'] and prediction['probability'] > 0.8:
                # E.g., model predicts high access, but cost function chose archive? Or this is simulated feedback.
                if SNS_TOPIC_ARN:
                    sns.publish(
                        TopicArn=SNS_TOPIC_ARN,
                        Subject='Wrongly Archived Scan',
                        Message=f"Scan {scan_id} was assigned to {chosen_tier} despite high access probability ({prediction['probability']})."
                    )
            
            logger.info(f"Successfully processed {scan_id}. Assigned tier: {chosen_tier}")
            
        except Exception as e:
            logger.error(f"Error processing {scan_id}: {str(e)}", exc_info=True)
            # Emit failure metric
            cloudwatch.put_metric_data(
                Namespace='SmartStorage',
                MetricData=[
                    {
                        'MetricName': 'InferenceFailure',
                        'Value': 1,
                        'Unit': 'Count'
                    }
                ]
            )
            raise e
            
    return {
        'statusCode': 200,
        'body': json.dumps('Inference completed successfully.')
    }
