import React from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { MagnifyingGlassIcon, ArrowUpTrayIcon } from '@heroicons/react/24/outline';
import { useArchive, tiers } from './ArchiveContext';
import { ArchiveGate, PageHeading, StudyTable } from './ArchiveUI';

export default function Studies() {
  const { studies } = useArchive();
  const [params, setParams] = useSearchParams();
  const complete = params.get('coverage') || 'all';
  const clinical = params.get('clinical') || 'all';
  const tier = params.get('tier') || 'all';
  const page = Math.max(1, Number(params.get('page')) || 1);
  const update = (key, value) => {
    const next = new URLSearchParams(params);
    if (!value || value === 'all') next.delete(key); else next.set(key, value);
    next.delete('page');
    setParams(next);
  };
  const setPage = value => { const next = new URLSearchParams(params); next.set('page', value); setParams(next); };
  const query = params.get('q') || '';
  const filtered = studies.filter(s => `${s.id} ${s.subject} ${s.collection}`.toLowerCase().includes(query.toLowerCase()) && (complete === 'all' || s.complete === (complete === 'complete')) && (clinical === 'all' || (s.clinical.status === 'VERIFIED') === (clinical === 'linked')) && (tier === 'all' || s.objects.some(o => o.tier === tier)));
  const totalPages = Math.max(1, Math.ceil(filtered.length / 8));
  const current = Math.min(page, totalPages);
  const clear = () => setParams({});
  return <ArchiveGate><PageHeading title="Study explorer" description="Find complete studies. Inspect the details that matter."><Link className="button primary" to="/import"><ArrowUpTrayIcon />Import study</Link></PageHeading><div className="filter-bar"><label className="search-field"><MagnifyingGlassIcon /><input aria-label="Search studies" placeholder="Search study or subject ID" value={query} onChange={e => { update('q',e.target.value); }} /></label><label>MRI coverage<select value={complete} onChange={e => { update('coverage',e.target.value); }}><option value="all">All sequence sets</option><option value="complete">Complete</option><option value="missing">Missing sequences</option></select></label><label>Clinical link<select value={clinical} onChange={e => { update('clinical',e.target.value); }}><option value="all">All clinical states</option><option value="linked">Linked</option><option value="review">Needs review</option></select></label><label>Storage tier<select value={tier} onChange={e => { update('tier',e.target.value); }}><option value="all">All tiers</option>{Object.entries(tiers).map(([key, t]) => <option key={key} value={key}>{t.label}</option>)}</select></label><button className="text-button" onClick={clear}>Clear filters</button></div><section className="panel"><div className="section-heading"><h2>{filtered.length} {filtered.length === 1 ? 'study' : 'studies'}</h2><span className="subtle-label">Results within the selected collection</span></div><StudyTable studies={filtered.slice((current - 1) * 8, current * 8)} /><div className="pagination"><span>Page {current} of {totalPages}</span><div><button className="button secondary" disabled={current <= 1} onClick={() => setPage(current - 1)}>Previous</button><button className="button secondary" disabled={current >= totalPages} onClick={() => setPage(current + 1)}>Next</button></div></div></section></ArchiveGate>;
}
