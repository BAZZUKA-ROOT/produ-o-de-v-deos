import { useMutation, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { Clapperboard, Film, X } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { fmtDate, JOB_LABEL, label } from "@/lib/format";
import type { Job, ProjectSummary, Template } from "@/lib/types";
import { useToast } from "./toast";
import { Badge, IconButton, Progress, StatusBadge } from "./ui";

const ratio: Record<string, string> = { "9:16": "aspect-[9/16]", "1:1": "aspect-square", "16:9": "aspect-video", "4:5": "aspect-[4/5]" };

export function ProjectCard({ p, actions }: { p: ProjectSummary; actions?: React.ReactNode }) {
  return (
    <div className="card group flex flex-col overflow-hidden transition hover:border-line-strong">
      <Link to={`/projetos/${p.id}/editor`} className="relative block aspect-video overflow-hidden bg-surface-2">
        {p.thumbnail_url ? (
          <img src={p.thumbnail_url} alt="" loading="lazy" className="size-full object-cover transition duration-500 group-hover:scale-105" />
        ) : (
          <div className="flex size-full items-center justify-center text-subtle"><Clapperboard className="size-8" /></div>
        )}
        <div className="absolute left-2 top-2"><StatusBadge status={p.status} /></div>
        {p.has_video && <span className="absolute bottom-2 right-2 flex items-center gap-1 rounded-md bg-black/70 px-1.5 py-0.5 text-[11px]"><Film className="size-3" />MP4</span>}
      </Link>
      <div className="flex flex-1 flex-col gap-2 p-3.5">
        <Link to={`/projetos/${p.id}/editor`} className="line-clamp-1 text-sm font-medium hover:text-ember">{p.name}</Link>
        <div className="flex flex-wrap gap-1.5">
          <Badge>{p.format}</Badge><Badge>{p.duration}s</Badge><Badge>{p.scene_count} cenas</Badge>
        </div>
        <div className="mt-auto flex items-center justify-between pt-1">
          <span className="text-[11px] text-subtle">{fmtDate(p.updated_at)}</span>
          <div className="flex gap-0.5">{actions}</div>
        </div>
      </div>
    </div>
  );
}

export function TemplateThumb({ t, className }: { t: Pick<Template, "palette" | "font" | "name" | "category_label">; className?: string }) {
  const pal = t.palette ?? ["#111827", "#7C3AED", "#F472B6", "#FFFFFF"];
  return (
    <div className={clsx("relative flex aspect-[9/16] flex-col justify-end overflow-hidden rounded-lg p-3", className)}
      style={{ background: `radial-gradient(circle at 80% 15%, ${pal[2]}66, transparent 45%), linear-gradient(160deg, ${pal[0]}, ${pal[1]})` }}>
      <div className="absolute inset-x-3 top-1/3 h-1 rounded-full" style={{ background: pal[2] }} />
      <span className="text-[10px] uppercase tracking-wider opacity-70" style={{ color: pal[3] }}>{t.category_label}</span>
      <span className="text-sm font-bold leading-tight" style={{ color: pal[3], fontFamily: t.font ?? undefined }}>{t.name.split("·").pop()?.trim()}</span>
    </div>
  );
}

export function aspectClass(fmt: string) {
  return ratio[fmt] ?? ratio["9:16"];
}

export function JobRow({ job, compact }: { job: Job; compact?: boolean }) {
  const qc = useQueryClient();
  const toast = useToast();
  const cancel = useMutation({
    mutationFn: () => api(`/jobs/${job.id}/cancel`, { method: "POST" }),
    onSuccess: () => { toast("Cancelamento solicitado"); qc.invalidateQueries(); },
    onError: (e) => toast((e as Error).message, "error"),
  });
  const active = ["queued", "running"].includes(job.status);
  return (
    <div className={clsx("flex flex-col gap-2", !compact && "rounded-lg border border-line bg-surface-2 p-3")}>
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <span className="text-sm font-medium">{JOB_LABEL[job.kind] ?? job.kind}</span>
          <StatusBadge status={job.status} />
        </div>
        {active && <IconButton label="Cancelar tarefa" onClick={() => cancel.mutate()} disabled={cancel.isPending}><X className="size-4" /></IconButton>}
      </div>
      {active && <Progress value={job.progress} />}
      <div className="flex justify-between text-[11px] text-muted">
        <span className="truncate">{job.error ? <span className="text-err">{job.error.slice(0, 140)}</span> : job.stage}</span>
        {active && <span>{Math.round(job.progress)}%</span>}
      </div>
    </div>
  );
}

export const optionList = (values: string[]) => values.map((v) => ({ value: v, label: label(v) }));
export const recordOptions = (r: Record<string, string>) => Object.entries(r).map(([value, l]) => ({ value, label: l }));
