import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, Trash2 } from "lucide-react";
import { useState } from "react";
import { useToast } from "@/components/toast";
import { Badge, Button, ConfirmModal, Empty, Input, PageHeader, PageLoader } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDate } from "@/lib/format";

interface Log { id: string; source: string; level: string; message: string; traceback: string | null; context: Record<string, unknown>; created_at: string }

export default function AdminLogs() {
  const qc = useQueryClient();
  const toast = useToast();
  const [source, setSource] = useState("");
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState<string | null>(null);
  const [clear, setClear] = useState(false);
  const { data } = useQuery({ queryKey: ["admin", "logs", source, page], queryFn: () => api<{ total: number; items: Log[] }>(`/admin/logs?page=${page}${source ? `&source=${encodeURIComponent(source)}` : ""}`), refetchInterval: 15000 });
  const wipe = useMutation({ mutationFn: () => api("/admin/logs", { method: "DELETE" }), onSuccess: () => { toast("Logs removidos", "success"); setClear(false); qc.invalidateQueries({ queryKey: ["admin", "logs"] }); } });
  return (
    <div className="animate-fade-in">
      <PageHeader title="Logs de erros" subtitle={data ? `${data.total} registro(s)` : undefined} actions={<Button variant="danger" icon={<Trash2 className="size-4" />} onClick={() => setClear(true)}>Limpar logs</Button>} />
      <Input className="mb-4 max-w-xs" placeholder="Filtrar por origem (api, worker...)" value={source} onChange={(e) => { setSource(e.target.value); setPage(1); }} />
      {!data ? <PageLoader /> : !data.items.length ? <Empty icon={<ChevronDown className="size-5" />} title="Nenhum erro registrado" /> : (
        <div className="flex flex-col gap-2">
          {data.items.map((l) => (
            <div key={l.id} className="card overflow-hidden">
              <button className="flex w-full items-start gap-3 p-3 text-left hover:bg-surface-2" onClick={() => setOpen(open === l.id ? null : l.id)}>
                <Badge className="shrink-0 !text-err">{l.source}</Badge>
                <span className="min-w-0 flex-1 truncate text-sm">{l.message}</span>
                <span className="shrink-0 text-[11px] text-muted">{fmtDate(l.created_at)}</span>
              </button>
              {open === l.id && (
                <div className="border-t border-line p-3">
                  <p className="mb-2 whitespace-pre-wrap text-sm">{l.message}</p>
                  {Object.keys(l.context).length > 0 && <pre className="mb-2 text-xs text-muted">{JSON.stringify(l.context, null, 2)}</pre>}
                  {l.traceback && <pre className="max-h-80 overflow-auto rounded-lg bg-black/40 p-3 font-mono text-[11px] text-subtle">{l.traceback}</pre>}
                </div>
              )}
            </div>
          ))}
          <div className="flex justify-end gap-3 text-xs">
            <button disabled={page <= 1} onClick={() => setPage(page - 1)} className="text-muted disabled:opacity-30">Anterior</button>
            <button disabled={page * 50 >= data.total} onClick={() => setPage(page + 1)} className="text-muted disabled:opacity-30">Próxima</button>
          </div>
        </div>
      )}
      <ConfirmModal open={clear} danger title="Limpar logs" text="Remover todos os registros de erro?" loading={wipe.isPending} onConfirm={() => wipe.mutate()} onClose={() => setClear(false)} />
    </div>
  );
}
