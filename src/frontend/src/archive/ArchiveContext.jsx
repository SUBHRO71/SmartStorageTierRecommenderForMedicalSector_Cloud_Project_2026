import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import axios from 'axios';

export const archiveApi = axios.create({ baseURL: `${import.meta.env.VITE_API_URL || 'http://127.0.0.1:5000/api'}/archive`, timeout: 30000 });
export const sequenceRoles = ['T1', 'T1ce', 'T2', 'FLAIR'];
export const tiers = { STANDARD: { label: 'Standard', short: 'Standard', color: '#16877c' }, STANDARD_IA: { label: 'Standard-IA', short: 'Standard-IA', color: '#5889c7' }, GLACIER: { label: 'Glacier Flexible', short: 'Glacier', color: '#c49037' }, DEEP_ARCHIVE: { label: 'Deep Archive', short: 'Deep Archive', color: '#8b80b5' } };
export const bytes = value => value >= 1024 ** 3 ? `${(value / 1024 ** 3).toFixed(2)} GiB` : `${(value / 1024 ** 2).toFixed(1)} MiB`;
export const money = value => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: 3 }).format(value || 0);
export const displayTime = (value, compact=false) => new Intl.DateTimeFormat('en-IN', {timeZone:import.meta.env.VITE_DISPLAY_TIMEZONE || 'Asia/Kolkata', ...(compact ? {hour:'2-digit',minute:'2-digit'} : {day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'})}).format(new Date(value));
export const messageOf = error => error.response?.data?.error?.message || error.message || 'Unable to reach the archive. Check the local backend and try again.';
const Context = createContext(null);
export function ArchiveProvider({ children }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [collection, setCollection] = useState('');
  const refresh = useCallback(async () => {
    setError('');
    try { const response = await archiveApi.get('/studies'); setData(response.data); }
    catch (e) { setError(messageOf(e)); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { refresh(); }, [refresh]);
  const allStudies = data?.studies || [];
  const studies = allStudies.filter(s => !collection || s.collection === collection);
  const summary = collection ? { ...data?.summary, studies: studies.length, objects: studies.reduce((sum, s) => sum + s.objects.length, 0), bytes: studies.reduce((sum, s) => sum + s.objects.reduce((n, o) => n + o.bytes, 0), 0), complete: studies.filter(s => s.complete).length, clinical: studies.filter(s => s.clinical.status === 'VERIFIED').length, issues: (data?.summary.issues || []).filter(i => studies.some(s => s.id === i.study_id)), distribution: Object.keys(tiers).map(t => ({ tier: t, bytes: studies.reduce((n,s) => n + s.objects.filter(o => o.tier === t).reduce((v,o) => v+o.bytes,0),0) })) } : data?.summary;
  return <Context.Provider value={{ data, studies, allStudies, summary, loading, error, collection, setCollection, refresh }}>{children}</Context.Provider>;
}
export const useArchive = () => useContext(Context);
