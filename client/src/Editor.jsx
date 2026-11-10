import { useEffect, useState } from 'react';
import { api } from './api.js';

const EMPTY = { name: '', title: '', bio: '', email: '', github: '', linkedin: '', skills: [], projects: [], education: [] };

export default function Editor() {
  const [templates, setTemplates] = useState([]);
  const [template, setTemplate] = useState('minimal');
  const [data, setData] = useState(EMPTY);
  const [html, setHtml] = useState('');
  const [msg, setMsg] = useState({ text: '', error: false });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api('/api/templates').then(setTemplates);
    api('/api/portfolio').then(p => { setTemplate(p.template); setData({ ...EMPTY, ...p.data }); });
  }, []);

  // live preview, debounced
  useEffect(() => {
    if (!data.name.trim()) { setHtml(''); return; }
    const t = setTimeout(() => api('/api/preview', { method: 'POST', body: { template, data } })
      .then(r => setHtml(r.html)).catch(() => {}), 350);
    return () => clearTimeout(t);
  }, [template, data]);

  const set = k => e => setData({ ...data, [k]: e.target.value });
  const setItem = (key, i, field, v) =>
    setData({ ...data, [key]: data[key].map((x, j) => (j === i ? { ...x, [field]: v } : x)) });
  const addItem = (key, blank) => setData({ ...data, [key]: [...data[key], blank] });
  const rmItem = (key, i) => setData({ ...data, [key]: data[key].filter((_, j) => j !== i) });

  const run = async (fn, ok) => {
    setBusy(true); setMsg({ text: '', error: false });
    try { await fn(); setMsg({ text: ok, error: false }); }
    catch (e) { setMsg({ text: e.message, error: true }); }
    setBusy(false);
  };
  const save = () => api('/api/portfolio', { method: 'PUT', body: { template, data } });
  const publish = () => run(async () => {
    await save();
    const r = await api('/api/publish', { method: 'POST' });
    setMsg({ text: `Live in ${r.duration_ms} ms: ${r.url}`, error: false, url: r.url });
  }, '');

  return (
    <div className="editor">
      <div className="form card">
        <h2>Your details</h2>
        <input placeholder="Full name *" value={data.name} onChange={set('name')} />
        <input placeholder="Headline (e.g. CS student)" value={data.title} onChange={set('title')} />
        <textarea placeholder="Short bio" rows={4} value={data.bio} onChange={set('bio')} />
        <input placeholder="Contact email" value={data.email} onChange={set('email')} />
        <input placeholder="GitHub URL" value={data.github} onChange={set('github')} />
        <input placeholder="LinkedIn URL" value={data.linkedin} onChange={set('linkedin')} />
        <input placeholder="Skills, comma separated" value={data.skills.join(', ')}
          onChange={e => setData({ ...data, skills: e.target.value.split(',').map(s => s.trimStart()) })} />

        <h3>Projects</h3>
        {data.projects.map((p, i) => (
          <div key={i} className="item">
            <input placeholder="Name" value={p.name} onChange={e => setItem('projects', i, 'name', e.target.value)} />
            <input placeholder="Link" value={p.link} onChange={e => setItem('projects', i, 'link', e.target.value)} />
            <textarea placeholder="Description" rows={2} value={p.description} onChange={e => setItem('projects', i, 'description', e.target.value)} />
            <button className="link" onClick={() => rmItem('projects', i)}>Remove</button>
          </div>
        ))}
        <button onClick={() => addItem('projects', { name: '', link: '', description: '' })}>+ Add project</button>

        <h3>Education</h3>
        {data.education.map((ed, i) => (
          <div key={i} className="item">
            <input placeholder="School" value={ed.school} onChange={e => setItem('education', i, 'school', e.target.value)} />
            <input placeholder="Degree" value={ed.degree} onChange={e => setItem('education', i, 'degree', e.target.value)} />
            <input placeholder="Years" value={ed.years} onChange={e => setItem('education', i, 'years', e.target.value)} />
            <button className="link" onClick={() => rmItem('education', i)}>Remove</button>
          </div>
        ))}
        <button onClick={() => addItem('education', { school: '', degree: '', years: '' })}>+ Add education</button>
      </div>

      <div className="side">
        <div className="card">
          <label>Template{' '}
            <select value={template} onChange={e => setTemplate(e.target.value)}>
              {templates.map(t => <option key={t}>{t}</option>)}
            </select>
          </label>
          <div className="row">
            <button disabled={busy} onClick={() => run(save, 'Saved')}>Save draft</button>
            <button className="primary" disabled={busy || !data.name.trim()} onClick={publish}>
              {busy ? 'Working…' : 'Publish'}
            </button>
          </div>
          {msg.text && <p className={msg.error ? 'error' : 'ok'}>
            {msg.text}{msg.url && <> <a href={msg.url} target="_blank" rel="noreferrer">Open site ↗</a></>}
          </p>}
        </div>
        <iframe className="preview" title="preview" sandbox="" srcDoc={html || '<p style="font-family:sans-serif;padding:24px;color:#888">Enter your name to see a live preview.</p>'} />
      </div>
    </div>
  );
}
