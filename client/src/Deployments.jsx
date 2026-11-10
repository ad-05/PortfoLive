import { useEffect, useState } from 'react';
import { api } from './api.js';

export default function Deployments() {
  const [rows, setRows] = useState(null);
  useEffect(() => { api('/api/deployments').then(setRows); }, []);
  if (!rows) return <p>Loading…</p>;
  return (
    <div className="card">
      <h2>Deployment history</h2>
      {!rows.length ? <p className="muted">No deployments yet. Publish from the Editor tab.</p> :
        <table>
          <thead><tr><th>When</th><th>Action</th><th>Status</th><th>Duration</th><th>URL / Error</th></tr></thead>
          <tbody>{rows.map(r => (
            <tr key={r.id}>
              <td>{r.created_at}</td><td>{r.action}</td>
              <td><span className={`badge ${r.status}`}>{r.status}</span></td>
              <td>{r.duration_ms} ms</td>
              <td>{r.url ? <a href={r.url} target="_blank" rel="noreferrer">{r.url}</a> : r.error}</td>
            </tr>))}
          </tbody>
        </table>}
    </div>
  );
}
