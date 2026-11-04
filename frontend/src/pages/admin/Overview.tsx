import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { CheckCircle2, Cpu, HardDrive, MemoryStick, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { JobRow } from "@/components/shared";
import { Card, PageHeader, PageLoader, Progress } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtBytes } from "@/lib/format";
import type { Job } from "@/lib/types";

export interface Resources { cpu_percent: number; cpu_count: number; load_avg: number[]; ram_total: number; ram_used: number; ram_percent: number; disk_total: number; disk_used: number; disk_free: number; disk_percent: number; api_uptime_seconds: number }
interface Overview { users: number; projects: number; videos: number; renders_24h: number; failures_24h: number; errors_24h: number; jobs_by_status: Record<string, number>; active_jobs: Job[]; resources: Resources }
type Svc = Record<string, { online?: boolean; error?: string; [k: string]: unknown }>;

function Spark({ data, color }: { data: number[]; color: string }) {
  if (data.length < 2) return <div className="h-10" />;
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * 100},${40 - (v / 100) * 38}`).join(" ");
  return (
    <svg viewBox="0 0 100 40" preserveAspectRatio="none" className="h-10 w-full" aria-hidden>
      <polyline points={`0,40 ${pts} 100,40`} fill={color} fillOpacity={0.12} stroke="none" />
      <polyline points={pts} fill="none" stroke={color} strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

function ServiceRow({ name, s, detail }: { name: string; s?: { online?: boolean; error?: string }; detail?: string }) {
  const ok = !!s?.online;
  return (
    <div className="flex items-start gap-3 border-b border-line/60 py-2.5 last:border-0">
      {ok ? <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-ok" /> : <XCircle className="mt-0.5 size-4 shrink-0 text-err" />}
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium">{name}</p>
        <p className={clsx("truncate text-[11px]", ok ? "text-muted" : "text-err/80")} title={s?.error ?? detail}>{ok ? detail : s?.error ?? "offline"}</p>
      </div>
    </div>
  );
}

export default function AdminOverview() {
  const { data } = useQuery({ queryKey: ["admin", "overview"], queryFn: () => api<Overview>("/admin/overview"), refetchInterval: 5000 });
  const { data: svc } = useQuery({ queryKey: ["admin", "services"], queryFn: () => api<Svc>("/admin/services"), refetchInterval: 20000 });
  const [hist, setHist] = useState<{ cpu: number[]; ram: number[] }>({ cpu: [], ram: [] });
  useEffect(() => {
    if (data) setHist((h) => ({ cpu: [...h.cpu, data.resources.cpu_percent].slice(-40), ram: [...h.ram, data.resources.ram_percent].slice(-40) }));
  }, [data]);
  if (!data) return <PageLoader />;
  const r = data.resources;
  const tts = (svc?.tts?.providers ?? {}) as Record<string, boolean>;
  return (
    <div className="animate-fade-in">
      <PageHeader title="Visão geral" subtitle={`API ativa há ${Math.floor(r.api_uptime_seconds / 3600)}h ${Math.floor((r.api_uptime_seconds % 3600) / 60)}min`} />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {[["Usuários", data.users], ["Projetos", data.projects], ["Vídeos", data.videos], ["Renders 24h", data.renders_24h], ["Falhas 24h", data.failures_24h], ["Erros 24h", data.errors_24h]].map(([l, v]) => (
          <Card key={l as string} className="p-4"><p className="text-2xl font-semibold tabular-nums">{v}</p><p className="text-xs text-muted">{l}</p></Card>
        ))}
      </div>
      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        <Card className="p-4">
          <div className="mb-2 flex items-center justify-between text-sm"><span className="flex items-center gap-2"><Cpu className="size-4 text-ember" />CPU ({r.cpu_count} núcleos)</span><span className="tabular-nums">{r.cpu_percent.toFixed(0)}%</span></div>
          <Spark data={hist.cpu} color="#ff6b2c" />
          <p className="mt-1 text-[11px] text-muted">Carga média: {r.load_avg.join(" · ")}</p>
        </Card>
        <Card className="p-4">
          <div className="mb-2 flex items-center justify-between text-sm"><span className="flex items-center gap-2"><MemoryStick className="size-4 text-ember" />RAM</span><span className="tabular-nums">{fmtBytes(r.ram_used)} / {fmtBytes(r.ram_total)}</span></div>
          <Spark data={hist.ram} color="#60a5fa" />
          <Progress value={r.ram_percent} className="mt-1" />
        </Card>
        <Card className="p-4">
          <div className="mb-2 flex items-center justify-between text-sm"><span className="flex items-center gap-2"><HardDrive className="size-4 text-ember" />Disco</span><span className="tabular-nums">{fmtBytes(r.disk_free)} livres</span></div>
          <p className="mb-3 mt-4 text-2xl font-semibold tabular-nums">{r.disk_percent}%</p>
          <Progress value={r.disk_percent} />
          <p className="mt-1 text-[11px] text-muted">{fmtBytes(r.disk_used)} de {fmtBytes(r.disk_total)}</p>
        </Card>
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_380px]">
        <Card className="p-4">
          <h2 className="mb-3 font-medium">Tarefas ativas</h2>
          {data.active_jobs.length ? <div className="flex flex-col gap-2">{data.active_jobs.map((j) => <JobRow key={j.id} job={j} />)}</div> : <p className="text-sm text-muted">Fila vazia.</p>}
          <div className="mt-4 flex flex-wrap gap-2 text-xs text-muted">{Object.entries(data.jobs_by_status).map(([k, v]) => <span key={k} className="rounded-md bg-surface-3 px-2 py-1">{k}: {v}</span>)}</div>
        </Card>
        <Card className="p-4">
          <h2 className="mb-1 font-medium">Status dos serviços</h2>
          {!svc ? <PageLoader /> : <>
            <ServiceRow name="PostgreSQL" s={svc.database} detail={`${svc.database?.latency_ms} ms`} />
            <ServiceRow name="Redis" s={svc.redis} detail={`${svc.redis?.latency_ms} ms`} />
            <ServiceRow name="Workers Celery" s={svc.workers} detail={`${svc.workers?.count} ativo(s)`} />
            <ServiceRow name="FFmpeg" s={svc.ffmpeg} detail={String(svc.ffmpeg?.version ?? "")} />
            <ServiceRow name={`Ollama (LLM)${svc.ollama?.active ? "" : " — inativo"}`} s={svc.ollama} detail={`${svc.ollama?.model} ${svc.ollama?.model_ready ? "✓ baixado" : "· modelo não baixado"}`} />
            <ServiceRow name={`ComfyUI (imagens)${svc.comfyui?.active ? "" : " — inativo"}`} s={svc.comfyui} detail={`${(svc.comfyui?.devices as string[] | undefined)?.join(", ") ?? ""}`} />
            <ServiceRow name="Síntese de voz" s={{ online: Object.values(tts).some(Boolean) }} detail={Object.entries(tts).map(([k, v]) => `${k} ${v ? "✓" : "✗"}`).join(" · ")} />
          </>}
        </Card>
      </div>
    </div>
  );
}
