import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { AlertTriangle, ArrowLeft, Check, Clapperboard, Download, Eye, Film, Image as ImageIcon, Loader2, Mic, MonitorPlay, Plus, Sparkles } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { JobRow } from "@/components/shared";
import { useToast } from "@/components/toast";
import { Button, ConfirmModal, PageLoader, StatusBadge, Tabs } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtSec } from "@/lib/format";
import { useOptions, useProject } from "@/lib/hooks";
import type { Asset, Company, Job, Project, Scene, Timeline } from "@/lib/types";
import { SceneInspector } from "./Inspector";
import { Player } from "./Player";
import { ProjectPanel, type SettingsPatch } from "./ProjectPanel";
import { TimelineBar } from "./TimelineBar";

type View = "live" | "preview" | "final";
type ScenePatch = Partial<Scene> & { image_asset_id?: string | null; clear_image?: boolean };

function deepMerge<T extends object>(a: T, b: Partial<T>): T {
  const out = { ...a } as Record<string, unknown>;
  for (const [k, v] of Object.entries(b)) {
    const cur = out[k];
    out[k] = v && typeof v === "object" && !Array.isArray(v) && cur && typeof cur === "object" ? deepMerge(cur as object, v as object) : v;
  }
  return out as T;
}

export default function Editor() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const toast = useToast();
  const { data: opts } = useOptions();
  const [view, setView] = useState<View>("live");
  const [panel, setPanel] = useState<"scene" | "project">("scene");
  const [selected, setSelected] = useState<string | null>(null);
  const [time, setTime] = useState(0);
  const [saving, setSaving] = useState(false);
  const [confirmDel, setConfirmDel] = useState<Scene | null>(null);
  const pending = useRef<{ scenes: Map<string, ScenePatch>; settings: SettingsPatch | null; project: { name?: string; company?: Company } }>({ scenes: new Map(), settings: null, project: {} });
  const timer = useRef<number | undefined>(undefined);

  const { data: project, isLoading } = useProject(id, (p) => {
    const j = p.jobs[0];
    if (!j) return;
    if (j.status === "completed" && (j.kind === "render" || j.kind === "preview")) setView(j.kind === "render" ? "final" : "preview");
    if (j.status === "failed") toast(`Falha: ${j.error ?? "erro desconhecido"}`, "error");
  });
  const { data: timeline } = useQuery({ queryKey: ["timeline", id], enabled: !!id, queryFn: () => api<Timeline>(`/projects/${id}/timeline`) });

  useEffect(() => {
    if (project && !selected && project.scenes[0]) setSelected(project.scenes[0].id);
  }, [project, selected]);

  const setProject = useCallback((fn: (p: Project) => Project) => qc.setQueryData<Project>(["project", id], (p) => (p ? fn(p) : p)), [qc, id]);

  const flush = useCallback(async () => {
    const pend = pending.current;
    const scenes = [...pend.scenes.entries()];
    const settings = pend.settings;
    const proj = pend.project;
    pend.scenes = new Map();
    pend.settings = null;
    pend.project = {};
    if (!scenes.length && !settings && !proj.name && !proj.company) return;
    setSaving(true);
    try {
      await Promise.all(scenes.map(([sid, patch]) => api(`/projects/${id}/scenes/${sid}`, { method: "PATCH", body: patch })));
      if (settings || proj.name || proj.company) {
        const fresh = await api<Project>(`/projects/${id}`, { method: "PATCH", body: { ...(settings && { settings }), ...proj } });
        if (!pending.current.settings && !pending.current.scenes.size) qc.setQueryData(["project", id], fresh);
      } else if (scenes.some(([, p]) => "narration" in p) && !pending.current.scenes.size) {
        qc.invalidateQueries({ queryKey: ["project", id] });
      }
      qc.invalidateQueries({ queryKey: ["timeline", id] });
    } catch (e) {
      toast(`Erro ao salvar: ${(e as Error).message}`, "error");
      qc.invalidateQueries({ queryKey: ["project", id] });
    } finally {
      setSaving(false);
    }
  }, [id, qc, toast]);

  const schedule = useCallback(() => {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => void flush(), 650);
  }, [flush]);

  useEffect(() => () => { window.clearTimeout(timer.current); void flush(); }, [flush]);

  const patchScene = (sid: string, patch: ScenePatch, image?: Asset | null) => {
    setProject((p) => ({
      ...p,
      scenes: p.scenes.map((s) => s.id === sid ? { ...s, ...patch, ...(image !== undefined && { image }), ...("narration" in patch && { narration_stale: true }) } as Scene : s),
    }));
    pending.current.scenes.set(sid, { ...pending.current.scenes.get(sid), ...patch });
    schedule();
  };
  const patchSettings = (patch: SettingsPatch) => {
    setProject((p) => ({ ...p, settings: deepMerge(p.settings, patch as Partial<Project["settings"]>) }));
    pending.current.settings = deepMerge((pending.current.settings ?? {}) as object, patch) as SettingsPatch;
    schedule();
  };
  const patchProject = (patch: { name?: string; company?: Company }) => {
    setProject((p) => ({ ...p, ...patch }));
    pending.current.project = { ...pending.current.project, ...patch };
    schedule();
  };

  const startJob = useMutation({
    mutationFn: async ({ path, body }: { path: string; body?: Record<string, unknown> }) => {
      window.clearTimeout(timer.current);
      await flush();
      return api<Job>(`/projects/${id}/${path}`, { method: "POST", body: body ?? {} });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["project", id] }),
    onError: (e) => toast((e as Error).message, "error"),
  });
  const structural = useMutation({
    mutationFn: async (fn: () => Promise<Project>) => { window.clearTimeout(timer.current); await flush(); return fn(); },
    onSuccess: (p) => { qc.setQueryData(["project", id], p); qc.invalidateQueries({ queryKey: ["timeline", id] }); },
    onError: (e) => toast((e as Error).message, "error"),
  });

  if (isLoading || !project || !opts) return <PageLoader />;

  const idx = project.scenes.findIndex((s) => s.id === selected);
  const scene = idx >= 0 ? project.scenes[idx] : null;
  const job = project.active_job;
  const busy = !!job;
  const missingImages = project.scenes.filter((s) => !s.image).length;
  const staleNarr = project.settings.narration_enabled && project.settings.narration_mode === "tts" && project.scenes.some((s) => s.narration_stale);

  const addScene = () => structural.mutate(() => api<Project>(`/projects/${id}/scenes`, { body: { position: idx >= 0 ? idx + 1 : project.scenes.length, title: "Nova cena", narration: "" } }));
  const duplicateScene = (s: Scene) => structural.mutate(() => api<Project>(`/projects/${id}/scenes`, {
    body: { position: s.position + 1, role: s.role, title: s.title, subtitle: s.subtitle, narration: s.narration, caption_override: s.caption_override, image_prompt: s.image_prompt, duration: s.duration, transition: s.transition, motion: s.motion, text_animation: s.text_animation, text_position: s.text_position, fit: s.fit, image_asset_id: s.image?.id ?? null },
  }));
  const reorder = (ids: string[]) => {
    setProject((p) => ({ ...p, scenes: ids.map((sid, i) => ({ ...p.scenes.find((s) => s.id === sid)!, position: i })) }));
    structural.mutate(() => api<Project>(`/projects/${id}/scenes/reorder`, { body: { scene_ids: ids } }));
  };
  const seek = (t: number) => {
    setTime(t);
    const ts = timeline?.scenes.find((x) => t >= x.start && t < x.start + x.duration);
    if (ts) setSelected(ts.id);
  };
  const selectScene = (sid: string) => {
    setSelected(sid);
    setPanel("scene");
    const ts = timeline?.scenes.find((x) => x.id === sid);
    if (ts) setTime(ts.start + 0.01);
  };

  const viewAsset = view === "final" ? project.output : view === "preview" ? project.preview : null;

  return (
    <div className="flex min-h-dvh flex-col bg-bg lg:h-dvh">
      <header className="flex shrink-0 flex-wrap items-center gap-2 border-b border-line bg-surface px-3 py-2 sm:px-4">
        <Link to="/projetos" aria-label="Voltar" className="flex size-8 items-center justify-center rounded-lg text-muted hover:bg-surface-3 hover:text-fg"><ArrowLeft className="size-4" /></Link>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h1 className="truncate text-sm font-semibold">{project.name}</h1>
            <StatusBadge status={project.status} />
          </div>
          <p className="flex items-center gap-1 text-[11px] text-muted">
            {saving ? <><Loader2 className="size-3 animate-spin" />Salvando...</> : <><Check className="size-3" />Salvo</>}
            <span className="mx-1">·</span>{project.settings.format} · {fmtSec(timeline?.total)} / alvo {project.settings.duration}s
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <Button size="sm" icon={<ImageIcon className="size-3.5" />} disabled={busy || !project.scenes.length} title="Gera imagens para cenas sem imagem"
            onClick={() => startJob.mutate({ path: "images", body: { force: false } })}>Gerar imagens{missingImages ? ` (${missingImages})` : ""}</Button>
          <Button size="sm" icon={<Mic className="size-3.5" />} disabled={busy || !project.settings.narration_enabled || project.settings.narration_mode !== "tts"}
            onClick={() => startJob.mutate({ path: "narration", body: { force: false } })}>Gerar narração</Button>
          <Button size="sm" icon={<Eye className="size-3.5" />} disabled={busy || !project.scenes.length} onClick={() => startJob.mutate({ path: "preview" })}>Prévia rápida</Button>
          <Button size="sm" variant="primary" icon={<Sparkles className="size-3.5" />} disabled={busy || !project.scenes.length} onClick={() => startJob.mutate({ path: "render" })}>Renderizar MP4</Button>
          {project.output && <a href={project.output.download_url}><Button size="sm" icon={<Download className="size-3.5" />}>Baixar</Button></a>}
        </div>
      </header>

      {job && (
        <div className="shrink-0 border-b border-line bg-surface-2 px-4 py-2"><div className="mx-auto max-w-3xl"><JobRow job={job} compact /></div></div>
      )}
      {!job && (timeline?.warnings.length || staleNarr) ? (
        <div className="flex shrink-0 items-start gap-2 border-b border-warn/20 bg-warn/5 px-4 py-1.5 text-[11px] text-warn">
          <AlertTriangle className="mt-0.5 size-3 shrink-0" />
          <span>{[...(timeline?.warnings ?? []), ...(staleNarr ? ["Há narrações desatualizadas: a duração exibida é estimada até gerar a narração."] : [])].join(" ")}</span>
        </div>
      ) : null}

      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <section className="flex min-h-[420px] flex-1 flex-col gap-3 p-3 sm:p-4">
          <Tabs className="mx-auto w-full max-w-md" value={view} onChange={setView} tabs={[
            { value: "live", label: "Ao vivo", icon: <MonitorPlay className="size-3.5" /> },
            { value: "preview", label: "Prévia renderizada", icon: <Eye className="size-3.5" /> },
            { value: "final", label: "Vídeo final", icon: <Film className="size-3.5" /> },
          ]} />
          <div className="min-h-0 flex-1">
            {view === "live" ? (
              <Player project={project} timeline={timeline} onSelect={setSelected} time={time} setTime={setTime} />
            ) : viewAsset ? (
              <div className="flex h-full flex-col items-center justify-center gap-2">
                <video key={viewAsset.id} src={viewAsset.url} controls className="max-h-full max-w-full rounded-lg bg-black shadow-2xl" />
                <p className="text-[11px] text-muted">{viewAsset.width}×{viewAsset.height} · {fmtSec(viewAsset.duration)}</p>
              </div>
            ) : (
              <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
                <Clapperboard className="size-8 text-subtle" />
                <p className="max-w-xs text-sm text-muted">{view === "preview" ? "Gere uma prévia rápida em baixa resolução para conferir o resultado real antes de exportar." : "Nenhum vídeo final ainda. Clique em “Renderizar MP4”."}</p>
                <Button size="sm" variant={view === "final" ? "primary" : "secondary"} disabled={busy || !project.scenes.length}
                  onClick={() => startJob.mutate({ path: view === "preview" ? "preview" : "render" })}>{view === "preview" ? "Gerar prévia" : "Renderizar"}</Button>
              </div>
            )}
          </div>
        </section>
        <aside className="flex max-h-none shrink-0 flex-col border-t border-line bg-surface lg:w-[360px] lg:border-l lg:border-t-0 xl:w-[400px]">
          <div className="border-b border-line p-3">
            <Tabs value={panel} onChange={setPanel} tabs={[{ value: "scene", label: "Cena" }, { value: "project", label: "Projeto" }]} />
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto p-4">
            {panel === "scene" ? (scene ? (
              <SceneInspector key={scene.id} scene={scene} index={idx} opts={opts} busy={startJob.isPending && startJob.variables?.path === "images"}
                onChange={(patch, image) => patchScene(scene.id, patch, image)}
                onDelete={() => setConfirmDel(scene)} onDuplicate={() => duplicateScene(scene)}
                onGenerateImage={() => startJob.mutate({ path: "images", body: { scene_ids: [scene.id], force: true } })} />
            ) : (
              <div className="flex flex-col items-center gap-3 py-10 text-center text-sm text-muted">
                Nenhuma cena selecionada.
                <Button size="sm" icon={<Plus className="size-3.5" />} onClick={addScene}>Adicionar cena</Button>
              </div>
            )) : (
              <ProjectPanel project={project} opts={opts} onSettings={patchSettings} onCompany={(company) => patchProject({ company })} onName={(name) => patchProject({ name })} />
            )}
          </div>
        </aside>
      </div>

      <div className={clsx("shrink-0", busy && "pointer-events-none opacity-60")}>
        <TimelineBar project={project} timeline={timeline} selectedId={selected} onSelect={selectScene} onReorder={reorder}
          onResize={(sid, d) => patchScene(sid, { duration: d })} onAdd={addScene} time={time} onSeek={seek} />
      </div>

      <ConfirmModal open={!!confirmDel} danger title="Remover cena" confirmLabel="Remover" text={`Remover a cena "${confirmDel?.title || "sem título"}"?`}
        onClose={() => setConfirmDel(null)}
        onConfirm={() => {
          const sid = confirmDel!.id;
          setConfirmDel(null);
          setSelected(null);
          pending.current.scenes.delete(sid);
          structural.mutate(() => api<Project>(`/projects/${id}/scenes/${sid}`, { method: "DELETE" }));
        }} />
    </div>
  );
}
