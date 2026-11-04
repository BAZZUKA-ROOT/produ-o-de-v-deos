import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, Search, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useToast } from "@/components/toast";
import { ConfirmModal, IconButton, Input, PageHeader, PageLoader, StatusBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import type { ProjectSummary } from "@/lib/types";

export default function AdminProjects() {
  const qc = useQueryClient();
  const toast = useToast();
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [del, setDel] = useState<ProjectSummary | null>(null);
  const { data } = useQuery({ queryKey: ["admin", "projects", q, page], queryFn: () => api<{ total: number; items: ProjectSummary[] }>(`/admin/projects?page=${page}${q ? `&q=${encodeURIComponent(q)}` : ""}`) });
  const remove = useMutation({ mutationFn: (id: string) => api(`/admin/projects/${id}`, { method: "DELETE" }), onSuccess: () => { toast("Projeto excluído", "success"); setDel(null); qc.invalidateQueries({ queryKey: ["admin", "projects"] }); } });
  return (
    <div className="animate-fade-in">
      <PageHeader title="Projetos" subtitle={data ? `${data.total} no total` : undefined} />
      <div className="relative mb-4 max-w-sm"><Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-subtle" /><Input className="pl-9" placeholder="Buscar" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} /></div>
      {!data ? <PageLoader /> : (
        <div className="card overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead className="border-b border-line text-left text-xs text-muted"><tr>{["Projeto", "Dono", "Status", "Formato", "Atualizado", ""].map((h) => <th key={h} className="px-4 py-2.5 font-medium">{h}</th>)}</tr></thead>
            <tbody>{data.items.map((p) => (
              <tr key={p.id} className="border-b border-line/60 last:border-0">
                <td className="px-4 py-2.5 font-medium">{p.name}</td>
                <td className="px-4 text-xs text-muted">{p.owner_email}</td>
                <td className="px-4"><StatusBadge status={p.status} /></td>
                <td className="px-4 text-xs">{p.format} · {p.duration}s · {p.scene_count} cenas</td>
                <td className="px-4 text-xs text-muted">{fmtDate(p.updated_at)}</td>
                <td className="px-4"><div className="flex">
                  <Link to={`/projetos/${p.id}/editor`} aria-label="Abrir" className="inline-flex size-8 items-center justify-center text-muted hover:text-fg"><ExternalLink className="size-4" /></Link>
                  <IconButton label="Excluir" className="hover:!text-err" onClick={() => setDel(p)}><Trash2 className="size-4" /></IconButton>
                </div></td>
              </tr>))}
            </tbody>
          </table>
          <div className="flex justify-end gap-2 p-3 text-xs">
            <button disabled={page <= 1} onClick={() => setPage(page - 1)} className="text-muted disabled:opacity-30">Anterior</button>
            <button disabled={page * 50 >= data.total} onClick={() => setPage(page + 1)} className="text-muted disabled:opacity-30">Próxima</button>
          </div>
        </div>
      )}
      <ConfirmModal open={!!del} danger title="Excluir projeto" confirmLabel="Excluir" text={`Excluir "${del?.name}" de ${del?.owner_email}?`} loading={remove.isPending} onConfirm={() => del && remove.mutate(del.id)} onClose={() => setDel(null)} />
    </div>
  );
}
