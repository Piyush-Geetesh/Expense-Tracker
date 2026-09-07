"use client";
import { useEffect, useState } from "react";
import { api, Cycle, currency, date, Expense, Page } from "../lib/api";
import { Deletion } from "./ConfirmDelete";

export function Totals({ cycle }: { cycle: Cycle | null }) {
  return <div className="totals">
    <div><span>Salary credited</span><strong>{currency(cycle?.amount || 0)}</strong></div>
    <div><span>Total expenses</span><strong>{currency(cycle?.total_expenses || 0)}</strong></div>
    <div><span>Remaining balance</span><strong className="balance">{currency(cycle?.remaining_balance || 0)}</strong></div>
  </div>;
}
export function Categories({ cycle }: { cycle: Cycle }) {
  return <div className="categories" aria-label="Category summaries">
    {cycle.category_summary.length ? cycle.category_summary.map(item =>
      <div className="category-total" key={item.category}><span>{item.category}</span><strong>{currency(item.amount)}</strong></div>)
      : <p className="muted">Category summaries will appear as you add expenses.</p>}
  </div>;
}
export function ExpenseTable({ expenses, remove, busy }: { expenses: Expense[]; remove: (item: Deletion) => void; busy: boolean }) {
  if (!expenses.length) return <p className="empty">No expenses in this cycle yet.</p>;
  return <div className="table-wrap"><table><thead><tr><th>Category / description</th><th>Date</th><th className="number">Amount</th><th><span className="sr-only">Actions</span></th></tr></thead>
    <tbody>{expenses.map(expense => <tr key={expense.id}>
      <td><span className="badge">{expense.category}</span><span className="description">{expense.description}</span></td>
      <td className="date">{date(expense.created_at)}</td><td className="number money">{currency(expense.amount)}</td>
      <td><button className="delete-small" disabled={busy} aria-label={`Delete ${expense.description}`} onClick={() => remove({
        path: `/expenses/${expense.id}/`, title: "Delete this expense?",
        description: `${expense.description} · ${currency(expense.amount)}. Only this expense will be removed.`, all: false,
      })}>Delete</button></td></tr>)}</tbody></table></div>;
}
export function bulkDeletion(cycle: Cycle): Deletion {
  return { path: `/cycles/${cycle.id}/expenses/`, title: "Delete all expenses in this cycle?",
    description: `This removes every expense from the ${date(cycle.credited_at)} salary cycle (#${cycle.id}, salary ${currency(cycle.amount)}). The salary cycle and all other cycles stay saved.`, all: true };
}
export default function CycleDetails({ cycle, revision, remove, busy, onError }: {
  cycle: Cycle; revision: number; remove: (item: Deletion) => void; busy: boolean; onError: (error: unknown) => void;
}) {
  const [page, setPage] = useState(1);
  const [rows, setRows] = useState<Page<Expense> | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let live = true;
    setLoading(true);
    api<Page<Expense>>(`/cycles/${cycle.id}/expenses/?page=${page}`).then(data => {
      if (live) setRows(data);
    }).catch(error => { if (live) { if (page > 1) setPage(1); else onError(error); } })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [cycle.id, page, revision, onError]);
  return <section className="card cycle-section">
    <div className="section-head"><div><p className="eyebrow">SALARY CYCLE #{cycle.id}</p><h2>{date(cycle.credited_at)}</h2></div>
      <span className={`status ${cycle.status}`}>{cycle.status}</span></div>
    <Totals cycle={cycle} />
    {cycle.status === "historical" && <p className="hint">Historical balance reflects deletions. New expenses belong to your current cycle.</p>}
    <h3>Spending by category</h3><Categories cycle={cycle} />
    <div className="section-head"><h3>Expenses</h3><button className="delete-small" disabled={busy || cycle.total_expenses === "0.00"}
      onClick={() => remove(bulkDeletion(cycle))}>Delete all expenses</button></div>
    {loading ? <p role="status">Loading expenses…</p> : <ExpenseTable expenses={rows?.results || []} remove={remove} busy={busy} />}
    {rows && rows.count > 10 && <div className="pagination">
      <button className="secondary" disabled={loading || !rows.previous} onClick={() => setPage(page - 1)}>Previous expenses</button>
      <span>Page {page}</span><button className="secondary" disabled={loading || !rows.next} onClick={() => setPage(page + 1)}>Next expenses</button></div>}
  </section>;
}
