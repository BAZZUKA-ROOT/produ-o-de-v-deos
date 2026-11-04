import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Search, Trash2 } from "lucide-react";
import { useState } from "react";
import { useToast } from "@/components/toast";
import { Badge, Button, ConfirmModal, Field, IconButton, Input, Modal, PageHeader, PageLoader, Select, Toggle } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtBytes, fmtDate } from "@/lib/format";
import type { User } from "@/lib/types";

export default function AdminUsers() {
  const qc = useQueryClient();
  const toast = useToast();
  const [q, setQ] = useState("");
  const [edit, setEdit] = useState<Partial<User> & { password?: string } | null>(null);
  const [del, setDel] = useState<User | null>(null);
  const { data } = useQuery({ queryKey: ["admin", "users", q], queryFn: () => api<User[]>(`/admin/users${q ? `?q=${encodeURIComponent(q)}` : ""}`) });
  const done = (msg: string) => { toast(msg, "success"); qc.invalidateQueries({ queryKey: ["admin", "users"] }); };
  const save = useMutation({
    mutationFn: (u: Partial<User> & { password?: string }) => u.id
      ? api(`/admin/users/${u.id}`, { method: "PATCH", body: { name: u.name, role: u.role, is_active: u.is_active, quota_mb: u.quota_mb ?? null, ...(u.password && { password: u.password }) } })
      : api("/admin/users", { body: { name: u.name, email: u.email, password: u.password, role: u.role ?? "user", quota_mb: u.quota_mb ?? null } }),
    onSuccess: () => { done("Usuário salvo"); setEdit(null); }, onError: (e) => toast((e as Error).message, "error"),
  });
  const remove = useMutation({ mutationFn: (id: string) => api(`/admin/users/${id}`, { method: "DELETE" }), onSuccess: () => { done("Usuário excluído"); setDel(null); }, onError: (e) => toast((e as Error).message, "error") });

  return (
    <div className="animate-fade-in">
      <PageHeader title="Usuários" actions={<Button variant="primary" icon={<Plus className="size-4" />} onClick={() => setEdit({ role: "user", is_active: true })}>Novo usuário</Button>} />
      <div className="relative mb-4 max-w-sm"><Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-subtle" /><Input className="pl-9" placeholder="Buscar por nome ou e-mail" value={q} onChange={(e) => setQ(e.target.value)} /></div>
      {!data ? <PageLoader /> : (
        <div className="card overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead className="border-b border-line text-left text-xs text-muted"><tr>{["Usuário", "Papel", "Status", "Projetos", "Armazenamento", "Último acesso", ""].map((h) => <th key={h} className="px-4 py-2.5 font-medium">{h}</th>)}</tr></thead>
            <tbody>
              {data.map((u) => (
                <tr key={u.id} className="cursor-pointer border-b border-line/60 last:border-0 hover:bg-surface-2" onClick={() => setEdit(u)}>
                  <td className="px-4 py-2.5"><p className="font-medium">{u.name}</p><p className="text-xs text-muted">{u.email}</p></td>
                  <td className="px-4"><Badge className={u.role === "admin" ? "!text-ember" : ""}>{u.role}</Badge></td>
                  <td className="px-4">{u.is_active ? <span className="text-ok">ativo</span> : <span className="text-err">inativo</span>}</td>
                  <td className="px-4 tabular-nums">{u.projects}</td>
                  <td className="px-4 tabular-nums">{fmtBytes(u.usage_bytes)}{u.quota_mb != null && <span className="text-muted"> / {u.quota_mb} MB</span>}</td>
                  <td className="px-4 text-xs text-muted">{fmtDate(u.last_login_at)}</td>
                  <td className="px-4" onClick={(e) => e.stopPropagation()}><IconButton label="Excluir" className="hover:!text-err" onClick={() => setDel(u)}><Trash2 className="size-4" /></IconButton></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Modal open={!!edit} onClose={() => setEdit(null)} title={edit?.id ? "Editar usuário" : "Novo usuário"}
        footer={<><Button variant="ghost" onClick={() => setEdit(null)}>Cancelar</Button><Button variant="primary" loading={save.isPending} onClick={() => edit && save.mutate(edit)}>Salvar</Button></>}>
        {edit && <div className="flex flex-col gap-4">
          <Field label="Nome"><Input value={edit.name ?? ""} onChange={(e) => setEdit({ ...edit, name: e.target.value })} /></Field>
          <Field label="E-mail"><Input type="email" disabled={!!edit.id} value={edit.email ?? ""} onChange={(e) => setEdit({ ...edit, email: e.target.value })} /></Field>
          <Field label={edit.id ? "Nova senha (opcional)" : "Senha"} hint="Mínimo 8 caracteres com letras e números"><Input type="password" value={edit.password ?? ""} onChange={(e) => setEdit({ ...edit, password: e.target.value })} /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Papel"><Select value={edit.role ?? "user"} onChange={(e) => setEdit({ ...edit, role: e.target.value as User["role"] })} options={[{ value: "user", label: "Usuário" }, { value: "admin", label: "Administrador" }]} /></Field>
            <Field label="Cota (MB)" hint="Vazio = padrão global"><Input type="number" min={0} value={edit.quota_mb ?? ""} onChange={(e) => setEdit({ ...edit, quota_mb: e.target.value === "" ? null : Number(e.target.value) })} /></Field>
          </div>
          {edit.id && <Toggle checked={!!edit.is_active} onChange={(v) => setEdit({ ...edit, is_active: v })} label="Conta ativa" />}
        </div>}
      </Modal>
      <ConfirmModal open={!!del} danger title="Excluir usuário" confirmLabel="Excluir" text={`Excluir ${del?.email}? Todos os projetos e arquivos dele serão removidos.`} loading={remove.isPending} onConfirm={() => del && remove.mutate(del.id)} onClose={() => setDel(null)} />
    </div>
  );
}
