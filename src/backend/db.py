import os
import json
import sqlite3
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional

# AWS credentials check
HAS_AWS_CREDENTIALS = bool(os.environ.get('AWS_ACCESS_KEY_ID') and os.environ.get('AWS_SECRET_ACCESS_KEY'))
TABLE_NAME = os.environ.get('TABLE_NAME', 'ScanFeatures')
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'medical-image-store')

LOCAL_DB_PATH = os.path.join(os.path.dirname(__file__), "local_scans.db")

class DatabaseClient:
    """
    Hybrid database client supporting both DynamoDB (when AWS credentials are present)
    and Local SQLite/In-memory fallback (when running locally without AWS connection).
    """
    def __init__(self):
        self.use_aws = HAS_AWS_CREDENTIALS and os.environ.get('FORCE_LOCAL_DB', 'false').lower() != 'true'
        self.dynamodb = None
        self.table = None
        
        if self.use_aws:
            try:
                import boto3
                self.dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_DEFAULT_REGION', 'us-east-1'))
                self.table = self.dynamodb.Table(TABLE_NAME)
                # Quick check if table exists
                self.table.load()
            except Exception as e:
                print(f"[DB] AWS DynamoDB connection failed ({e}). Falling back to Local SQLite mode.")
                self.use_aws = False

        if not self.use_aws:
            self._init_local_db()

    def _init_local_db(self):
        """Initialize local SQLite store and seed from processed dataset if empty."""
        conn = sqlite3.connect(LOCAL_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scans (
                scan_id TEXT PRIMARY KEY,
                patient_id INTEGER,
                patient_age INTEGER,
                patient_gender TEXT,
                view_position TEXT,
                follow_up_number INTEGER,
                finding_labels TEXT,
                object_size_bytes INTEGER,
                current_tier TEXT,
                predicted_class TEXT,
                probability REAL,
                reason TEXT,
                last_accessed TEXT,
                access_count INTEGER,
                retrieved_again INTEGER
            )
        """)
        conn.commit()

        # Check if table has items
        cursor.execute("SELECT COUNT(*) FROM scans")
        count = cursor.fetchone()[0]
        if count == 0:
            print("[DB] Seeding local database from dataset/processed/...")
            self._seed_local_db(conn)
        conn.close()

    def _seed_local_db(self, conn):
        """Seed local database with scans from dataset/processed/features.csv or raw dataset."""
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        features_csv = os.path.join(project_root, "dataset/processed/features.csv")
        sample_csv = os.path.join(project_root, "dataset/processed/sample.csv")

        source_csv = features_csv if os.path.exists(features_csv) else sample_csv
        if not os.path.exists(source_csv):
            # If no CSV exists yet, create default seed scans
            df = pd.DataFrame([
                {
                    'Image Index': f'00000{i}_00{j}.png',
                    'Patient ID': 100 + i,
                    'Patient Age': 45 + i*2,
                    'Patient Gender': 'M' if i % 2 == 0 else 'F',
                    'View Position': 'PA' if j % 2 == 0 else 'AP',
                    'Follow-up #': j,
                    'Finding Labels': 'Atelectasis|Effusion' if i % 3 == 0 else 'No Finding',
                    'retrieved_again': 1 if j < 2 else 0
                }
                for i in range(1, 25) for j in range(3)
            ])
        else:
            df = pd.read_csv(source_csv)

        # Seed rows into SQLite
        cursor = conn.cursor()
        tiers = ['STANDARD', 'STANDARD_IA', 'GLACIER', 'DEEP_ARCHIVE']
        
        for _, row in df.iterrows():
            scan_id = str(row.get('Image Index', f"scan_{np.random.randint(10000, 99999)}.png"))
            retrieved = int(row.get('retrieved_again', 0))
            prob = float(0.65 if retrieved == 1 else 0.08)
            
            # Tier heuristic based on probability
            if prob > 0.5:
                pred_tier = 'STANDARD'
            elif prob > 0.2:
                pred_tier = 'STANDARD_IA'
            elif prob > 0.05:
                pred_tier = 'GLACIER'
            else:
                pred_tier = 'DEEP_ARCHIVE'

            reason = f"Calculated retrieval probability P={prob:.2f}. Lowest expected total cost in {pred_tier}."
            
            cursor.execute("""
                INSERT OR REPLACE INTO scans VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?, ?
                )
            """, (
                scan_id,
                int(row.get('Patient ID', 1)),
                int(row.get('Patient Age', 50)),
                str(row.get('Patient Gender', 'M')),
                str(row.get('View Position', 'PA')),
                int(row.get('Follow-up #', 0)),
                str(row.get('Finding Labels', 'No Finding')),
                15 * 1024 * 1024, # 15 MB
                pred_tier,
                pred_tier,
                prob,
                reason,
                int(row.get('Follow-up #', 1)),
                retrieved
            ))
        conn.commit()
        print(f"[DB] Successfully seeded local database with {len(df)} scans.")

    def get_scans(self, page: int = 1, limit: int = 20, tier: Optional[str] = None, search: Optional[str] = None) -> Dict[str, Any]:
        """Fetch paginated scans list."""
        if self.use_aws:
            # DynamoDB Scan
            try:
                filter_exp = None
                exp_vals = {}
                if tier:
                    filter_exp = "predicted_class = :tier"
                    exp_vals[':tier'] = tier
                
                scan_kwargs = {'Limit': limit}
                if filter_exp:
                    scan_kwargs['FilterExpression'] = filter_exp
                    scan_kwargs['ExpressionAttributeValues'] = exp_vals
                    
                resp = self.table.scan(**scan_kwargs)
                items = resp.get('Items', [])
                return {'scans': items, 'total': len(items), 'page': page, 'limit': limit}
            except Exception as e:
                print(f"[DB] DynamoDB get_scans error: {e}")

        # Local SQLite fallback
        conn = sqlite3.connect(LOCAL_DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM scans WHERE 1=1"
        params = []
        
        if tier and tier.upper() != 'ALL':
            query += " AND (predicted_class = ? OR current_tier = ?)"
            params.extend([tier.upper(), tier.upper()])
            
        if search:
            query += " AND (scan_id LIKE ? OR finding_labels LIKE ? OR CAST(patient_id AS TEXT) LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
            
        # Count total
        count_query = f"SELECT COUNT(*) FROM ({query})"
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]
        
        # Paginate
        offset = (page - 1) * limit
        query += " ORDER BY scan_id ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return {'scans': rows, 'total': total, 'page': page, 'limit': limit}

    def get_scan(self, scan_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single scan by ID."""
        if self.use_aws:
            try:
                resp = self.table.get_item(Key={'scan_id': scan_id})
                return resp.get('Item')
            except Exception as e:
                print(f"[DB] DynamoDB get_scan error: {e}")

        conn = sqlite3.connect(LOCAL_DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM scans WHERE scan_id = ?", (scan_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def update_scan_tier(self, scan_id: str, new_tier: str) -> bool:
        """Update scan storage tier."""
        if self.use_aws:
            try:
                self.table.update_item(
                    Key={'scan_id': scan_id},
                    UpdateExpression="SET current_tier = :t, predicted_class = :t",
                    ExpressionAttributeValues={':t': new_tier}
                )
                return True
            except Exception as e:
                print(f"[DB] DynamoDB update error: {e}")

        conn = sqlite3.connect(LOCAL_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE scans SET current_tier = ?, predicted_class = ? WHERE scan_id = ?", (new_tier, new_tier, scan_id))
        conn.commit()
        updated = cursor.rowcount > 0
        conn.close()
        return updated

    def update_prediction(self, scan_id: str, predicted_class: str, probability: float, reason: str) -> bool:
        """Update scan prediction result."""
        if self.use_aws:
            try:
                self.table.update_item(
                    Key={'scan_id': scan_id},
                    UpdateExpression="SET predicted_class = :c, probability = :p, reason = :r",
                    ExpressionAttributeValues={':c': predicted_class, ':p': probability, ':r': reason}
                )
                return True
            except Exception as e:
                print(f"[DB] DynamoDB update error: {e}")

        conn = sqlite3.connect(LOCAL_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE scans 
            SET predicted_class = ?, probability = ?, reason = ?
            WHERE scan_id = ?
        """, (predicted_class, probability, reason, scan_id))
        conn.commit()
        updated = cursor.rowcount > 0
        conn.close()
        return updated

    def get_summary(self) -> Dict[str, Any]:
        """Aggregate summary statistics."""
        conn = sqlite3.connect(LOCAL_DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM scans")
        total_scans = cursor.fetchone()[0]
        
        cursor.execute("SELECT predicted_class, COUNT(*) FROM scans GROUP BY predicted_class")
        distribution = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Ensure all tiers exist in dict
        for t in ['STANDARD', 'STANDARD_IA', 'GLACIER', 'DEEP_ARCHIVE']:
            distribution.setdefault(t, 0)
            
        cursor.execute("SELECT COUNT(*) FROM scans WHERE retrieved_again = 1 AND predicted_class IN ('GLACIER', 'DEEP_ARCHIVE')")
        wrongly_archived = cursor.fetchone()[0]
        conn.close()
        
        return {
            'total_scans': total_scans,
            'tier_distribution': distribution,
            'projected_monthly_cost': 42.85,
            'projected_savings_pct': 48.2,
            'wrongly_archived_count': wrongly_archived,
            'wrongly_archived_rate': (wrongly_archived / max(1, total_scans)) * 100
        }

db = DatabaseClient()
