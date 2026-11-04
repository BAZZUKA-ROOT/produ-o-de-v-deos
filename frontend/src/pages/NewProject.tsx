import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { ArrowLeft, ArrowRight, Building2, Check, Clapperboard, ImagePlus, LayoutTemplate, RefreshCw, Settings2, Sparkles, Wand2, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { JobRow, recordOptions, TemplateThumb } from "@/components/shared";
import { useToast } from "@/components/toast";
import { Button, Card, Field, Input, PageHeader, PageLoader, Select, Textarea, Toggle } from "@/components/ui";
import { api } from "@/lib/api";
import { label } from "@/lib/format";
import { useOptions, useProject } from "@/lib/hooks";
import type { Asset, Company, Project, Scene, Template } from "@/lib/types";
import { useUpload } from "./Library";
import { TemplateGrid } from "./Templates";

const STEPS = [
  { label: "Template", icon: LayoutTemplate },
  { label: "Empresa", icon: Building2 },
  { label: "Vídeo", icon: Settings2 },
  { label: "Roteiro IA", icon: Wand2 },
];

const emptyCompany: Company = { name: "", segment: "", description: "", product: "", offer: "", audience: "", differentials: "", phone: "", whatsapp: "", instagram: "", address: "", website: "" };

interface Config { format: string; duration: number; style: string; video_type: string; music_mood: string; narration_enabled: boolean; voice_gender: "female" | "male"; voice_speed: number; subtitles_enabled: boolean; quality: string }

function Choice({ active, onClick, children, className }: { active: boolean; onClick: () => void; children: React.ReactNode; className?: string }) {
  return (
    <button type="button" onClick={onClick} className={clsx("rounded-lg border px-3 py-2.5 text-sm transition", active ? "border-ember/60 bg-ember/10 text-fg" : "border-line text-muted hover:border-line-strong hover:text-fg", className)}>
      {children}
    </button>
  );
}

export default function NewProject() {
  const [params] = useSearchParams();
  const nav = useNavigate();
  const toast = useToast();
  const qc = useQueryClient();
  const { data: opts } = useOptions();
  const [step, setStep] = useState(params.get("template") ? 1 : 0);
  const [template, setTemplate] = useState<Template | null>(null);
  const [company, setCompany] = useState<Company>(emptyCompany);
  const [cfg, setCfg] = useState<Config>({ format: "9:16", duration: 30, style: "moderno", video_type: "anuncio", music_mood: "upbeat", narration_enabled: true, voice_gender: "female", voice_speed: 1, subtitles_enabled: true, quality: "1080p" });
  const [projectId, setProjectId] = useState<string | null>(null);
  const [edits, setEdits] = useState<Record<string, Partial<Scene>>>({});
  const [photos, setPhotos] = useState<Asset[]>([]);
  const upload = useUpload();

  const tplId = params.get("template");
  const { data: tplFull } = useQuery({ queryKey: ["template", tplId], enabled: !!tplId, queryFn: () => api<Template>(`/templates/${tplId}`) });
  useEffect(() => { if (tplFull) pickTemplate(tplFull); }, [tplFull]); // eslint-disable-line react-hooks/exhaustive-deps

  const pickTemplate = (t: Template | null) => {
    setTemplate(t);
    if (t) {
      setCfg((c) => ({ ...c, style: t.style, video_type: t.video_type, music_mood: opts?.style_presets[t.style]?.music ?? c.music_mood }));
      setCompany((c) => ({ ...c, segment: c.segment || t.category_label }));
    }
  };

  const project = useProject(projectId ?? undefined, (p) => {
    if (p.jobs[0]?.status === "completed") toast("Roteiro pronto! Revise antes de renderizar.", "success");
    else if (p.jobs[0]?.status === "failed") toast(p.jobs[0].error ?? "Falha ao gerar roteiro", "error");
  });

  const create = useMutation({
    mutationFn: async () => {
      let id = projectId;
      const settings = { ...cfg, photo_asset_ids: photos.map((p) => p.id) };
      if (id) {
        await api(`/projects/${id}`, { method: "PATCH", body: { company, settings } });
      } else {
        const p = await api<Project>("/projects", { body: { template_id: template?.id ?? null, company, settings } });
        id = p.id;
        setProjectId(id);
      }
      await api(`/projects/${id}/script`, { method: "POST" });
      setEdits({});
      await qc.invalidateQueries({ queryKey: ["project", id] });
    },
    onError: (e) => toast((e as Error).message, "error"),
  });

  const saveEdits = async () => {
    const p = project.data!;
    await Promise.all(Object.entries(edits).map(([sid, patch]) => api(`/projects/${p.id}/scenes/${sid}`, { method: "PATCH", body: patch })));
    setEdits({});
  };
  const finish = useMutation({
    mutationFn: async (render: boolean) => {
      await saveEdits();
      if (render) await api(`/projects/${projectId}/render`, { method: "POST" });
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["projects"] }); nav(`/projetos/${projectId}/editor`); },
    onError: (e) => toast((e as Error).message, "error"),
  });

  const companyValid = company.name.trim().length > 0 && (company.description.trim() || company.product.trim());
  const set = (k: keyof Company) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setCompany({ ...company, [k]: e.target.value });
  const p = project.data;
  const job = p?.active_job;
  const sceneVal = <K extends keyof Scene>(s: Scene, k: K) => (edits[s.id]?.[k] ?? s[k]) as Scene[K];
  const edit = (s: Scene, patch: Partial<Scene>) => setEdits((e) => ({ ...e, [s.id]: { ...e[s.id], ...patch } }));

  if (!opts) return <PageLoader />;

  return (
    <div className="mx-auto max-w-5xl animate-fade-in">
      <PageHeader title="Novo vídeo" subtitle="Informe os dados do negócio e a IA prepara roteiro, cenas e narração." />
      <ol className="mb-8 grid grid-cols-4 gap-2">
        {STEPS.map((s, i) => (
          <li key={s.label}>
            <button disabled={i > step && !(i === 3 && projectId)} onClick={() => setStep(i)}
              className={clsx("flex w-full items-center gap-2 border-t-2 pt-3 text-left text-xs transition sm:text-sm", i <= step ? "border-ember text-fg" : "border-line text-subtle")}>
              <span className={clsx("flex size-6 shrink-0 items-center justify-center rounded-full text-[11px]", i < step ? "bg-ember text-black" : i === step ? "border border-ember text-ember" : "border border-line")}>
                {i < step ? <Check className="size-3.5" /> : i + 1}
              </span>
              <span className="hidden sm:inline">{s.label}</span>
            </button>
          </li>
        ))}
      </ol>

      {step === 0 && (
        <div>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm text-muted">Escolha um template por segmento ou comece do zero.</p>
            <Button variant="ghost" onClick={() => { pickTemplate(null); setStep(1); }}>Começar do zero <ArrowRight className="size-4" /></Button>
          </div>
          <TemplateGrid selected={template?.id} onPick={(t) => { pickTemplate(t); setStep(1); }} />
        </div>
      )}

      {step === 1 && (
        <Card className="p-5 sm:p-6">
          {template && (
            <div className="mb-5 flex items-center gap-3 rounded-lg bg-surface-2 p-2.5">
              <TemplateThumb t={template} className="!aspect-square w-12 !p-1 [&>span]:hidden" />
              <div className="text-sm"><p className="font-medium">{template.name}</p><p className="text-xs text-muted">{template.description}</p></div>
            </div>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Nome da empresa *"><Input value={company.name} onChange={set("name")} placeholder="Ex.: Pizzaria Bella Napoli" /></Field>
            <Field label="Segmento comercial"><Input value={company.segment} onChange={set("segment")} placeholder="Ex.: Pizzaria" /></Field>
            <Field label="Descrição do negócio" className="sm:col-span-2"><Textarea value={company.description} onChange={set("description")} placeholder="O que a empresa faz, há quanto tempo, onde atende..." /></Field>
            <Field label="Produto ou serviço a divulgar"><Input value={company.product} onChange={set("product")} /></Field>
            <Field label="Promoção ou oferta"><Input value={company.offer} onChange={set("offer")} placeholder="Ex.: 20% de desconto até sexta" /></Field>
            <Field label="Público-alvo"><Input value={company.audience} onChange={set("audience")} /></Field>
            <Field label="Diferenciais" hint="Separe por vírgulas"><Input value={company.differentials} onChange={set("differentials")} /></Field>
            <Field label="WhatsApp"><Input value={company.whatsapp} onChange={set("whatsapp")} placeholder="(11) 98765-4321" /></Field>
            <Field label="Telefone"><Input value={company.phone} onChange={set("phone")} /></Field>
            <Field label="Instagram"><Input value={company.instagram} onChange={set("instagram")} placeholder="@suaempresa" /></Field>
            <Field label="Endereço (opcional)"><Input value={company.address} onChange={set("address")} /></Field>
          </div>
          <div className="mt-5 rounded-lg border border-dashed border-line-strong p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-sm font-medium">Fotos da empresa e dos produtos <span className="font-normal text-muted">(recomendado)</span></p>
                <p className="text-xs text-muted">Fotos reais deixam o vídeo muito mais profissional. Serão usadas nas cenas de produto e oferta primeiro.</p>
              </div>
              <label className="inline-flex h-9 cursor-pointer items-center gap-2 rounded-lg border border-line bg-surface-3 px-4 text-sm hover:border-line-strong">
                {upload.isPending ? <RefreshCw className="size-4 animate-spin" /> : <ImagePlus className="size-4" />} Adicionar fotos
                <input type="file" hidden multiple accept="image/jpeg,image/png,image/webp" onChange={async (e) => {
                  const files = Array.from(e.target.files ?? []).slice(0, 12 - photos.length);
                  e.target.value = "";
                  for (const f of files) {
                    try { const a = await upload.mutateAsync({ file: f, kind: "image" }); setPhotos((p) => [...p, a]); } catch { /* toast exibido */ }
                  }
                }} />
              </label>
            </div>
            {photos.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {photos.map((p) => (
                  <div key={p.id} className="group relative size-20 overflow-hidden rounded-lg">
                    <img src={p.url} alt={p.name} className="size-full object-cover" />
                    <button aria-label="Remover foto" onClick={() => setPhotos((x) => x.filter((y) => y.id !== p.id))} className="absolute right-1 top-1 rounded bg-black/70 p-0.5"><X className="size-3" /></button>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="mt-6 flex justify-between">
            <Button variant="ghost" icon={<ArrowLeft className="size-4" />} onClick={() => setStep(0)}>Voltar</Button>
            <Button variant="primary" disabled={!companyValid} onClick={() => setStep(2)}>Continuar <ArrowRight className="size-4" /></Button>
          </div>
        </Card>
      )}

      {step === 2 && (
        <Card className="flex flex-col gap-6 p-5 sm:p-6">
          <div>
            <p className="mb-2 text-xs font-medium text-muted">Formato</p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {[["9:16", "Reels · TikTok · Shorts"], ["1:1", "Feed quadrado"], ["4:5", "Feed retrato"], ["16:9", "YouTube · Anúncios"]].map(([f, d]) => (
                <Choice key={f} active={cfg.format === f} onClick={() => setCfg({ ...cfg, format: f })} className="flex items-center gap-3 text-left">
                  <span className={clsx("shrink-0 rounded-sm border-2 border-current", f === "9:16" ? "h-6 w-3.5" : f === "16:9" ? "h-3.5 w-6" : f === "4:5" ? "h-6 w-5" : "size-5")} />
                  <span><span className="block font-medium">{f}</span><span className="text-[11px] text-subtle">{d}</span></span>
                </Choice>
              ))}
            </div>
          </div>
          <div>
            <p className="mb-2 text-xs font-medium text-muted">Duração</p>
            <div className="grid grid-cols-4 gap-2">{opts.durations.map((d) => <Choice key={d} active={cfg.duration === d} onClick={() => setCfg({ ...cfg, duration: d })}>{d}s</Choice>)}</div>
          </div>
          <div>
            <p className="mb-2 text-xs font-medium text-muted">Estilo</p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {Object.entries(opts.styles).map(([k, v]) => {
                const pal = opts.style_presets[k].palette;
                return (
                  <Choice key={k} active={cfg.style === k} onClick={() => setCfg({ ...cfg, style: k, music_mood: opts.style_presets[k].music })} className="flex items-center gap-3 text-left">
                    <span className="flex -space-x-1">{pal.slice(0, 3).map((c) => <span key={c} className="size-4 rounded-full border border-black/40" style={{ background: c }} />)}</span>
                    <span style={{ fontFamily: opts.style_presets[k].font }}>{v}</span>
                  </Choice>
                );
              })}
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Tipo de vídeo"><Select value={cfg.video_type} onChange={(e) => setCfg({ ...cfg, video_type: e.target.value })} options={recordOptions(opts.video_types)} /></Field>
            <Field label="Música de fundo"><Select value={cfg.music_mood} onChange={(e) => setCfg({ ...cfg, music_mood: e.target.value })} options={[...recordOptions(opts.music_moods), { value: "none", label: "Sem música" }]} /></Field>
            <Field label="Qualidade"><Select value={cfg.quality} onChange={(e) => setCfg({ ...cfg, quality: e.target.value })} options={[{ value: "1080p", label: "1080p (recomendado)" }, { value: "720p", label: "720p (mais rápido)" }]} /></Field>
          </div>
          <div className="grid gap-4 rounded-lg border border-line p-4 sm:grid-cols-3">
            <Toggle checked={cfg.narration_enabled} onChange={(v) => setCfg({ ...cfg, narration_enabled: v })} label="Narração com IA" />
            <Field label="Voz"><Select disabled={!cfg.narration_enabled} value={cfg.voice_gender} onChange={(e) => setCfg({ ...cfg, voice_gender: e.target.value as "female" | "male" })} options={[{ value: "female", label: "Feminina" }, { value: "male", label: "Masculina" }]} /></Field>
            <Field label={`Velocidade: ${cfg.voice_speed.toFixed(2)}x`}><input type="range" min={0.8} max={1.3} step={0.05} disabled={!cfg.narration_enabled} value={cfg.voice_speed} onChange={(e) => setCfg({ ...cfg, voice_speed: Number(e.target.value) })} className="accent-[var(--color-ember)]" /></Field>
            <Toggle checked={cfg.subtitles_enabled} onChange={(v) => setCfg({ ...cfg, subtitles_enabled: v })} label="Legendas automáticas" />
          </div>
          <div className="flex justify-between">
            <Button variant="ghost" icon={<ArrowLeft className="size-4" />} onClick={() => setStep(1)}>Voltar</Button>
            <Button variant="primary" icon={<Sparkles className="size-4" />} loading={create.isPending} onClick={async () => { await create.mutateAsync(); setStep(3); }}>Gerar roteiro com IA</Button>
          </div>
        </Card>
      )}

      {step === 3 && (
        <div className="flex flex-col gap-4">
          {(!p || job) && (
            <Card className="flex flex-col items-center gap-4 p-10 text-center">
              <div className="relative flex size-14 items-center justify-center rounded-2xl bg-ember/10"><Wand2 className="size-6 animate-pulse text-ember" /></div>
              <div>
                <p className="font-medium">A IA está escrevendo seu roteiro</p>
                <p className="mt-1 text-sm text-muted">Analisando o negócio, criando gancho, cenas, textos e chamada para ação.</p>
              </div>
              {job && <div className="w-full max-w-sm"><JobRow job={job} compact /></div>}
            </Card>
          )}
          {p && !job && p.scenes.length > 0 && (
            <>
              <Card className="p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-wide text-muted">Roteiro · {p.script.engine?.startsWith("ollama") ? `IA (${p.script.engine.replace("ollama:", "")})` : "modo template"}</p>
                    <h2 className="mt-1 text-lg font-semibold">{p.script.title}</h2>
                    {p.script.analysis && <p className="mt-1 max-w-2xl text-sm text-muted">{p.script.analysis}</p>}
                  </div>
                  <Button icon={<RefreshCw className="size-4" />} loading={create.isPending} onClick={() => create.mutate()}>Gerar outro roteiro</Button>
                </div>
                {p.script.caption && <p className="mt-3 rounded-lg bg-surface-2 p-3 text-xs text-muted"><span className="font-medium text-fg">Legenda do post: </span>{p.script.caption} {p.script.hashtags?.join(" ")}</p>}
              </Card>
              {p.scenes.map((s, i) => (
                <Card key={s.id} className="grid gap-4 p-4 sm:grid-cols-[120px_1fr]">
                  <div className="flex flex-row items-center gap-2 sm:flex-col sm:items-start">
                    <span className="flex size-7 items-center justify-center rounded-full bg-surface-3 text-xs font-semibold">{i + 1}</span>
                    <span className="text-xs text-ember">{label(s.role)}</span>
                    <Field label="Duração (s)" className="w-24"><Input type="number" min={1} max={30} step={0.5} value={sceneVal(s, "duration")} onChange={(e) => edit(s, { duration: Number(e.target.value) })} /></Field>
                  </div>
                  <div className="grid gap-3 md:grid-cols-2">
                    <Field label="Texto na tela"><Input value={sceneVal(s, "title")} onChange={(e) => edit(s, { title: e.target.value })} /></Field>
                    <Field label="Subtítulo"><Input value={sceneVal(s, "subtitle")} onChange={(e) => edit(s, { subtitle: e.target.value })} /></Field>
                    <Field label="Narração" className="md:col-span-2"><Textarea rows={2} value={sceneVal(s, "narration")} onChange={(e) => edit(s, { narration: e.target.value })} /></Field>
                    <Field label="Sugestão de imagem (prompt para IA)" className="md:col-span-2"><Input value={sceneVal(s, "image_prompt")} onChange={(e) => edit(s, { image_prompt: e.target.value })} /></Field>
                  </div>
                </Card>
              ))}
              <div className="flex flex-col-reverse justify-between gap-2 sm:flex-row">
                <Button variant="ghost" icon={<ArrowLeft className="size-4" />} onClick={() => setStep(2)}>Ajustar configuração</Button>
                <div className="flex flex-col gap-2 sm:flex-row">
                  <Button icon={<Clapperboard className="size-4" />} loading={finish.isPending && finish.variables === false} onClick={() => finish.mutate(false)}>Abrir no editor</Button>
                  <Button variant="primary" icon={<Sparkles className="size-4" />} loading={finish.isPending && finish.variables === true} onClick={() => finish.mutate(true)}>Aprovar e gerar vídeo</Button>
                </div>
              </div>
            </>
          )}
          {p && !job && p.scenes.length === 0 && (
            <Card className="p-6 text-center">
              <p className="text-sm text-muted">{p.jobs[0]?.error ?? "Não foi possível gerar o roteiro."}</p>
              <Button className="mt-4" variant="primary" onClick={() => create.mutate()}>Tentar novamente</Button>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
