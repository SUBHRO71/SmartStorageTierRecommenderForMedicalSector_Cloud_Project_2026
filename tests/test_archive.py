import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import nibabel as nib
import numpy as np
from flask import Flask
from werkzeug.datastructures import MultiDict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/backend"))
from archive import Archive, policy
from archive_routes import create_archive_blueprint


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        self.env = patch.dict(os.environ, {"ARCHIVE_DB_PATH": str(self.path / "archive.db"), "ARCHIVE_DATA_DIR": str(self.path / "files")})
        self.env.start()
        self.app = Flask(__name__)
        self.app.register_blueprint(create_archive_blueprint())
        self.client = self.app.test_client()
        self.archive = Archive()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def seed(self):
        self.assertEqual(self.client.post('/api/archive/demo').status_code, 201)
        return self.archive.get('DEMO-001')

    def nifti_payload(self, clinical='subject_id,diagnosis,age\nTEST-01,Glioma,41\n'):
        volume = self.path / 'fixture.nii'
        nib.save(nib.Nifti1Image(np.random.default_rng(42).normal(size=(16, 16, 16)).astype('float32'), np.eye(4)), volume)
        data = {'subject': 'TEST-01', 'collection': 'Synthetic file fixture', 'license': 'Test-only synthetic data',
                'clinical': (io.BytesIO(clinical.encode()), 'clinical.csv')}
        for role in ('T1', 'T1ce', 'T2', 'FLAIR'):
            data[role] = (io.BytesIO(volume.read_bytes()), role + '.nii')
        return data

    def test_empty_then_explicit_idempotent_sample(self):
        self.assertEqual(self.client.get('/api/archive/studies').json['summary']['studies'], 0)
        self.seed()
        self.assertEqual(self.client.post('/api/archive/demo').json['imported'], 0)
        payload = self.client.get('/api/archive/studies').json
        self.assertEqual(payload['summary']['studies'], 12)
        self.assertEqual(payload['summary']['synthetic'], 12)
        self.assertTrue(all(s['analysis']['status'] == 'NOT_RUN' for s in payload['studies']))
        self.assertTrue(all(not o['has_pixels'] for s in payload['studies'] for o in s['objects']))

    def test_constraints_and_failed_analysis_never_archive(self):
        self.seed()
        for identifier in ('DEMO-001', 'DEMO-004', 'DEMO-007', 'DEMO-009'):
            self.assertEqual(policy(self.archive.get(identifier))['tier'], 'STANDARD')
        study = self.archive.get('DEMO-008')
        study['access']['max_hours'] = 0
        decision = policy(study)
        self.assertFalse(any(c['eligible'] for c in decision['candidates'] if c['tier'] in ('GLACIER','DEEP_ARCHIVE')))
        study['analysis']['status'] = 'FAILED'
        self.assertEqual(policy(study)['tier'], 'STANDARD')

    def test_stale_placement_is_rejected_and_bundle_restore_recorded(self):
        self.seed()
        study = self.archive.get('DEMO-008')
        response = self.client.post('/api/archive/studies/DEMO-008/placement', json={'version':0,'reason':'Test scenario'})
        self.assertEqual(response.status_code, 400)
        response = self.client.post('/api/archive/studies/DEMO-008/placement', json={'version':study['version'],'reason':'Test scenario'})
        self.assertEqual(response.status_code, 200)
        placed = response.json['study']
        self.assertTrue(all(o['tier'] == placed['requested_tier'] for o in placed['objects']))
        response = self.client.post('/api/archive/studies/DEMO-008/restore', json={'version':placed['version']})
        self.assertEqual(response.status_code, 200)
        self.assertIn(response.json['study']['restore'], ('AVAILABLE_LOCAL','NOT_REQUIRED'))
        self.assertEqual(len(self.archive.events('DEMO-008')), 3)

    def test_import_exact_clinical_join_measured_sizes_and_real_preview(self):
        response = self.client.post('/api/archive/import', data=self.nifti_payload(), content_type='multipart/form-data')
        self.assertEqual(response.status_code, 201, response.json)
        study = response.json['study']
        self.assertEqual(study['clinical']['status'], 'VERIFIED')
        self.assertEqual(study['clinical']['fields']['age'], '41')
        self.assertTrue(study['complete'])
        self.assertTrue(all(o['sha256'] and o['bytes'] > 0 and o['has_pixels'] for o in study['objects']))
        self.assertTrue(all('file' not in o for o in study['objects']))
        preview = self.client.get(f"/api/archive/studies/{study['id']}/preview/T1?plane=coronal&slice=0.5")
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.mimetype, 'image/png')
        self.assertTrue(preview.data.startswith(b'\x89PNG'))

    def test_duplicate_clinical_rows_are_ambiguous_not_verified(self):
        response = self.client.post('/api/archive/import', data=self.nifti_payload('subject_id,diagnosis\nTEST-01,A\nTEST-01,B\n'), content_type='multipart/form-data')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['study']['clinical']['status'], 'AMBIGUOUS')
        self.assertEqual(response.json['study']['decision']['tier'], 'STANDARD')

    def test_input_and_workload_validation(self):
        self.seed()
        self.assertEqual(self.client.post('/api/archive/studies/DEMO-001/analyze', json={'preprocessed':True}).status_code,400)
        self.assertEqual(self.client.get('/api/archive/costs?accesses=nan').status_code,400)
        self.assertEqual(self.client.get('/api/archive/costs?horizon=-2').status_code,400)
        self.assertEqual(self.client.get('/api/archive/studies/DOES-NOT-EXIST').status_code,404)
        self.assertEqual(self.client.patch('/api/archive/studies/DEMO-001/access',json={'hold':'false','active':False,'max_hours':0,'reason':'Bad type'}).status_code,400)

    def test_component_totals_and_missing_sequence_rejection(self):
        self.seed()
        response = self.client.get('/api/archive/costs?horizon=6&accesses=4')
        self.assertEqual(response.status_code,200)
        for candidate in response.json['policies']:
            self.assertAlmostEqual(candidate['cost'],sum(candidate['components'].values()))
        self.assertEqual(self.client.post('/api/archive/studies/DEMO-004/analyze',json={'preprocessed':True}).status_code,400)

    def test_malformed_files_do_not_create_partial_studies(self):
        payload = {'subject':'TEST-01','collection':'Fixture','license':'Synthetic test only','T1':(io.BytesIO(b'not a nifti file'),'bad.nii')}
        response = self.client.post('/api/archive/import',data=payload,content_type='multipart/form-data')
        self.assertEqual(response.status_code,400)
        self.assertEqual(self.archive.studies(),[])
        self.assertFalse(list((self.path/'files').glob('*')))

    def test_dicom_header_subject_and_study_integrity(self):
        import pydicom
        from pydicom.dataset import FileDataset, FileMetaDataset
        from pydicom.uid import ExplicitVRLittleEndian, MRImageStorage, generate_uid
        def dicom(subject, study_uid):
            meta = FileMetaDataset()
            meta.TransferSyntaxUID = ExplicitVRLittleEndian
            meta.MediaStorageSOPClassUID = MRImageStorage
            meta.MediaStorageSOPInstanceUID = generate_uid()
            dataset = FileDataset(None, {}, file_meta=meta, preamble=b'\0'*128)
            dataset.PatientID = subject
            dataset.StudyInstanceUID = study_uid
            dataset.SeriesInstanceUID = generate_uid()
            dataset.Modality = 'MR'
            dataset.Rows = 64
            dataset.Columns = 64
            dataset.PixelSpacing = [1,1]
            stream = io.BytesIO()
            pydicom.dcmwrite(stream,dataset,enforce_file_format=True)
            stream.seek(0)
            return stream
        uid = generate_uid()
        data = {'subject':'TEST-01','collection':'DICOM fixture','license':'Synthetic test only','T1':(dicom('TEST-01',uid),'test.dcm')}
        response = self.client.post('/api/archive/import',data=data,content_type='multipart/form-data')
        self.assertEqual(response.status_code,201,response.json)
        self.assertEqual(response.json['study']['objects'][0]['geometry']['study_uid'],uid)
        self.assertEqual(response.json['study']['objects'][0]['geometry']['rows'],64)
        bad = {'subject':'TEST-01','collection':'DICOM fixture','license':'Synthetic test only','T1':(dicom('OTHER',uid),'bad.dcm')}
        self.assertEqual(self.client.post('/api/archive/import',data=bad,content_type='multipart/form-data').status_code,400)
        self.assertEqual(len(self.archive.studies()),1)

    def test_v2_cloud_is_explicitly_gated(self):
        cloud = Flask('cloud')
        cloud.register_blueprint(create_archive_blueprint(True))
        self.assertEqual(cloud.test_client().get('/api/archive/studies').status_code,501)

    def test_worker_preserves_current_access_and_recovers_interruption(self):
        study = self.seed()
        study['access']['hold'] = True
        study['analysis']['status'] = 'RUNNING'
        self.archive.save(study,'ANALYSIS_STARTED')
        self.archive.recover_interrupted_analysis()
        recovered = self.archive.get(study['id'])
        self.assertEqual(recovered['analysis']['status'],'FAILED')
        self.assertTrue(recovered['access']['hold'])
        self.assertEqual(recovered['decision']['tier'],'STANDARD')


if __name__ == '__main__':
    unittest.main()
