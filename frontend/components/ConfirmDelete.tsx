"use client";
import { useEffect, useRef, useState } from "react";

export type Deletion = { path: string; title: string; description: string; all: boolean };
export default function ConfirmDelete({ item, busy, error, cancel, confirm }: {
  item: Deletion; busy: boolean; error: string; cancel: () => void; confirm: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [typed, setTyped] = useState("");
  useEffect(() => { const element = dialog.current; element?.showModal(); return () => element?.close(); }, []);
  return <dialog ref={dialog} aria-labelledby="delete-title" onCancel={(event) => { event.preventDefault(); if (!busy) cancel(); }}>
    <h2 id="delete-title">{item.title}</h2>
    <p className="wrap">{item.description}</p>
    <p>This cannot be undone.</p>
    {item.all && <><label htmlFor="confirm-delete">Type DELETE to confirm</label>
      <input id="confirm-delete" value={typed} onChange={event => setTyped(event.target.value)} autoComplete="off" disabled={busy} /></>}
    {error && <p role="alert" className="error">{error}</p>}
    <div className="actions"><button className="secondary" autoFocus onClick={cancel} disabled={busy}>Cancel</button>
      <button className="danger" disabled={busy || (item.all && typed !== "DELETE")} onClick={confirm}>
        {busy ? "Deleting…" : item.all ? "Delete all expenses" : "Delete expense"}</button></div>
  </dialog>;
}
