import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Broom, ScanSearch } from "@/pages/admin/icons";
import { useToast } from "@/components/toast";
import { Button, Card, PageHeader, PageLoader, Progress } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtBytes } from "@/lib/format";
import { SettingsCard, type Values } from "./settingsForm";

interface Info { storage_dir: string; temp_dir: string; models_dir: string; storage_bytes: number; temp_bytes: number; models_bytes: number; disk_total: number; disk_free: number; by_kind: { kind: string; count: number; bytes: number }[]; settings: Values }

export default function AdminStorage() {
  const qc = useQueryClient();
  const toast = useToast();
  const { data } = useQuery({ queryKey: ["admin", "storage"], queryFn: () => api<Info>("/admin/storage") });
  const clean = useMutation({ mutationFn: () => api<{ removed: number }>("/admin/storage/cleanup-temp", { method: "POST" }), onSuccess: (r) => { toast(`${r.removed} item(ns) temporário(s) removido(s)`, "success"); qc.invalidateQueries({ queryKey: ["admin", "storage"] }); } });
  const scan = useMutation({ mutationFn: (del: boolean) => api<{ orphans: number; orphan_bytes: number; deleted: boolean; missing_files: string[] }>(`/admin/storage/scan-orphans?delete=${del}`, { method: "POST" }),
    onSuccess: (r) => toast(`${r.orphans} arquivo(s) órfão(s) (${fmtBytes(r.orphan_bytes)})${r.deleted ? " removidos" : ""}. ${r.missing_files.length} registro(s) sem arquivo.`, "info") });
  if (!data) return <PageLoader />;
  const used = data.disk_total - data.disk_free;
  return (
    <div className="flex max-w-4xl flex-col gap-4 animate-fade-in">
      <PageHeader title="Armazenamento" />
      <Card className="p-5">
        <div className="mb-2 flex justify-between text-sm"><span>Disco do servidor</span><span className="text-muted">{fmtBytes(used)} / {fmtBytes(data.disk_total)}</span></div>
        <Progress value={(used / data.disk_total) * 100} />
        <div className="mt-5 grid gap-3 sm:grid-cols-3">
          {[["Arquivos de usuários", data.storage_bytes, data.storage_dir], ["Temporários", data.temp_bytes, data.temp_dir], ["Modelos de IA", data.models_bytes, data.models_dir]].map(([l, b, p]) => (
            <div key={l as string} className="rounded-lg bg-surface-2 p-3"><p className="text-lg font-semibold">{fmtBytes(b as number)}</p><p className="text-xs text-muted">{l}</p><p className="mt-1 truncate font-mono text-[10px] text-subtle" title={p as string}>{p}</p></div>
          ))}
        </div>
        <div className="mt-5 grid gap-2 sm:grid-cols-5">
          {data.by_kind.map((k) => <div key={k.kind} className="rounded-lg border border-line p-2 text-xs"><p className="font-medium capitalize">{k.kind}</p><p className="text-muted">{k.count} · {fmtBytes(k.bytes)}</p></div>)}
        </div>
        <div className="mt-5 flex flex-wrap gap-2">
          <Button icon={<Broom />} loading={clean.isPending} onClick={() => clean.mutate()}>Limpar temporários antigos</Button>
          <Button icon={<ScanSearch />} loading={scan.isPending && scan.variables === false} onClick={() => scan.mutate(false)}>Verificar órfãos</Button>
          <Button variant="danger" loading={scan.isPending && scan.variables === true} onClick={() => scan.mutate(true)}>Remover órfãos</Button>
        </div>
      </Card>
      <SettingsCard title="Limites" section="storage" values={data.settings} fields={[
        { key: "max_image_upload_mb", label: "Upload máx. de imagem (MB)", type: "number" },
        { key: "max_audio_upload_mb", label: "Upload máx. de áudio (MB)", type: "number" },
        { key: "user_quota_mb", label: "Cota padrão por usuário (MB)", type: "number" },
        { key: "temp_retention_hours", label: "Retenção de temporários (h)", type: "number" },
      ]} />
    </div>
  );
}
