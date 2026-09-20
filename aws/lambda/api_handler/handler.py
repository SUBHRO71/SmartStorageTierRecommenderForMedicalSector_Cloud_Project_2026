import json
import os
import boto3
import logging
from decimal import Decimal

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
s3 = boto3.client('s3')

TABLE_NAME = os.environ.get('TABLE_NAME', 'ScanFeatures')
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'medical-image-store')
table = dynamodb.Table(TABLE_NAME)

def build_response(status_code, body):
    """Helper to build HTTP response with CORS."""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'OPTIONS,GET,POST,PUT,DELETE',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization'
        },
        'body': json.dumps(body, cls=DecimalEncoder)
    }

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def get_scans(event):
    query_params = event.get('queryStringParameters') or {}
    limit = int(query_params.get('limit', 20))
    tier = query_params.get('tier')
    
    # Full scan (not recommended for large tables, but okay for MVP API)
    try:
        if tier:
            response = table.scan(
                FilterExpression='predicted_class = :tier',
                ExpressionAttributeValues={':tier': tier},
                Limit=limit
            )
        else:
            response = table.scan(Limit=limit)
            
        items = response.get('Items', [])
        return build_response(200, {
            'scans': items,
            'total': len(items), # approximate without counting whole table
            'page': 1
        })
    except Exception as e:
        logger.error(f"Error fetching scans: {e}")
        return build_response(500, {'error': 'Internal server error'})

def get_scan(event):
    scan_id = event['pathParameters']['id']
    try:
        response = table.get_item(Key={'scan_id': scan_id})
        if 'Item' not in response:
            return build_response(404, {'error': 'Scan not found'})
        return build_response(200, response['Item'])
    except Exception as e:
        logger.error(f"Error fetching scan {scan_id}: {e}")
        return build_response(500, {'error': 'Internal server error'})

def predict_scan(event):
    scan_id = event['pathParameters']['id']
    return build_response(200, {'message': f'Prediction triggered for {scan_id}', 'class': 'STANDARD_IA'})

def get_costs(event):
    # Dummy implementation for cost summary
    return build_response(200, {
        'our_model': 120.50,
        'baseline_standard': 250.00,
        'baseline_age': 200.00,
        'baseline_intelligent': 180.00,
        'wrongly_archived_rate': 0.05
    })

def override_tier(event):
    scan_id = event['pathParameters']['id']
    try:
        body = json.loads(event.get('body', '{}'))
        new_tier = body.get('tier')
        if not new_tier:
            return build_response(400, {'error': 'Tier is required'})
            
        # Update DynamoDB
        response = table.get_item(Key={'scan_id': scan_id})
        if 'Item' not in response:
            return build_response(404, {'error': 'Scan not found'})
            
        previous_tier = response['Item'].get('predicted_class')
        
        table.update_item(
            Key={'scan_id': scan_id},
            UpdateExpression="set predicted_class=:t",
            ExpressionAttributeValues={':t': new_tier}
        )
        
        # In a real app, you would also update S3 tag here
        
        return build_response(200, {
            'success': True,
            'previous_tier': previous_tier,
            'new_tier': new_tier
        })
    except Exception as e:
        logger.error(f"Error updating tier: {e}")
        return build_response(500, {'error': 'Internal server error'})

def get_dashboard_summary(event):
    return build_response(200, {
        'total_scans': 1000,
        'tier_distribution': {
            'STANDARD': 200,
            'STANDARD_IA': 300,
            'GLACIER': 400,
            'DEEP_ARCHIVE': 100
        },
        'projected_monthly_cost': 120.50,
        'wrongly_archived_count': 5
    })

def lambda_handler(event, context):
    logger.info(f"API Request: {event.get('httpMethod')} {event.get('resource')}")
    
    path = event.get('resource', '')
    method = event.get('httpMethod', '')
    
    if method == 'OPTIONS':
        return build_response(200, {})
        
    try:
        if path == '/api/scans' and method == 'GET':
            return get_scans(event)
        elif path == '/api/scans/{id}' and method == 'GET':
            return get_scan(event)
        elif path == '/api/scans/{id}/predict' and method == 'POST':
            return predict_scan(event)
        elif path == '/api/costs' and method == 'GET':
            return get_costs(event)
        elif path == '/api/scans/{id}/tier' and method == 'POST':
            return override_tier(event)
        elif path == '/api/dashboard/summary' and method == 'GET':
            return get_dashboard_summary(event)
        else:
            return build_response(404, {'error': 'Not found'})
    except Exception as e:
        logger.error(f"Unhandled error: {e}", exc_info=True)
        return build_response(500, {'error': 'Internal server error'})
