import React, { useEffect, useState, useRef } from 'react';

import { Link, useParams, useLocation } from 'react-router-dom';

import { ArrowLeftIcon, ArrowPathIcon, CubeTransparentIcon, ShieldCheckIcon, ArrowDownTrayIcon, CheckCircleIcon } from '@heroicons/react/24/outline';

import { archiveApi, bytes, displayTime, money, messageOf, sequenceRoles, tiers, useArchive } from './ArchiveContext';

import { PageHeading, SequenceSet, Status, TierLabel } from './ArchiveUI';



function VolumePreview({ study, role, plane, slice, overlay, opacity, active }) {

  const [error, setError] = useState(false);

  const object = study.objects.find(o => o.role === role);

  const url = `${archiveApi.defaults.baseURL}/studies/${study.id}/preview/${role}?plane=${plane}&slice=${slice}&overlay=${overlay}&opacity=${opacity}`;

  useEffect(() => setError(false), [url]);

  return <div className={`volume-preview ${active ? 'active-sequence' : ''}`}><span className="volume-label">{role}</span>{object?.has_pixels && object.format === 'NIfTI' && !error ? <img src={url} alt={`${role} ${plane} MRI slice`} onError={() => setError(true)} /> : <div className="volume-empty"><CubeTransparentIcon /><span>{!object ? 'Sequence missing' : object.format === 'DICOM' ? 'DICOM series imported' : error ? 'Preview unavailable' : 'No pixels loaded'}</span><small>{object?.format === 'DICOM' ? 'Convert to NIfTI for volume inspection' : 'Import a permitted MRI volume'}</small></div>}<span className="volume-plane">{plane} · {Math.round(slice * 100)}%</span></div>;

}



