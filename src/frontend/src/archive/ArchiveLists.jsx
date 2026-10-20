import React, { useState } from 'react';
import { cloudMode } from '../runtime';
import { Link } from 'react-router-dom';
import { ArrowRightIcon, CheckCircleIcon } from '@heroicons/react/24/outline';
import { displayTime, useArchive } from './ArchiveContext';
import { ArchiveGate, PageHeading, Status } from './ArchiveUI';

export function Quality() {
  const { summary } = useArchive();
  const [filter, setFilter] = useState('all');
  const issues = (summary?.issues || []).filter(i => filter === 'all' || i.kind === filter);
  return <ArchiveGate><PageHeading title="Data quality" description="A usable study starts with trustworthy inputs." /><div className="segmented-control" aria-label="Issue filter">{[['all', 'All issues'], ['sequence', 'MRI coverage'], ['clinical', 'Clinical linkage'], ['hold', 'Access holds'], ['analysis', 'Analysis']].map(([key, name]) => <button key={key} aria-pressed={filter === key} className={filter === key ? 'selected' : ''} onClick={() => setFilter(key)}>{name}</button>)}</div><section className="panel"><div className="section-heading"><h2>{issues.length} items to inspect</h2><span className="subtle-label">Manual holds are protection, not data errors.</span></div>{issues.map(i => <Link className="quality-row" key={`${i.study_id}-${i.kind}`} to={`/studies/${i.study_id}`}><div><strong>{i.title}</strong><p>{i.kind === 'sequence' ? 'Confirm all four sequence roles before model analysis.' : i.kind === 'clinical' ? 'Clinical records need an exact match in the source subject namespace.' : i.kind === 'analysis' ? 'Inspect input quality and model run details before retrying.' : 'Review the access requirement and the reason for this hold.'}</p></div><Status tone={i.kind === 'hold' ? 'neutral' : 'attention'}>{i.study_id}</Status><ArrowRightIcon /></Link>)}{!issues.length && <div className="empty-panel small"><CheckCircleIcon /><h3>No issues in this filter.</h3><p>Choose another category to inspect its records.</p></div>}</section></ArchiveGate>;
}

export function Operations() {
  const { data, studies } = useArchive();
  const events = (data?.events || []).filter(e => studies.some(s => s.id === e.study_id));
  return <ArchiveGate><PageHeading title="Operations" description="A visible trail from import to placement and restore." /><div className="notice"><strong>{cloudMode ? 'AWS execution' : 'Local execution'}</strong><span>{cloudMode ? 'S3 member states are reconciled every five minutes. Requested placement remains pending until S3 confirms every member.' : 'Placement and restore events here simulate a complete bundle. No AWS objects are moved.'}</span></div><section className="panel"><div className="section-heading"><h2>Operation history</h2><span className="subtle-label">Latest 100 archive events</span></div>{events.map(e => <div className="operation-row" key={e.id}><span className="timeline-dot" /><div><Link to={`/studies/${e.study_id}`}>{e.kind.replaceAll('_', ' ').toLowerCase()}</Link><p>{e.details.message}</p><small>{e.study_id} · Version {e.details.version}</small></div><time dateTime={e.created}>{displayTime(e.created)}</time></div>)}{!events.length && <div className="table-empty">Import a study to start the operation history.</div>}</section></ArchiveGate>;
}
