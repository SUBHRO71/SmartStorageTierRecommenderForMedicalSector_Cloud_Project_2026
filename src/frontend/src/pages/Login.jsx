import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { RectangleStackIcon, ArrowRightIcon, ShieldCheckIcon, CheckCircleIcon } from '@heroicons/react/24/outline';
import { useAuth } from '../auth/CognitoAuth';
import { userPoolId } from '../runtime';

export default function Login() {
  const [email, setEmail] = useState(''), [password, setPassword] = useState('');
  const [error, setError] = useState(''), [loading, setLoading] = useState(false);
  const { signIn } = useAuth();
  const navigate = useNavigate(), location = useLocation();
  const local = !userPoolId;
  const login = async (username, secret) => { setLoading(true); setError(''); try { await signIn(username, secret); navigate(location.state?.from?.pathname || '/', {replace:true}); } catch(e) { setError(e.message); } finally { setLoading(false); } };
  return <div className="login-page"><section className="login-story"><LinkBrand /><div><h1>The whole study.{' '}<br />Ready when you{' '}<br />need it.</h1><p>Clinical context, complete MRI sequences and a storage decision you can explain.</p><div className="login-workflow">{[['Import','Keep every sequence together.'],['Verify','Link the clinical context.'],['Place','Put access requirements first.']].map(([name, text]) => <div key={name}><CheckCircleIcon /><span><strong>{name}</strong><small>{text}</small></span></div>)}</div></div><span className="login-story-footer">CloudTierRecommender · Cancer imaging research</span></section><section className="login-form-side"><div className="login-form"><ShieldCheckIcon className="login-shield" /><h2>Welcome to your archive.</h2><p>Sign in to inspect studies and manage their storage.</p><form onSubmit={e => { e.preventDefault(); login(email,password); }}><label>{local ? "Email address" : "Email or username"}<input type={local ? "email" : "text"} required autoComplete="username" value={email} onChange={e => setEmail(e.target.value)} placeholder={local ? "you@example.com" : "Your account name"} /></label><label>Password<input type="password" required autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Enter your password" /></label>{error && <div className="error-box" role="alert">{error}</div>}<button className="button primary full-width" disabled={loading}>{loading ? 'Signing in…' : 'Sign in'}<ArrowRightIcon /></button></form>{local && <div className="local-login"><span>Working locally?</span><button className="button secondary full-width" disabled={loading} onClick={() => login('admin@hospital.com','password')}>Open local workspace</button><p>Local demonstration authentication.<br />Sample data is labeled inside the workspace.</p></div>}<small className="login-footnote">Public research data · Inference-only MRI model</small></div></section></div>;
}
function LinkBrand() { return <div className="brand"><span className="brand-symbol"><RectangleStackIcon /></span><span>CloudTier<span className="brand-sub">Imaging archive</span></span></div>; }
