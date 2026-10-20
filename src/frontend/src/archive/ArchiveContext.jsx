import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import axios from 'axios';
import { Auth } from '@aws-amplify/auth';
import { apiUrl, cloudMode } from '../runtime';

export const archiveApi = axios.create({ baseURL: `${apiUrl}/archive`, timeout: 120000 });
archiveApi.interceptors.request.use(async config => {
  if (cloudMode) {
    const session = await Auth.currentSession();
    config.headers.Authorization = `Bearer ${session.getIdToken().getJwtToken()}`;
  }
  return config;
});
export async function uploadStudy(form, onProgress = () => {}) {
  if (!cloudMode) return (await archiveApi.post('/import', form)).data.study;
  const metadata = {}, files = [];
  for (const [role, value] of form.entries()) {
    if (value instanceof File) { if (value.size) files.push({ role, file: value }); }
    else metadata[role] = value;
  }
  if (files.reduce((sum, item) => sum + item.file.size, 0) > 512 * 1024 * 1024) throw new Error('An import must be at most 512 MiB.');
  const { data } = await archiveApi.post('/uploads', { ...metadata, files: files.map(({ role, file }) => ({ role, name: file.name, size: file.size })) });
  for (let i = 0; i < files.length; i++) {
    onProgress(`Uploading file ${i + 1} of ${files.length}…`);
    const response = await fetch(data.uploads[i].url, { method: 'PUT', headers: { 'Content-Type': 'application/octet-stream' }, body: files[i].file });
    if (!response.ok) throw new Error('A source upload failed. Start a new import to retry.');
  }
  await archiveApi.post(`/uploads/${data.id}/commit`, {});
  onProgress('Validating uploaded study…');
  for (let i = 0; i < 900; i++) {
    await new Promise(resolve => setTimeout(resolve, 2000));
    const result = (await archiveApi.get(`/uploads/${data.id}`)).data;
    if (result.status === 'DONE') return result.study;
    if (result.status === 'FAILED') throw new Error(result.message || 'The import failed. Start a new upload.');
  }
  throw new Error('The import is still running. Refresh the study list later to inspect its result.');
}
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