export default function StudyDetail() {

  const { id } = useParams();

  const location = useLocation();

  const backTo = /^\/studies(?:\?|$)/.test(location.state?.from || '') ? location.state.from : '/studies';

  const reviewRef = useRef(null), reviewButtonRef = useRef(null);

  const [selectedRole, setSelectedRole] = useState('T1');

  const { refresh } = useArchive();

  const [study, setStudy] = useState(null), [events, setEvents] = useState([]);

  const [error, setError] = useState(''), [busy, setBusy] = useState(false), [notice, setNotice] = useState('');

  const [tab, setTab] = useState('clinical'), [plane, setPlane] = useState('axial'), [slice, setSlice] = useState(.5);

  const [overlay, setOverlay] = useState('none'), [opacity, setOpacity] = useState(.4);

  const [preprocessed, setPreprocessed] = useState(false), [reason, setReason] = useState('');

  const [access, setAccess] = useState({ hold: false, active: false, max_hours: '' });

  const [review, setReview] = useState(false), [placementReason, setPlacementReason] = useState('');

  useEffect(() => {

    if (review && reviewRef.current) {

      reviewRef.current.focus({preventScroll:true});

      reviewRef.current.scrollIntoView({behavior:'instant',block:'start'});

    }

  }, [review]);

  const load = async () => { try { const { data } = await archiveApi.get(`/studies/${id}`); setStudy(data.study); setEvents(data.events); setAccess({ ...data.study.access, max_hours: data.study.access.max_hours ?? '' }); } catch(e) { setError(messageOf(e)); } };

  useEffect(() => { setStudy(null); setError(''); load(); }, [id]);

  useEffect(() => { if (study?.analysis.status !== 'RUNNING') return; const timer = setInterval(load, 3000); return () => clearInterval(timer); }, [study?.analysis.status, id]);

  const action = async (suffix, payload, verb = 'post') => { setBusy(true); setError(''); setNotice(''); try { const { data } = await archiveApi[verb](`/studies/${id}/${suffix}`, { ...payload, version: study.version }); setStudy(data.study); setReview(false); await load(); await refresh(); setNotice(suffix === 'restore' ? 'All required members are available in the local restore simulation.' : suffix === 'placement' ? 'Study placement was updated in the local simulation.' : suffix === 'analyze' ? 'MRI analysis started. This page will track the result.' : 'Study updated and recorded in the audit history.'); } catch(e) { setError(messageOf(e)); } finally { setBusy(false); } };

  if (!study) return <div className="empty-panel" role={error ? 'alert' : 'status'}><ArrowPathIcon className={error ? '' : 'spin'} /><h2>{error ? 'Unable to open study' : 'Opening study…'}</h2>{error && <><p>{error}</p><button className="button primary" onClick={load}>Try again</button></>}</div>;

  const observed = [...new Set(study.objects.map(o => o.tier))];

  const canAnalyze = study.complete && study.objects.every(o => o.has_pixels && o.format === 'NIfTI');

  return <><Link to={backTo} className="back-link"><ArrowLeftIcon />Back to studies</Link><PageHeading title={study.id} description={`${study.subject} · ${study.collection} · ${study.release}`}><Status tone={study.source === 'SYNTHETIC' ? 'attention' : 'success'}>{study.source === 'SYNTHETIC' ? 'Synthetic sample' : 'Imported study'}</Status><button className="button secondary" disabled={busy} onClick={() => action('restore', {})}><ArrowDownTrayIcon />Simulate restore</button></PageHeading><div className="study-state-strip"><SequenceSet study={study} /><span>{bytes(study.objects.reduce((n,o) => n+o.bytes,0))} · {study.objects.length} objects</span><TierLabel value={observed.length === 1 ? observed[0] : 'Mixed'} /><Status>Restore: {study.restore.replaceAll('_', ' ').toLowerCase()}</Status></div>{error && <p className="error-box" role="alert">{error}</p>}{notice && <p className="success-box" role="status"><CheckCircleIcon />{notice}</p>}<div className="study-workspace"><section className="viewer-panel"><div className="viewer-heading"><div><h2>MRI workbench</h2><p>{study.source === 'SYNTHETIC' ? 'Sample metadata · no MRI imagery' : 'Uploaded volumes · research preview'}</p></div><CubeTransparentIcon /></div><label className="mobile-sequence-picker">MRI sequence<select aria-label="Displayed MRI sequence" value={selectedRole} onChange={e => setSelectedRole(e.target.value)}>{sequenceRoles.map(role => <option key={role}>{role}</option>)}</select></label><div className="viewer-grid">{sequenceRoles.map(role => <VolumePreview key={role} study={study} role={role} plane={plane} slice={slice} overlay={overlay} opacity={opacity} active={selectedRole === role} />)}</div><div className="viewer-controls"><label>Plane<select value={plane} onChange={e => setPlane(e.target.value)}><option value="axial">Axial</option><option value="coronal">Coronal</option><option value="sagittal">Sagittal</option></select></label><label className="slice-control">Relative slice<input aria-label="MRI slice position" type="range" min="0" max="1" step=".01" value={slice} onChange={e => setSlice(Number(e.target.value))} /></label><span>{Math.round(slice * 100)}%</span></div><div className="overlay-controls"><label>Prediction overlay<select aria-label="Prediction overlay" value={overlay} disabled={study.analysis.status !== 'READY'} onChange={e => setOverlay(e.target.value)}><option value="none">Off</option><option value="WT">Whole tumor (WT)</option><option value="TC">Tumor core (TC)</option><option value="ET">Enhancing tumor (ET)</option></select></label><label>Opacity<input aria-label="Overlay opacity" type="range" min="0" max="1" step=".05" value={opacity} disabled={overlay === 'none'} onChange={e => setOpacity(Number(e.target.value))} /></label><span>Model prediction</span></div><div className="viewer-note">Independent sequence previews. Cross-sequence correspondence requires verified alignment.</div></section><aside className="panel context-panel"><div className="context-tabs" role="tablist" aria-label="Study context">{[['clinical', 'Clinical'], ['metadata', 'Metadata'], ['policy', 'Policy']].map(([key, name]) => <button role="tab" aria-selected={tab === key} id={`tab-${key}`} aria-controls={`panel-${key}`} key={key} className={tab === key ? 'selected' : ''} onClick={() => setTab(key)}>{name}</button>)}</div><div className="context-content" role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>{tab === 'clinical' ? <><h2>Reported clinical fields</h2><Status tone={study.clinical.status === 'VERIFIED' ? 'success' : 'attention'}>{study.clinical.status.toLowerCase()}</Status><dl className="detail-list">{Object.entries(study.clinical.fields).map(([key, value]) => <div key={key}><dt>{key === 'age' ? 'Age at source event' : key}</dt><dd>{value || 'Not reported'}</dd></div>)}</dl>{!Object.keys(study.clinical.fields).length && <p>No matched clinical fields. Inspect the source subject ID and CSV.</p>}<div className="provenance-note"><ShieldCheckIcon /><span>{study.clinical.provenance}</span></div></> : tab === 'metadata' ? <><h2>Study provenance</h2><dl className="detail-list">{[['Subject', study.subject], ['Modality', study.modality], ['Source', study.collection], ['Release', study.release], ['Permission', study.license], ['Study version', study.version]].map(([key,value]) => <div key={key}><dt>{key}</dt><dd>{value}</dd></div>)}</dl><p className="context-help">NIfTI subject relationships are source-declared. Imported DICOM subject IDs are validated against their headers.</p></> : <><h2>Recommended placement</h2><TierLabel value={study.decision.tier} /><p className="decision-reason">{study.decision.reason}</p><div className="decision-meta"><span>{study.decision.horizon}-month scenario</span><span>{study.decision.accesses} expected study accesses</span><span>{study.decision.version}</span></div><button ref={reviewButtonRef} aria-expanded={review} aria-controls="placement-review" className="button primary full-width" onClick={() => setReview(!review)} disabled={busy}>Review local placement</button><button className="text-button" onClick={() => action('recommend', {})} disabled={busy}>Recalculate recommendation</button></>}</div></aside></div><div className="detail-grid"><section className="panel padded"><div className="section-heading"><div><h2>Access comes first</h2><p>These requirements govern eligible storage tiers.</p></div><ShieldCheckIcon /></div><form onSubmit={e => { e.preventDefault(); action('access', { ...access, max_hours: access.max_hours === '' ? null : Number(access.max_hours), reason }, 'patch'); }}><div className="checkbox-row"><label><input type="checkbox" checked={access.active} onChange={e => setAccess({ ...access, active: e.target.checked })} />Active research / follow-up window</label><label><input type="checkbox" checked={access.hold} onChange={e => setAccess({ ...access, hold: e.target.checked })} />Manual hot-storage hold</label></div><div className="form-grid"><label>Maximum wait for complete study<select value={access.max_hours} onChange={e => setAccess({ ...access, max_hours: e.target.value })}><option value="">Not declared — keep Standard</option><option value="0">Immediate access</option><option value="12">Up to 12 hours</option><option value="48">Up to 48 hours</option></select></label><label>Reason for change<input required minLength={3} value={reason} onChange={e => setReason(e.target.value)} placeholder="Describe the access requirement" /></label></div><button className="button secondary" disabled={busy}>Save access requirements</button></form></section><section className="panel padded"><div className="section-heading"><div><h2>MRI analysis</h2><p>Frozen pretrained weights. Inspectable research output.</p></div><Status tone={study.analysis.status === 'READY' ? 'success' : 'neutral'}>{study.analysis.status.replaceAll('_',' ').toLowerCase()}</Status></div><p className="model-name">{study.analysis.model}</p><p>{study.analysis.message}</p>{study.analysis.volumes_mL && <div className="region-volumes">{Object.entries(study.analysis.volumes_mL).map(([name, value]) => <div key={name}><span>{name}</span><strong>{value}<small>mL</small></strong></div>)}</div>}{study.analysis.runtime_seconds && <p className="subtle-label">{study.analysis.runtime_seconds}s · {study.analysis.device} · checkpoint {study.analysis.checkpoint_sha256?.slice(0,12)}</p>}<label className="check-label"><input type="checkbox" disabled={!canAnalyze} checked={preprocessed} onChange={e => setPreprocessed(e.target.checked)} />Volumes are aligned, brain-extracted and on a 1 mm grid.</label><button className="button secondary" disabled={!canAnalyze || !preprocessed || busy || study.analysis.status === 'RUNNING'} onClick={() => action('analyze', { preprocessed })}><ArrowPathIcon />{study.analysis.status === 'RUNNING' ? 'Analysis running…' : 'Run MRI analysis'}</button>{!canAnalyze && <small className="block-help">Import all four NIfTI volumes to enable analysis.</small>}</section></div>{review && <section id="placement-review" className="panel placement-review padded"><h2 ref={reviewRef} tabIndex={-1}>Review the complete bundle</h2><p>This simulates placement of all {study.objects.length} members into {tiers[study.decision.tier].label}. Local image files remain on this machine.</p><table className="candidate-table"><thead><tr><th>Candidate</th><th>Eligibility</th><th>Modeled cost</th></tr></thead><tbody>{study.decision.candidates.map(c => <tr key={c.tier}><td><TierLabel value={c.tier} /></td><td>{c.eligible ? 'Eligible' : 'Blocked by requirement'}</td><td>{money(c.cost)}</td></tr>)}</tbody></table><p className="subtle-label">{study.decision.limitations}</p><label className="review-reason">Placement reason<input value={placementReason} onChange={e => setPlacementReason(e.target.value)} placeholder="Reason for this local placement" /></label><div className="button-row"><button className="button primary" disabled={busy || placementReason.trim().length < 3} onClick={() => action('placement', { reason: placementReason })}>Apply local simulation</button><button className="button secondary" onClick={() => { setReview(false); reviewButtonRef.current?.focus(); }}>Cancel</button></div></section>}<section className="panel"><div className="section-heading"><h2>Sequence & object manifest</h2><span className="subtle-label">Source checksums for imported files</span></div><p className="table-scroll-hint">Scroll horizontally to inspect every object field.</p><div className="table-scroll" role="region" aria-label="Object manifest — scroll horizontally for all columns" tabIndex={0}><table className="manifest-table"><thead><tr><th>Sequence</th><th>Format / geometry</th><th>Bytes</th><th>Integrity</th><th>Observed tier</th></tr></thead><tbody>{study.objects.map(o => <tr key={o.id}><td>{o.role}</td><td>{o.format}<small>{o.geometry?.shape?.join(' × ') || o.geometry?.series_uid || 'Sample metadata only'}</small></td><td>{bytes(o.bytes)}</td><td><span title={o.sha256 || 'No source pixels in sample'}>{o.sha256?.slice(0,16) || 'Not applicable'}</span></td><td><TierLabel value={o.tier} /></td></tr>)}</tbody></table></div></section><section className="panel audit-panel"><div className="section-heading"><h2>Decision & operation history</h2><span className="subtle-label">Append-only local events</span></div>{events.map(e => <div className="audit-row" key={e.id}><span className="timeline-dot" /><div><strong>{e.kind.replaceAll('_',' ').toLowerCase()}</strong><p>{e.details.message}</p></div><time>{displayTime(e.created)}</time></div>)}</section></>;

}
