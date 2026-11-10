import { useEffect, useState } from 'react';
import { api } from './api.js';

export default function Admin() {
  const [s, setS] = useState(null);
  useEffect(() => { api('/api/admin/stats').then(setS); }, []);
  if (!s) return <p>Loading…</p>;
  const stat = (label, v) => <div className="stat"><b>{v}</b><span>{label}</span></div>;
  return (
    <div className="card">
      <h2>Admin dashboard</h2>
      <div className="stats">
        {stat('Users', s.users)}{stat('Deployments', s.total)}{stat('Succeeded', s.success)}
        {stat('Failed', s.failed)}{stat('Avg duration (ms)', s.avg_duration_ms)}
      </div>
      <h3>Recent deployments</h3>
      <table>
        <thead><tr><th>When</th><th>Site</th><th>Action</th><th>Status</th><th>Duration</th></tr></thead>
        <tbody>{s.recent.map(r => (
          <tr key={r.id}><td>{r.created_at}</td><td>{r.username}</td><td>{r.action}</td>
            <td><span className={`badge ${r.status}`}>{r.status}</span></td><td>{r.duration_ms} ms</td></tr>))}
        </tbody>
      </table>
    </div>
  );
}
