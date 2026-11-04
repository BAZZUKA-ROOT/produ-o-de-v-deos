import { Sparkles } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { APP_NAME } from "@/components/AppLayout";
import { Button, Field, Input } from "@/components/ui";
import { useAuth } from "@/lib/auth";

function Shell({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <div className="relative flex min-h-full items-center justify-center overflow-hidden px-4 py-12">
      <div className="pointer-events-none absolute -top-40 left-1/2 h-96 w-[48rem] -translate-x-1/2 rounded-full bg-ember/10 blur-3xl" />
      <div className="relative w-full max-w-sm animate-slide-up">
        <div className="mb-8 flex flex-col items-center gap-3 text-center">
          <img src="/favicon.svg" alt="" className="size-12" />
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
            <p className="mt-1 text-sm text-muted">{subtitle}</p>
          </div>
        </div>
        <div className="card p-6">{children}</div>
        <p className="mt-6 flex items-center justify-center gap-1.5 text-xs text-subtle"><Sparkles className="size-3" /> {APP_NAME} · IA local e open source</p>
      </div>
    </div>
  );
}

export function LoginPage() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      nav("/");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <Shell title="Entrar" subtitle="Crie vídeos comerciais com IA em minutos">
      <form onSubmit={submit} className="flex flex-col gap-4">
        <Field label="E-mail"><Input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
        <Field label="Senha"><Input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
        {error && <p className="rounded-lg bg-err/10 px-3 py-2 text-sm text-err">{error}</p>}
        <Button variant="primary" size="lg" loading={loading} type="submit">Entrar</Button>
        <p className="text-center text-sm text-muted">Não tem conta? <Link className="text-ember hover:underline" to="/cadastro">Cadastre-se</Link></p>
      </form>
    </Shell>
  );
}

export function RegisterPage() {
  const { register } = useAuth();
  const nav = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await register(form.name, form.email, form.password);
      nav("/");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <Shell title="Criar conta" subtitle="O primeiro cadastro vira administrador da plataforma">
      <form onSubmit={submit} className="flex flex-col gap-4">
        <Field label="Nome"><Input required minLength={2} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
        <Field label="E-mail"><Input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
        <Field label="Senha" hint="Mínimo de 8 caracteres, com letras e números"><Input type="password" autoComplete="new-password" required minLength={8} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></Field>
        {error && <p className="rounded-lg bg-err/10 px-3 py-2 text-sm text-err">{error}</p>}
        <Button variant="primary" size="lg" loading={loading} type="submit">Criar conta</Button>
        <p className="text-center text-sm text-muted">Já tem conta? <Link className="text-ember hover:underline" to="/login">Entrar</Link></p>
      </form>
    </Shell>
  );
}
