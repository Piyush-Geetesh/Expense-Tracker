"use client";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, Cycle, Dashboard, Page, date } from "../lib/api";
import ConfirmDelete, { Deletion } from "./ConfirmDelete";
import CycleDetails, { bulkDeletion, Categories, ExpenseTable, Totals } from "./CycleDetails";

export default function Tracker({ view }: { view: "dashboard" | "history" }) {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [history, setHistory] = useState<Page<Cycle> | null>(null);
  const [page, setPage] = useState(1);
  const [revision, setRevision] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [deletion, setDeletion] = useState<Deletion | null>(null);
  const [deleteError, setDeleteError] = useState("");
  const onError = useCallback((error: unknown) => {
    if (error instanceof ApiError && error.status === 403) {
      setDashboard(null); setHistory(null); setUsername(""); router.replace("/login");
    } else setError((error as Error).message);
  }, [router]);
  useEffect(() => {
    let live = true;
    setLoading(true); setError("");
    Promise.all([
      api<{ username: string }>("/auth/me/"),
      view === "dashboard" ? api<Dashboard>("/dashboard/") : api<Page<Cycle>>(`/cycles/?page=${page}`),
    ]).then(([user, data]) => {
      if (!live) return;
      setUsername(user.username);
      if (view === "dashboard") setDashboard(data as Dashboard);
      else setHistory(data as Page<Cycle>);
    }).catch(error => { if (live) onError(error); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [view, revision, page, onError]);
  useEffect(() => {
    const clearStalePage = () => { setDashboard(null); setHistory(null); setRevision(value => value + 1); };
    const visibility = () => { if (document.visibilityState === "visible") clearStalePage(); };
    window.addEventListener("pageshow", clearStalePage);
    document.addEventListener("visibilitychange", visibility);
    return () => { window.removeEventListener("pageshow", clearStalePage); document.removeEventListener("visibilitychange", visibility); };
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>, kind: "salary" | "expense") {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setBusy(true); setError(""); setNotice("");
    try {
      await api(kind === "salary" ? "/cycles/" : "/expenses/", "POST",
        kind === "salary" ? { amount: form.get("amount") } : { amount: form.get("amount"), description: form.get("description") });
      formElement.reset();
      setNotice(kind === "salary" ? "Salary credited. Your new cycle is ready." : "Expense added.");
      setRevision(value => value + 1);
    } catch (error) { onError(error); }
    finally { setBusy(false); }
  }
  async function logout() {
    setBusy(true); setError("");
    try {
      await api("/auth/logout/", "POST");
      setDashboard(null); setHistory(null); setUsername("");
      router.replace("/login"); router.refresh();
    } catch (error) { onError(error); setBusy(false); }
  }
  async function confirmDelete() {
    if (!deletion) return;
    setBusy(true); setDeleteError("");
    try {
      await api(deletion.path, "DELETE");
      setDeletion(null); setNotice("Expenses updated."); setRevision(value => value + 1);
    } catch (error) {
      if (error instanceof ApiError && error.status === 403) { setDeletion(null); onError(error); }
      else setDeleteError((error as Error).message);
    } finally { setBusy(false); }
  }
  const remove = (item: Deletion) => { setDeleteError(""); setDeletion(item); };
  const cycle = dashboard?.cycle || null;
  return <>
    <header className="topbar">
      <Link href="/" className="brand"><span className="brand-dot" />Expense Tracker</Link>
      <nav aria-label="Main navigation"><Link className={view === "dashboard" ? "active" : ""} href="/">Dashboard</Link>
        <Link className={view === "history" ? "active" : ""} href="/history">History</Link>
        <button className="nav-button" onClick={logout} disabled={busy || !username}>Sign out</button></nav>
    </header>
    <main>
      <div className="page-head"><div><p className="eyebrow">{username ? `YOUR PERSONAL TRACKER · ${username}` : "YOUR PERSONAL TRACKER"}</p>
        <h1>{view === "dashboard" ? "Make room for what matters." : "Your salary cycle history."}</h1>
        <p>{view === "dashboard" ? "A clear view of this cycle, one expense at a time." : "Every salary has its own story. Your expenses stay with their cycle."}</p></div></div>
      {error && <div className="error" role="alert">{error} <button className="secondary" onClick={() => setRevision(value => value + 1)}>Refresh</button></div>}
      {notice && <p className="success" role="status">{notice}</p>}
      {loading ? <p role="status" className="card">Loading your {view}…</p> : view === "dashboard" && dashboard ? <>
        <section className="card balance-card">
          <div className="section-head"><p className="eyebrow">{cycle ? `CURRENT CYCLE · ${date(cycle.credited_at)}` : "YOUR FIRST CYCLE"}</p>
            {cycle && <span className={`status ${cycle.status}`}>{cycle.status}</span>}</div>
          <Totals cycle={cycle} />
          <p className="balance-note">{!cycle ? "Credit your first salary to start tracking expenses." :
            dashboard.can_add_expense ? "Every expense here belongs to this salary cycle." : "Cycle complete. You can now credit your next salary."}</p>
        </section>
        <div className="dashboard-grid">
          <div className="form-stack">
            <section className="card"><h2>Credit salary</h2><p className="hint">A new salary starts a new cycle.</p>
              <form onSubmit={event => submit(event, "salary")}><label htmlFor="salary">Salary amount</label>
                <input id="salary" name="amount" type="number" min="0.01" step="0.01" placeholder="e.g. 80000"
                  required disabled={busy || !dashboard.can_credit_salary} />
                <button className="full" disabled={busy || !dashboard.can_credit_salary}>Credit salary</button></form>
              {!dashboard.can_credit_salary && <p className="hint">Use the remaining balance before starting another cycle.</p>}
            </section>
            <section className="card"><h2>Add an expense</h2>
              <form onSubmit={event => submit(event, "expense")}><label htmlFor="expense-amount">Expense amount</label>
                <input id="expense-amount" name="amount" type="number" min="0.01" step="0.01" placeholder="e.g. 250"
                  required disabled={busy || !dashboard.can_add_expense} />
                <label htmlFor="description">Description</label>
                <input id="description" name="description" maxLength={200} placeholder="lunch - at Restaurant" required disabled={busy || !dashboard.can_add_expense} />
                <p className="hint">Text before the first hyphen becomes the category. No hyphen? It goes under Other.</p>
                <button className="full" disabled={busy || !dashboard.can_add_expense}>Add expense</button></form>
              {!dashboard.can_add_expense && <p className="hint">Credit a salary to enable expenses.</p>}
            </section>
          </div>
          <div className="form-stack">
            <section className="card"><div className="section-head"><h2>Recent expenses</h2><Link href="/history">View history →</Link></div>
              <ExpenseTable expenses={dashboard.recent_expenses} remove={remove} busy={busy} />
              {cycle && <div className="card-footer"><button className="delete-small" disabled={busy || cycle.total_expenses === "0.00"}
                onClick={() => remove(bulkDeletion(cycle))}>Delete all expenses</button><span className="hint">Current cycle only</span></div>}
            </section>
            {cycle && <section className="card"><h2>Spending by category</h2><Categories cycle={cycle} /></section>}
          </div>
        </div>
      </> : view === "history" && history ? <>
        {!history.count && <section className="card empty"><h2>A fresh page.</h2><p>Your salary cycles will appear here after you credit your first salary.</p><Link href="/">Go to dashboard →</Link></section>}
        {history.results.map(item => <CycleDetails key={item.id} cycle={item} revision={revision} remove={remove} busy={busy} onError={onError} />)}
        {history.count > 10 && <div className="pagination"><button className="secondary" disabled={!history.previous} onClick={() => setPage(page - 1)}>Previous cycles</button>
          <span>Page {page}</span><button className="secondary" disabled={!history.next} onClick={() => setPage(page + 1)}>Next cycles</button></div>}
      </> : null}
    </main>
    <footer>Your money. Your cycles. Your space.</footer>
    {deletion && <ConfirmDelete item={deletion} busy={busy} error={deleteError} cancel={() => setDeletion(null)} confirm={confirmDelete} />}
  </>;
}
