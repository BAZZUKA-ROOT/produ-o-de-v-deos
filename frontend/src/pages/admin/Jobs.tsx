import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RotateCw, X } from "lucide-react";
import { useState } from "react";
import { useToast } from "@/components/toast";
import { Button, Modal, PageHeader, PageLoader, Progress, Select, StatusBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDate, JOB_LABEL, STATUS_LABEL } from "@/lib/format";
import type { Job } from "@/lib/types";

export default function AdminJobs() {
  const qc = useQueryClient();
  const toast = useToast();
  const [kind, setKind] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState<string | null>(null);
  const qs = new URLSearchParams({ page: String(page), ...(kind && { kind }), ...(status && { status }) });
  const { data } = useQuery({ queryKey: ["admin", "jobs", qs.toString()], queryFn: () => api<{ total: number; items: Job[] }>(`/admin/jobs?${qs}`), refetchInterval: 4000 });
  const { data: detail } = useQuery({ queryKey: ["admin", "job", open], enabled: !!open, queryFn: () => api<Job & { params: unknown }>(`/admin/jobs/${open}`), refetchInterval: 3000 });
  const { data: workers } = useQuery({ queryKey: ["admin", "workers"], queryFn: () => api<{ active: Record<string, unknown[]>; reserved: Record<string, unknown[]>; stats: Record<string, { pool?: { "max-concurrency"?: number } }> }>("/admin/workers"), refetchInterval: 10000, retry: false });
  const act = useMutation({
    mutationFn: ({ id, action }: { id: string; action: "cancel" | "retry" }) => api(`/admin/jobs/${id}/${action}`, { method: "POST" }),
    onSuccess: (_, v) => { toast(v.action === "cancel" ? "Cancelamento solicitado" : "Tarefa reenfileirada", "success"); qc.invalidateQueries({ queryKey: ["admin"] }); },
    onError: (e) => toast((e as Error).message, "error"),
  });
  return (
    <div className="animate-fade-in">
      <PageHeader title="Tarefas e renderizações" subtitle="Histórico, monitoramento da fila e logs detalhados." />
      {workers && (
        <div className="mb-4 flex flex-wrap gap-2">
          {Object.entries(workers.stats).map(([name, st]) => (
            <div key={name} className="card px-3 py-2 text-xs">
              <p className="font-medium">{name}</p>
              <p className="text-muted">concorrência {st.pool?.["max-concurrency"] ?? "?"} · executando {workers.active[name]?.length ?? 0} · reservadas {workers.reserved[name]?.length ?? 0}</p>
            </div>
          ))}
          {!Object.keys(workers.stats).length && <p className="text-sm text-err">Nenhum worker conectado.</p>}
        </div>
      )}
      <div className="mb-4 flex flex-wrap gap-2">
        <Select className="w-48" value={kind} onChange={(e) => { setKind(e.target.value); setPage(1); }} options={[{ value: "", label: "Todos os tipos" }, ...Object.entries(JOB_LABEL).map(([value, label]) => ({ value, label }))]} />
        <Select className="w-48" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} options={[{ value: "", label: "Todos os status" }, ...["queued", "running", "completed", "failed", "cancelled"].map((s) => ({ value: s, label: STATUS_LABEL[s] }))]} />
      </div>
      {!data ? <PageLoader /> : (
        <div className="card overflow-x-auto">
          <table className="w-full min-w-[820px] text-sm">
            <thead className="border-b border-line text-left text-xs text-muted"><tr>{["Tipo", "Projeto / usuário", "Status", "Progresso", "Criada", "Duração", "Tent.", ""].map((h) => <th key={h} className="px-4 py-2.5 font-medium">{h}</th>)}</tr></thead>
            <tbody>{data.items.map((j) => (
              <tr key={j.id} className="cursor-pointer border-b border-line/60 last:border-0 hover:bg-surface-2" onClick={() => setOpen(j.id)}>
                <td className="px-4 py-2.5 font-medium">{JOB_LABEL[j.kind]}</td>
                <td className="px-4"><p className="truncate">{j.project_name ?? "—"}</p><p className="text-xs text-muted">{j.user_email}</p></td>
                <td className="px-4"><StatusBadge status={j.status} /></td>
                <td className="w-40 px-4">{["queued", "running"].includes(j.status) ? <Progress value={j.progress} /> : <span className="line-clamp-1 text-xs text-muted" title={j.error ?? ""}>{j.error ?? j.stage}</span>}</td>
                <td className="px-4 text-xs text-muted">{fmtDate(j.created_at)}</td>
                <td className="px-4 text-xs tabular-nums">{j.duration_seconds != null ? `${j.duration_seconds}s` : "—"}</td>
                <td className="px-4 text-xs">{j.attempts}</td>
                <td className="px-4" onClick={(e) => e.stopPropagation()}>
                  {["queued", "running"].includes(j.status) ? <Button size="sm" variant="ghost" icon={<X className="size-3.5" />} onClick={() => act.mutate({ id: j.id, action: "cancel" })}>Cancelar</Button>
                    : ["failed", "cancelled"].includes(j.status) && j.kind !== "model_pull" ? <Button size="sm" variant="ghost" icon={<RotateCw className="size-3.5" />} onClick={() => act.mutate({ id: j.id, action: "retry" })}>Repetir</Button> : null}
                </td>
              </tr>))}
            </tbody>
          </table>
          <div className="flex justify-end gap-3 p-3 text-xs">
            <button disabled={page <= 1} onClick={() => setPage(page - 1)} className="text-muted disabled:opacity-30">Anterior</button>
            <button disabled={page * 50 >= data.total} onClick={() => setPage(page + 1)} className="text-muted disabled:opacity-30">Próxima</button>
          </div>
        </div>
      )}
      <Modal open={!!open} onClose={() => setOpen(null)} title="Detalhes da tarefa" wide>
        {!detail ? <PageLoader /> : (
          <div className="flex flex-col gap-3 text-sm">
            <div className="flex flex-wrap items-center gap-2"><StatusBadge status={detail.status} /><span className="text-muted">{JOB_LABEL[detail.kind]} · {detail.stage} · {Math.round(detail.progress)}%</span></div>
            {detail.error && <pre className="whitespace-pre-wrap rounded-lg bg-err/10 p-3 text-xs text-err">{detail.error}</pre>}
            <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-lg bg-black/40 p-3 font-mono text-xs leading-relaxed text-muted">{detail.logs || "Sem logs."}</pre>
            <pre className="overflow-auto rounded-lg bg-surface-2 p-3 font-mono text-[11px] text-subtle">{JSON.stringify({ params: detail.params, result: detail.result }, null, 2)}</pre>
          </div>
        )}
      </Modal>
    </div>
  );
}
