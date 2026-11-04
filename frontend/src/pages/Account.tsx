import { useState } from "react";
import { useToast } from "@/components/toast";
import { Button, Card, Field, Input, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { User } from "@/lib/types";

export default function Account() {
  const { user, setSession, refresh, logout } = useAuth();
  const toast = useToast();
  const [name, setName] = useState(user?.name ?? "");
  const [pw, setPw] = useState({ current: "", next: "" });
  const [busy, setBusy] = useState("");
  const run = async (key: string, fn: () => Promise<void>) => {
    setBusy(key);
    try { await fn(); } catch (e) { toast((e as Error).message, "error"); } finally { setBusy(""); }
  };
  return (
    <div className="max-w-2xl animate-fade-in">
      <PageHeader title="Minha conta" />
      <Card className="mb-4 p-5">
        <h2 className="mb-4 font-medium">Perfil</h2>
        <div className="flex flex-col gap-4">
          <Field label="Nome"><Input value={name} onChange={(e) => setName(e.target.value)} /></Field>
          <Field label="E-mail"><Input value={user?.email ?? ""} disabled /></Field>
          <div><Button variant="primary" loading={busy === "p"} onClick={() => run("p", async () => { await api("/auth/me", { method: "PATCH", body: { name } }); await refresh(); toast("Perfil atualizado", "success"); })}>Salvar</Button></div>
        </div>
      </Card>
      <Card className="mb-4 p-5">
        <h2 className="mb-4 font-medium">Alterar senha</h2>
        <div className="flex flex-col gap-4">
          <Field label="Senha atual"><Input type="password" value={pw.current} onChange={(e) => setPw({ ...pw, current: e.target.value })} /></Field>
          <Field label="Nova senha" hint="Mínimo de 8 caracteres, com letras e números"><Input type="password" value={pw.next} onChange={(e) => setPw({ ...pw, next: e.target.value })} /></Field>
          <div><Button variant="primary" loading={busy === "s"} onClick={() => run("s", async () => {
            const r = await api<{ access_token: string; user: User }>("/auth/change-password", { body: { current_password: pw.current, new_password: pw.next } });
            setSession(r.access_token, r.user); setPw({ current: "", next: "" }); toast("Senha alterada. Outras sessões foram encerradas.", "success");
          })}>Alterar senha</Button></div>
        </div>
      </Card>
      <Card className="p-5">
        <h2 className="mb-2 font-medium">Sessões</h2>
        <p className="mb-4 text-sm text-muted">Encerra o acesso em todos os dispositivos, inclusive este.</p>
        <Button variant="danger" loading={busy === "l"} onClick={() => run("l", async () => { await api("/auth/logout-all", { method: "POST" }); logout(); })}>Sair de todos os dispositivos</Button>
      </Card>
    </div>
  );
}
