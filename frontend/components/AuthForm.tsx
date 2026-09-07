"use client";
import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "../lib/api";

export default function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const registering = mode === "register";
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true); setError("");
    try {
      await api(`/auth/${mode}/`, "POST", { username: form.get("username"), password: form.get("password") });
      router.replace("/"); router.refresh();
    } catch (error) { setError((error as Error).message); }
    finally { setBusy(false); }
  }
  return <main className="auth">
    <div className="brand"><span className="brand-dot" />Expense Tracker</div>
    <section className="card">
      <p className="eyebrow">YOUR MONEY, YOUR SPACE</p>
      <h1>{registering ? "A fresh start." : "Welcome back."}</h1>
      <p>{registering ? "Create an account to track your salary and everyday spending." : "Sign in to your personal expense tracker."}</p>
      {error && <p className="error" role="alert">{error}</p>}
      <form onSubmit={submit}>
        <label htmlFor="username">Username</label>
        <input id="username" name="username" autoComplete="username" maxLength={150} required disabled={busy} />
        <label htmlFor="password">Password</label>
        <input id="password" name="password" type="password" autoComplete={registering ? "new-password" : "current-password"}
          maxLength={128} required disabled={busy} />
        {registering && <p className="hint">Use a strong password with at least 8 characters. Avoid common passwords or your username.</p>}
        <button className="full" disabled={busy}>{busy ? "Please wait…" : registering ? "Create account" : "Sign in"}</button>
      </form>
      <p className="auth-switch">{registering ? "Already have an account? " : "New here? "}
        <Link href={registering ? "/login" : "/register"}>{registering ? "Sign in" : "Create an account"}</Link></p>
    </section>
  </main>;
}
