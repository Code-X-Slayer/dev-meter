import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  ArrowUpRight,
  BarChart3,
  ChevronRight,
  CircleAlert,
  Code2,
  Copy,
  KeyRound,
  LayoutDashboard,
  LogOut,
  Menu,
  Plus,
  Server,
  ShieldCheck,
  Terminal,
  Trash2,
  X,
  Zap,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, type ApiKey, type DailyUsage, type Service, type Summary } from "./api";

type Page = "overview" | "services" | "keys" | "analytics" | "playground";

const nav = [
  { id: "overview" as Page, label: "Overview", icon: LayoutDashboard },
  { id: "services" as Page, label: "Services", icon: Server },
  { id: "keys" as Page, label: "API keys", icon: KeyRound },
  { id: "analytics" as Page, label: "Analytics", icon: BarChart3 },
  { id: "playground" as Page, label: "API playground", icon: Terminal },
];

function App() {
  const [token, setToken] = useState<string | null>(null);
  const [identity, setIdentity] = useState<string | null>(null);
  const [page, setPage] = useState<Page>("overview");
  const [services, setServices] = useState<Service[]>([]);
  const [selectedService, setSelectedService] = useState<Service | null>(null);
  const [notice, setNotice] = useState<{ type: "error" | "success"; text: string } | null>(null);
  const [mobileNav, setMobileNav] = useState(false);

  const handleLogout = () => {
    setToken(null);
    setIdentity(null);
    setServices([]);
    setSelectedService(null);
  };

  const loadServices = useCallback(async (authToken: string) => {
    const result = await api.services(authToken);
    setServices(result);
    setSelectedService((current) => current ?? result[0] ?? null);
  }, []);

  useEffect(() => {
    if (!token) return;
    Promise.all([api.me(token), loadServices(token)]).then(([me]) => setIdentity(me.username)).catch(() => handleLogout());
  }, [token, loadServices]);

  useEffect(() => {
    const onUnauthorized = () => handleLogout();
    window.addEventListener("devmeter:unauthorized", onUnauthorized);
    return () => window.removeEventListener("devmeter:unauthorized", onUnauthorized);
  }, []);

  if (!token) return <Login onLogin={setToken} />;

  const pageTitle = nav.find((item) => item.id === page)?.label ?? "Overview";
  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileNav ? "sidebar-open" : ""}`}>
        <div className="brand"><div className="brand-mark"><Zap size={18} /></div><span>devmeter</span></div>
        <div className="workspace-label">Control plane</div>
        <nav>
          {nav.map(({ id, label, icon: Icon }) => (
            <button className={`nav-item ${page === id ? "active" : ""}`} key={id} onClick={() => { setPage(id); setMobileNav(false); }}>
              <Icon size={17} /><span>{label}</span>{page === id && <ChevronRight className="nav-arrow" size={15} />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="secure-note"><ShieldCheck size={17} /><span>Protected workspace<br /><small>JWT authenticated</small></span></div>
          <button className="logout-button" onClick={handleLogout}><LogOut size={16} /> Sign out</button>
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <button className="mobile-menu" onClick={() => setMobileNav((value) => !value)}><Menu size={20} /></button>
          <div><div className="eyebrow">Workspace / {pageTitle}</div><h1>{pageTitle}</h1></div>
          <div className="topbar-right"><span className="status-dot">System operational</span><div className="avatar">{identity?.slice(0, 1).toUpperCase()}</div></div>
        </header>
        {notice && <div className={`notice ${notice.type}`}><CircleAlert size={16} />{notice.text}<button onClick={() => setNotice(null)}><X size={15} /></button></div>}
        <div className="page-content">
          {page === "overview" && <Overview token={token} services={services} onNavigate={setPage} />}
          {page === "services" && <Services token={token} services={services} setServices={setServices} selected={selectedService} setSelected={setSelectedService} onNotice={setNotice} />}
          {page === "keys" && <Keys token={token} services={services} selected={selectedService} onNotice={setNotice} />}
          {page === "analytics" && <Analytics token={token} services={services} selected={selectedService} onSelect={setSelectedService} />}
          {page === "playground" && <Playground token={token} services={services} selected={selectedService} onSelect={setSelectedService} onNotice={setNotice} />}
        </div>
      </main>
    </div>
  );
}

function Login({ onLogin }: { onLogin: (token: string) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setLoading(true); setError("");
    try { onLogin((await api.login(username, password)).access_token); } catch (err) { setError(err instanceof Error ? err.message : "Unable to sign in"); } finally { setLoading(false); }
  };
  return <div className="login-page"><div className="login-glow" /><div className="login-card">
    <div className="brand login-brand"><div className="brand-mark"><Zap size={18} /></div><span>devmeter</span></div>
    <div className="login-heading"><span className="overline">API infrastructure</span><h1>Welcome back.</h1><p>Sign in to your control plane and keep every service in view.</p></div>
    <form onSubmit={submit}><label>Administrator username<input autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="admin" required /></label><label>Password<input autoComplete="current-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" required /></label>{error && <div className="form-error"><CircleAlert size={15} />{error}</div>}<button className="primary-button full" disabled={loading}>{loading ? "Authenticating…" : "Sign in"}<ArrowUpRight size={17} /></button></form>
    <p className="login-footnote"><ShieldCheck size={14} /> Your session stays in memory and is never persisted.</p>
  </div></div>;
}

function Overview({ token, services, onNavigate }: { token: string; services: Service[]; onNavigate: (page: Page) => void }) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [daily, setDaily] = useState<DailyUsage[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => { if (!services[0]) { setLoading(false); return; } Promise.all([api.summary(token, services[0].id), api.daily(token, services[0].id)]).then(([s, d]) => { setSummary(s); setDaily(d.slice(-14)); }).finally(() => setLoading(false)); }, [token, services]);
  const chartData = daily.map((item) => ({ date: item.date.slice(5), requests: item.total_requests, successful: item.successful_requests }));
  return <><div className="page-intro"><div><span className="overline">Good morning</span><h2>Your API surface, at a glance.</h2><p>Monitor the health and usage of your registered services.</p></div><button className="secondary-button" onClick={() => onNavigate("services")}><Plus size={16} /> Register service</button></div>
    {!services.length ? <EmptyState icon={Server} title="Your control plane is ready" text="Register your first service to start routing requests and measuring usage." action="Register a service" onClick={() => onNavigate("services")} /> : <>
      <div className="metric-grid"><Metric label="Total requests" value={loading ? "—" : summary?.total_requests.toLocaleString() ?? "0"} detail="Across selected service" icon={Activity} tone="violet" /><Metric label="Success rate" value={loading ? "—" : `${summary?.success_rate_percent.toFixed(1)}%`} detail="Upstream responses" icon={ShieldCheck} tone="green" /><Metric label="Avg. latency" value={loading ? "—" : `${summary?.average_duration_ms.toFixed(0)} ms`} detail="Request duration" icon={Zap} tone="amber" /><Metric label="Quota remaining" value={loading ? "—" : summary?.requests_remaining.toLocaleString() ?? "0"} detail="Current UTC day" icon={BarChart3} tone="blue" /></div>
      <div className="content-grid"><section className="panel chart-panel"><div className="panel-heading"><div><span className="overline">Traffic</span><h3>Request volume</h3></div><span className="panel-caption">Last 14 days</span></div><TrafficChart data={chartData} /></section><section className="panel service-panel"><div className="panel-heading"><div><span className="overline">Active resources</span><h3>Services</h3></div><button className="icon-button" onClick={() => onNavigate("services")}><ArrowUpRight size={16} /></button></div>{services.slice(0, 4).map((service) => <div className="service-row" key={service.id}><div className="service-icon"><Server size={16} /></div><div><strong>{service.name}</strong><span>{service.upstream_base_url}</span></div><span className="healthy">Active</span></div>)}<button className="text-button" onClick={() => onNavigate("services")}>View all services <ChevronRight size={15} /></button></section></div>
    </>}</>;
}

function Services({ token, services, setServices, selected, setSelected, onNotice }: { token: string; services: Service[]; setServices: (value: Service[]) => void; selected: Service | null; setSelected: (value: Service | null) => void; onNotice: (value: { type: "error" | "success"; text: string }) => void }) {
  const [open, setOpen] = useState(false); const [name, setName] = useState(""); const [url, setUrl] = useState(""); const [loading, setLoading] = useState(false);
  const create = async (e: React.FormEvent) => { e.preventDefault(); setLoading(true); try { const service = await api.createService(token, { name, upstream_base_url: url }); setServices([...services, service]); setSelected(service); setOpen(false); setName(""); setUrl(""); onNotice({ type: "success", text: "Service registered successfully." }); } catch (err) { onNotice({ type: "error", text: err instanceof Error ? err.message : "Unable to register service." }); } finally { setLoading(false); } };
  return <><div className="page-intro"><div><span className="overline">Resource registry</span><h2>Services</h2><p>Registered upstreams and their gateway surface.</p></div><button className="primary-button" onClick={() => setOpen(true)}><Plus size={16} /> Register service</button></div>
    <div className="service-layout"><div className="panel service-list">{services.length ? services.map((service) => <button className={`service-list-item ${selected?.id === service.id ? "selected" : ""}`} key={service.id} onClick={() => setSelected(service)}><div className="service-icon"><Server size={17} /></div><div><strong>{service.name}</strong><span>{service.upstream_base_url}</span></div><ChevronRight size={16} /></button>) : <EmptyState icon={Server} title="No services yet" text="Register an upstream to create your first gateway route." action="Register service" onClick={() => setOpen(true)} />}</div>{selected && <ServiceDetail token={token} service={selected} />}</div>
    {open && <Modal title="Register a service" onClose={() => setOpen(false)}><form onSubmit={create} className="modal-form"><label>Service name<input value={name} onChange={(e) => setName(e.target.value)} placeholder="Inference API" required /></label><label>Upstream base URL<input type="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://api.example.com/v1" required /><small>Private and loopback destinations are rejected by the API.</small></label><div className="modal-actions"><button type="button" className="secondary-button" onClick={() => setOpen(false)}>Cancel</button><button className="primary-button" disabled={loading}>{loading ? "Registering…" : "Register service"}</button></div></form></Modal>}</>;
}

function ServiceDetail({ token, service }: { token: string; service: Service }) {
  const [keys, setKeys] = useState<ApiKey[]>([]); const [summary, setSummary] = useState<Summary | null>(null);
  useEffect(() => { Promise.all([api.keys(token, service.id), api.summary(token, service.id)]).then(([k, s]) => { setKeys(k); setSummary(s); }); }, [token, service.id]);
  return <section className="panel service-detail"><div className="detail-hero"><div className="service-icon large"><Server size={22} /></div><div><span className="overline">Service details</span><h3>{service.name}</h3><p>{service.upstream_base_url}</p></div></div><div className="detail-stats"><div><span>Created</span><strong>{new Date(service.created_at).toLocaleDateString()}</strong></div><div><span>Requests</span><strong>{summary?.total_requests ?? "—"}</strong></div><div><span>Keys</span><strong>{keys.length}</strong></div></div><div className="detail-note"><ShieldCheck size={16} /><span>Ownership is scoped to your authenticated administrator account.</span></div></section>;
}

function Keys({ token, services, selected, onNotice }: { token: string; services: Service[]; selected: Service | null; onNotice: (value: { type: "error" | "success"; text: string }) => void }) {
  const [service, setService] = useState(selected?.id ?? services[0]?.id ?? ""); const [keys, setKeys] = useState<ApiKey[]>([]); const [name, setName] = useState(""); const [secret, setSecret] = useState<string | null>(null); const [loading, setLoading] = useState(false);
  const load = useCallback(() => { if (service) api.keys(token, service).then(setKeys).catch(() => setKeys([])); }, [token, service]);
  useEffect(load, [load]); useEffect(() => { if (selected) setService(selected.id); }, [selected]);
  const create = async (e: React.FormEvent) => { e.preventDefault(); setLoading(true); try { const key = await api.createKey(token, service, name); setKeys([...keys, key]); setSecret(key.secret ?? null); setName(""); onNotice({ type: "success", text: "API key created. Copy the secret now; it will not be shown again." }); } catch (err) { onNotice({ type: "error", text: err instanceof Error ? err.message : "Unable to create key." }); } finally { setLoading(false); } };
  const revoke = async (id: string) => { try { await api.revokeKey(token, id); setKeys(keys.map((key) => key.id === id ? { ...key, revoked_at: new Date().toISOString() } : key)); onNotice({ type: "success", text: "API key revoked." }); } catch (err) { onNotice({ type: "error", text: err instanceof Error ? err.message : "Unable to revoke key." }); } };
  return <><div className="page-intro"><div><span className="overline">Credentials</span><h2>API keys</h2><p>Issue scoped gateway credentials and revoke them instantly.</p></div></div>{services.length ? <><div className="toolbar"><select value={service} onChange={(e) => setService(e.target.value)}>{services.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select><form className="inline-form" onSubmit={create}><input value={name} onChange={(e) => setName(e.target.value)} placeholder="New key name" required /><button className="primary-button" disabled={loading}><Plus size={16} /> Create key</button></form></div><section className="panel table-panel"><div className="table-header"><span>Key</span><span>Name</span><span>Created</span><span>Status</span><span /></div>{keys.map((key) => <div className="table-row" key={key.id}><span className="key-prefix"><KeyRound size={14} />{key.key_prefix}…</span><strong>{key.name}</strong><span>{new Date(key.created_at).toLocaleDateString()}</span><span className={key.revoked_at ? "status revoked" : "status active"}>{key.revoked_at ? "Revoked" : "Active"}</span><span>{!key.revoked_at && <button className="danger-button" onClick={() => revoke(key.id)}><Trash2 size={15} /></button>}</span></div>)}{!keys.length && <div className="table-empty">No keys created for this service.</div>}</section>{secret && <Modal title="Save your API key" onClose={() => setSecret(null)}><div className="secret-box"><div className="secret-warning"><ShieldCheck size={17} /><span>This secret is shown once. It is not stored in the browser.</span></div><code>{secret}</code><button className="secondary-button full" onClick={() => navigator.clipboard.writeText(secret)}><Copy size={15} /> Copy secret</button></div></Modal>}</> : <EmptyState icon={KeyRound} title="Create a service first" text="API keys are scoped to a registered service." />}</>;
}

function Analytics({ token, services, selected, onSelect }: { token: string; services: Service[]; selected: Service | null; onSelect: (service: Service) => void }) {
  const [summary, setSummary] = useState<Summary | null>(null); const [daily, setDaily] = useState<DailyUsage[]>([]); const [start, setStart] = useState(""); const [end, setEnd] = useState("");
  useEffect(() => { if (!selected) return; Promise.all([api.summary(token, selected.id), api.daily(token, selected.id, start, end)]).then(([s, d]) => { setSummary(s); setDaily(d); }); }, [token, selected, start, end]);
  return <><div className="page-intro"><div><span className="overline">Observability</span><h2>Analytics</h2><p>Understand traffic patterns and upstream performance.</p></div><select value={selected?.id ?? ""} onChange={(e) => { const next = services.find((item) => item.id === e.target.value); if (next) onSelect(next); }}>{services.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select></div>{!selected ? <EmptyState icon={BarChart3} title="No usage to show" text="Register a service and route a request to begin measuring traffic." /> : <><div className="metric-grid compact"><Metric label="Requests" value={summary?.total_requests.toLocaleString() ?? "—"} detail="All time" icon={Activity} tone="violet" /><Metric label="Successful" value={summary?.successful_requests.toLocaleString() ?? "—"} detail={`${summary?.success_rate_percent.toFixed(1) ?? "—"}% success rate`} icon={ShieldCheck} tone="green" /><Metric label="Failed" value={summary?.failed_requests.toLocaleString() ?? "—"} detail="Upstream failures" icon={CircleAlert} tone="red" /><Metric label="Average duration" value={`${summary?.average_duration_ms.toFixed(0) ?? "—"} ms`} detail="Across all requests" icon={Zap} tone="amber" /></div><section className="panel chart-panel analytics-chart"><div className="panel-heading"><div><span className="overline">Daily traffic</span><h3>Requests over time</h3></div><div className="date-filters"><input type="date" value={start} onChange={(e) => setStart(e.target.value)} /><span>to</span><input type="date" value={end} onChange={(e) => setEnd(e.target.value)} /></div></div><TrafficChart data={daily.map((item) => ({ date: item.date.slice(5), requests: item.total_requests, successful: item.successful_requests }))} /></section></>}</>;
}

function Playground({ token, services, selected, onSelect, onNotice }: { token: string; services: Service[]; selected: Service | null; onSelect: (service: Service) => void; onNotice: (value: { type: "error" | "success"; text: string }) => void }) {
  const [key, setKey] = useState(""); const [body, setBody] = useState('{\n  "input": "hello"\n}'); const [response, setResponse] = useState<unknown>(null); const [status, setStatus] = useState<number | null>(null); const [loading, setLoading] = useState(false);
  const submit = async () => {
    if (!selected || !key) return;
    let payload: unknown;
    try {
      payload = JSON.parse(body);
    } catch {
      setStatus(null);
      setResponse(null);
      onNotice({ type: "error", text: "Enter a valid JSON request body before sending." });
      return;
    }
    setLoading(true);
    try {
      const result = await api.gateway(key, selected.id, payload);
      setResponse(result);
      setStatus(200);
    } catch (err) {
      setStatus(502);
      setResponse({ detail: err instanceof Error ? err.message : "Gateway request failed" });
      onNotice({ type: "error", text: "The gateway request did not succeed." });
    } finally {
      setLoading(false);
    }
  };
  return <><div className="page-intro"><div><span className="overline">Developer tools</span><h2>API playground</h2><p>Send a real JSON request through your protected gateway.</p></div></div>{services.length ? <div className="playground-grid"><section className="panel playground-form"><label>Service<select value={selected?.id ?? ""} onChange={(e) => { const next = services.find((item) => item.id === e.target.value); if (next) onSelect(next); }}>{services.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select></label><label>Gateway API key<input type="password" value={key} onChange={(e) => setKey(e.target.value)} placeholder="Paste a service API key" /></label><label>JSON body<textarea value={body} onChange={(e) => setBody(e.target.value)} spellCheck={false} /></label><button className="primary-button" onClick={submit} disabled={loading || !key}>{loading ? "Sending…" : "Send request"}<ArrowUpRight size={16} /></button></section><section className="panel response-panel"><div className="panel-heading"><div><span className="overline">Response</span><h3>{status ? `HTTP ${status}` : "Waiting for request"}</h3></div>{status && <span className={status < 400 ? "status active" : "status revoked"}>{status < 400 ? "Success" : "Error"}</span>}</div><pre>{response ? JSON.stringify(response, null, 2) : "// Your upstream response will appear here"}</pre></section></div> : <EmptyState icon={Terminal} title="Create a service first" text="The playground sends requests to registered services only." />}</>;
}

function Metric({ label, value, detail, icon: Icon, tone }: { label: string; value: string; detail: string; icon: typeof Activity; tone: string }) { return <div className="metric-card"><div className={`metric-icon ${tone}`}><Icon size={17} /></div><div><span>{label}</span><strong>{value}</strong><small>{detail}</small></div></div>; }
function TrafficChart({ data }: { data: { date: string; requests: number; successful: number }[] }) { return data.length ? <div className="chart"><ResponsiveContainer width="100%" height="100%"><AreaChart data={data}><defs><linearGradient id="violetFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#8b7cf6" stopOpacity={0.3} /><stop offset="100%" stopColor="#8b7cf6" stopOpacity={0} /></linearGradient></defs><CartesianGrid stroke="#25304b" strokeDasharray="3 3" vertical={false} /><XAxis dataKey="date" tick={{ fill: "#77819b", fontSize: 11 }} axisLine={false} tickLine={false} /><YAxis allowDecimals={false} tick={{ fill: "#77819b", fontSize: 11 }} axisLine={false} tickLine={false} width={30} /><Tooltip contentStyle={{ background: "#151e35", border: "1px solid #2a3653", borderRadius: 10, color: "#f4f5fb" }} /><Area type="monotone" dataKey="requests" stroke="#9a8cff" strokeWidth={2} fill="url(#violetFill)" /></AreaChart></ResponsiveContainer></div> : <div className="chart-empty">No traffic recorded for this range.</div>; }
function EmptyState({ icon: Icon, title, text, action, onClick }: { icon: typeof Server; title: string; text: string; action?: string; onClick?: () => void }) { return <div className="empty-state"><div className="empty-icon"><Icon size={22} /></div><h3>{title}</h3><p>{text}</p>{action && <button className="secondary-button" onClick={onClick}>{action}<ArrowUpRight size={15} /></button>}</div>; }
function Modal({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) { return <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}><div className="modal"><div className="modal-header"><h3>{title}</h3><button className="icon-button" onClick={onClose}><X size={17} /></button></div>{children}</div></div>; }

export default App;
