import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, Download, FolderOpen, Plus, Search, Trash2, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ProjectCard } from "@/components/shared";
import { useToast } from "@/components/toast";
import { Button, ConfirmModal, Empty, IconButton, Input, PageHeader, PageLoader, Select } from "@/components/ui";
import { api, download } from "@/lib/api";
import { STATUS_LABEL } from "@/lib/format";
import type { Page, Project, ProjectSummary } from "@/lib/types";

export default function Projects() {
  const qc = useQueryClient();
  const toast = useToast();
  const nav = useNavigate();
  const [params, setParams] = useSearchParams();
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [del, setDel] = useState<ProjectSummary | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const status = params.get("status") ?? "";
  const qs = new URLSearchParams({ page: String(page), page_size: "24", ...(q && { q }), ...(status && { status }) });
  const { data, isLoading } = useQuery({ queryKey: ["projects", qs.toString()], queryFn: () => api<Page<ProjectSummary>>(`/projects?${qs}`), placeholderData: keepPreviousData });

  const refresh = () => { qc.invalidateQueries({ queryKey: ["projects"] }); qc.invalidateQueries({ queryKey: ["dashboard"] }); };
  const dup = useMutation({ mutationFn: (id: string) => api<Project>(`/projects/${id}/duplicate`, { method: "POST" }), onSuccess: () => { toast("Projeto duplicado", "success"); refresh(); }, onError: (e) => toast((e as Error).message, "error") });
  const remove = useMutation({ mutationFn: (id: string) => api(`/projects/${id}`, { method: "DELETE" }), onSuccess: () => { toast("Projeto excluído", "success"); setDel(null); refresh(); }, onError: (e) => toast((e as Error).message, "error") });
  const imp = useMutation({
    mutationFn: (f: File) => { const fd = new FormData(); fd.append("file", f); return api<Project>("/projects/import", { body: fd }); },
    onSuccess: (p) => { toast("Projeto importado", "success"); refresh(); nav(`/projetos/${p.id}/editor`); },
    onError: (e) => toast((e as Error).message, "error"),
  });
  const exportProject = async (p: ProjectSummary) => {
    try { await download(`/projects/${p.id}/export`, `${p.name}.forja.zip`); } catch (e) { toast((e as Error).message, "error"); }
  };
  const pages = data ? Math.ceil(data.total / 24) : 1;

  return (
    <div className="animate-fade-in">
      <PageHeader title="Projetos" subtitle={data ? `${data.total} projeto(s)` : undefined} actions={<>
        <input ref={fileRef} type="file" accept=".zip" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) imp.mutate(f); e.target.value = ""; }} />
        <Button icon={<Upload className="size-4" />} loading={imp.isPending} onClick={() => fileRef.current?.click()}>Importar</Button>
        <Link to="/novo"><Button variant="primary" icon={<Plus className="size-4" />}>Novo vídeo</Button></Link>
      </>} />
      <div className="mb-5 flex flex-col gap-2 sm:flex-row">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-subtle" />
          <Input placeholder="Buscar projetos..." className="pl-9" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
        </div>
        <Select className="sm:w-56" value={status} onChange={(e) => { setPage(1); setParams(e.target.value ? { status: e.target.value } : {}); }}
          options={[{ value: "", label: "Todos os status" }, ...Object.entries(STATUS_LABEL).filter(([k]) => ["draft", "ready", "processing", "completed", "failed"].includes(k)).map(([value, label]) => ({ value, label }))]} />
      </div>
      {isLoading ? <PageLoader /> : !data?.items.length ? (
        <Empty icon={<FolderOpen className="size-5" />} title="Nenhum projeto encontrado" action={<Link to="/novo"><Button variant="primary">Criar vídeo</Button></Link>} />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {data.items.map((p) => (
            <ProjectCard key={p.id} p={p} actions={<>
              <IconButton label="Duplicar" onClick={() => dup.mutate(p.id)}><Copy className="size-3.5" /></IconButton>
              <IconButton label="Exportar projeto (.zip)" onClick={() => exportProject(p)}><Download className="size-3.5" /></IconButton>
              <IconButton label="Excluir" className="hover:!text-err" onClick={() => setDel(p)}><Trash2 className="size-3.5" /></IconButton>
            </>} />
          ))}
        </div>
      )}
      {pages > 1 && (
        <div className="mt-6 flex items-center justify-center gap-3 text-sm">
          <Button size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Anterior</Button>
          <span className="text-muted">{page} / {pages}</span>
          <Button size="sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>Próxima</Button>
        </div>
      )}
      <ConfirmModal open={!!del} danger title="Excluir projeto" confirmLabel="Excluir"
        text={`O projeto "${del?.name}" e seus vídeos renderizados serão excluídos permanentemente. Imagens enviadas por você permanecem na biblioteca.`}
        loading={remove.isPending} onConfirm={() => del && remove.mutate(del.id)} onClose={() => setDel(null)} />
    </div>
  );
}
