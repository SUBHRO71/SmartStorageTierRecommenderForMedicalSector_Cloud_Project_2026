import React, { useState, useEffect, useRef } from 'react';
import { NavLink, Link, Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Squares2X2Icon, RectangleStackIcon, ShieldCheckIcon, CurrencyDollarIcon, ClockIcon, ArrowRightOnRectangleIcon, ArrowPathIcon, MagnifyingGlassIcon, Bars3Icon, XMarkIcon, ArrowUpRightIcon } from '@heroicons/react/24/outline';
import { useAuth } from '../auth/CognitoAuth';
import { useArchive } from './ArchiveContext';

export default function ArchiveShell() {
  const { user, signOut } = useAuth();
  const { data, collection, setCollection, allStudies, refresh } = useArchive();
  const [menu, setMenu] = useState(false);
  const [mobile, setMobile] = useState(() => window.matchMedia('(max-width: 767px)').matches);
  const navRef = useRef(null), toggleRef = useRef(null), previouslyOpen = useRef(false);
  useEffect(() => {
    if (!menu && previouslyOpen.current) toggleRef.current?.focus();
    previouslyOpen.current = menu;
  }, [menu]);
  useEffect(() => {
    const query = window.matchMedia('(max-width: 767px)');
    const update = () => { setMobile(query.matches); if (!query.matches) setMenu(false); };
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, []);
  useEffect(() => {
    if (!menu || !mobile) return;
    const controls = [...navRef.current.querySelectorAll('a,button')];
    controls[1]?.focus();
    const handle = event => {
      if (event.key === 'Escape') { setMenu(false); toggleRef.current?.focus(); }
      if (event.key === 'Tab') {
        const first=controls[0], last=controls[controls.length-1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener('keydown',handle);
    return () => document.removeEventListener('keydown',handle);
  }, [menu,mobile]);
  const [search, setSearch] = useState('');
  const navigate = useNavigate();
  const location = useLocation();
  useEffect(() => { window.scrollTo({top:0,behavior:'instant'}); }, [location.pathname]);
  const navigation = [['Overview', '/', Squares2X2Icon], ['Studies', '/studies', RectangleStackIcon], ['Data quality', '/quality', ShieldCheckIcon], ['Policy & costs', '/costs', CurrencyDollarIcon], ['Operations', '/operations', ClockIcon]];
  const collections = [...new Set(allStudies.map(s => s.collection))];
  const synthetic = allStudies.some(s => s.source === 'SYNTHETIC');
  return <div className="archive-app"><a className="skip-link" href="#archive-main">Skip to content</a><aside id="archive-navigation" ref={navRef} inert={mobile && !menu ? '' : undefined} className={`sidebar ${menu ? 'sidebar-open' : ''}`}><Link to="/" className="brand" onClick={() => setMenu(false)}><span className="brand-symbol" aria-hidden="true"><RectangleStackIcon /></span><span>CloudTier<span className="brand-sub">Imaging archive</span></span></Link><button className="icon-button sidebar-close" aria-label="Close navigation" onClick={() => setMenu(false)}><XMarkIcon /></button><nav aria-label="Main navigation">{navigation.map(([name, path, Icon]) => <NavLink key={path} to={path} end={path === '/'} onClick={() => setMenu(false)} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}><Icon />{name}{name === 'Data quality' && data?.summary.issues.length > 0 && <span className="nav-count">{data.summary.issues.length}</span>}</NavLink>)}</nav><div className="sidebar-bottom"><div className="sidebar-note"><ShieldCheckIcon /><strong>Context before cost.</strong><p>Keep access requirements at the centre of every storage decision.</p></div><Link className="legacy-link" to="/scans">X-ray workspace <ArrowUpRightIcon /></Link><div className="sidebar-user"><span className="avatar">A</span><div><strong>Archive administrator</strong><small>{user?.attributes?.email || user?.username}</small></div><button className="icon-button" aria-label="Sign out" onClick={signOut}><ArrowRightOnRectangleIcon /></button></div></div></aside>{menu && <button className="nav-backdrop" aria-label="Close navigation" onClick={() => setMenu(false)} />}<div className="workspace" inert={mobile && menu ? '' : undefined}><header className="topbar"><button ref={toggleRef} className="icon-button menu-toggle" aria-expanded={menu} aria-controls="archive-navigation" aria-label="Open navigation" onClick={() => setMenu(true)}><Bars3Icon /></button><div className="breadcrumb">Workspace <span>/</span> <strong>{navigation.find(([, p]) => p !== '/' && location.pathname.startsWith(p))?.[0] || (location.pathname === '/import' ? 'Import study' : 'Overview')}</strong></div><form className="global-search" onSubmit={e => { e.preventDefault(); navigate(`/studies?q=${encodeURIComponent(search)}`); }}><MagnifyingGlassIcon /><input aria-label="Search archive studies" placeholder="Find a study or subject…" value={search} onChange={e => setSearch(e.target.value)} /></form><span className="mode-badge"><i />Local workspace</span><button className="icon-button" aria-label="Refresh archive" onClick={refresh}><ArrowPathIcon /></button></header><div className="scopebar"><label>Collection <select value={collection} onChange={e => setCollection(e.target.value)} aria-label="Selected collection"><option value="">All collections</option>{collections.map(c => <option key={c}>{c}</option>)}</select></label><span>{synthetic ? 'Includes synthetic sample records' : 'User-imported research data'}<span className="scope-dot">·</span> {data ? 'Connected to local API' : 'Connecting…'}</span></div><main id="archive-main" className="archive-main" key={location.pathname}><Outlet /></main><footer className="workspace-footer"><span>CloudTierRecommender · Cancer imaging research prototype</span><span>Storage decisions with a visible reason.</span></footer></div></div>;
}
