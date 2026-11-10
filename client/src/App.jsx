import { useEffect, useState } from 'react';
import { api, setToken } from './api.js';
import Editor from './Editor.jsx';
import Deployments from './Deployments.jsx';
import Admin from './Admin.jsx';

function Auth({ onAuth }) {
  const [mode, setMode] = useState('login');
  const [f, setF] = useState({ username: '', email: '', password: '' });
  const [err, setErr] = useState('');
  const set = k => e => setF({ ...f, [k]: e.target.value });
  async function submit(e) {
    e.preventDefault(); setErr('');
    try {
      const r = await api(`/api/auth/${mode}`, { method: 'POST', body: f });
      setToken(r.token); onAuth(r.user);
    } catch (e2) { setErr(e2.message); }
  }
  return (
    <form className="card auth" onSubmit={submit}>
      <h2>{mode === 'login' ? 'Log in' : 'Create account'}</h2>
      {mode === 'register' && <input placeholder="Username (your site URL)" value={f.username} onChange={set('username')} />}
      <input placeholder="Email" type="email" value={f.email} onChange={set('email')} />
      <input placeholder="Password (8+ chars)" type="password" value={f.password} onChange={set('password')} />
      {err && <p className="error">{err}</p>}
      <button className="primary">{mode === 'login' ? 'Log in' : 'Sign up'}</button>
      <button type="button" className="link" onClick={() => setMode(mode === 'login' ? 'register' : 'login')}>
        {mode === 'login' ? 'Need an account? Sign up' : 'Have an account? Log in'}
      </button>
    </form>
  );
}

export default function App() {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);
  const [tab, setTab] = useState('editor');

  useEffect(() => { api('/api/me').then(setUser).catch(() => setToken('')).finally(() => setReady(true)); }, []);
  if (!ready) return null;

  const logout = () => { setToken(''); setUser(null); };
  return (
    <>
      <nav>
        <strong>PortfoLive</strong>
        {user && (
          <>
            <button className={tab === 'editor' ? 'active' : ''} onClick={() => setTab('editor')}>Editor</button>
            <button className={tab === 'deployments' ? 'active' : ''} onClick={() => setTab('deployments')}>Deployments</button>
            {user.is_admin && <button className={tab === 'admin' ? 'active' : ''} onClick={() => setTab('admin')}>Admin</button>}
            <span className="spacer" />
            <span className="muted">{user.username}</span>
            <button onClick={logout}>Log out</button>
          </>
        )}
      </nav>
      <div className="page">
        {!user ? <Auth onAuth={setUser} /> :
          tab === 'editor' ? <Editor /> :
          tab === 'deployments' ? <Deployments /> : <Admin />}
      </div>
    </>
  );
}
