import { FolderOpen, Music2, X } from "lucide-react";
import { useState } from "react";
import { optionList, recordOptions } from "@/components/shared";
import { Button, Field, Input, Select, Tabs, Textarea, Toggle } from "@/components/ui";
import { fmtSec, label } from "@/lib/format";
import type { Asset, Company, Options, Project, ProjectSettings } from "@/lib/types";
import { MediaPicker } from "./MediaPicker";

type SettingsPatch = Partial<Omit<ProjectSettings, "watermark" | "end_card">> & { watermark?: Partial<ProjectSettings["watermark"]>; end_card?: Partial<ProjectSettings["end_card"]> };
type Tab = "video" | "audio" | "brand" | "company";

function AssetChip({ asset, empty, onPick, onClear }: { asset: Asset | null; empty: string; onPick: () => void; onClear?: () => void }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-line bg-surface-2 p-2">
      {asset?.kind === "image" || asset?.kind === "logo" ? <img src={asset.url} alt="" className="size-9 rounded object-contain" /> : <Music2 className="size-4 text-muted" />}
      <div className="min-w-0 flex-1">
        <p className="truncate text-xs">{asset?.name ?? empty}</p>
        {asset?.duration != null && <p className="text-[10px] text-muted">{fmtSec(asset.duration)}</p>}
      </div>
      <Button size="sm" variant="ghost" icon={<FolderOpen className="size-3.5" />} onClick={onPick}>Escolher</Button>
      {asset && onClear && <button aria-label="Remover" className="text-muted hover:text-err" onClick={onClear}><X className="size-3.5" /></button>}
    </div>
  );
}

export function ProjectPanel({ project, opts, onSettings, onCompany, onName }: {
  project: Project; opts: Options; onSettings: (p: SettingsPatch) => void; onCompany: (c: Company) => void; onName: (n: string) => void;
}) {
  const s = project.settings;
  const [tab, setTab] = useState<Tab>("video");
  const [picker, setPicker] = useState<null | "music" | "logo" | "audio">(null);
  const c = project.company;
  const setC = (k: keyof Company) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => onCompany({ ...c, [k]: e.target.value });
  const providers = Object.keys(opts.voices);

  return (
    <div className="flex flex-col gap-4">
      <Tabs value={tab} onChange={setTab} tabs={[{ value: "video", label: "Vídeo" }, { value: "audio", label: "Áudio" }, { value: "brand", label: "Marca" }, { value: "company", label: "Empresa" }]} />
      {tab === "video" && (
        <div className="flex flex-col gap-3">
          <Field label="Nome do projeto"><Input value={project.name} onChange={(e) => onName(e.target.value)} /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Formato"><Select value={s.format} onChange={(e) => onSettings({ format: e.target.value })} options={opts.formats.map((f) => ({ value: f, label: f }))} /></Field>
            <Field label="Duração alvo"><Select value={String(s.duration)} onChange={(e) => onSettings({ duration: Number(e.target.value) })} options={opts.durations.map((d) => ({ value: String(d), label: `${d}s` }))} /></Field>
            <Field label="Estilo"><Select value={s.style} onChange={(e) => onSettings({ style: e.target.value })} options={recordOptions(opts.styles)} /></Field>
            <Field label="Tipo"><Select value={s.video_type} onChange={(e) => onSettings({ video_type: e.target.value })} options={recordOptions(opts.video_types)} /></Field>
            <Field label="Fonte dos títulos"><Select value={s.font} onChange={(e) => onSettings({ font: e.target.value })} options={opts.fonts.map((f) => ({ value: f, label: f }))} /></Field>
            <Field label="Qualidade final"><Select value={s.quality} onChange={(e) => onSettings({ quality: e.target.value })} options={opts.qualities.map((q) => ({ value: q, label: q }))} /></Field>
          </div>
          <Field label="Paleta (fundo, secundária, destaque, texto)">
            <div className="flex gap-2">
              {s.palette.map((col, i) => (
                <label key={i} className="relative size-9 cursor-pointer overflow-hidden rounded-lg border border-line" style={{ background: col }}>
                  <input type="color" value={col} aria-label={`Cor ${i + 1}`} className="absolute inset-0 cursor-pointer opacity-0"
                    onChange={(e) => { const p = [...s.palette]; p[i] = e.target.value.toUpperCase(); onSettings({ palette: p }); }} />
                </label>
              ))}
            </div>
          </Field>
          <Toggle checked={s.fit_duration} onChange={(v) => onSettings({ fit_duration: v })} label="Ajustar automaticamente à duração alvo" />
          <Toggle checked={s.stage_effects ?? true} onChange={(v) => onSettings({ stage_effects: v })} label="Palco animado (feixes de luz, grade e partículas)" />
          <Toggle checked={s.sfx_enabled ?? true} onChange={(v) => onSettings({ sfx_enabled: v })} label="Efeitos sonoros (whoosh, impactos)" />
          <div className="rounded-lg border border-line p-3">
            <Toggle checked={s.subtitles_enabled} onChange={(v) => onSettings({ subtitles_enabled: v })} label="Legendas automáticas" />
            {s.subtitles_enabled && <Field label="Estilo das legendas" className="mt-3"><Select value={s.subtitle_style} onChange={(e) => onSettings({ subtitle_style: e.target.value })} options={optionList(opts.subtitle_styles)} /></Field>}
          </div>
        </div>
      )}
      {tab === "audio" && (
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <p className="text-xs font-medium text-muted">Trilha sonora</p>
            <Select value={s.music_asset_id ? "__custom" : s.music_mood} onChange={(e) => e.target.value !== "__custom" && onSettings({ music_mood: e.target.value, music_asset_id: null })}
              options={[...recordOptions(opts.music_moods).map((o) => ({ ...o, label: `Trilha do sistema · ${o.label}` })), { value: "none", label: "Sem música" }, ...(s.music_asset_id ? [{ value: "__custom", label: "Música da biblioteca" }] : [])]} />
            <AssetChip asset={s.music_asset_id ? project.music : null} empty="Usar música própria..." onPick={() => setPicker("music")} onClear={() => onSettings({ music_asset_id: null })} />
            {project.music && <audio src={project.music.url} controls className="h-8 w-full" />}
            <Field label={`Volume da música: ${Math.round(s.music_volume * 100)}%`}><input type="range" min={0} max={1} step={0.05} value={s.music_volume} onChange={(e) => onSettings({ music_volume: Number(e.target.value) })} className="accent-[var(--color-ember)]" /></Field>
          </div>
          <div className="flex flex-col gap-3 rounded-lg border border-line p-3">
            <Toggle checked={s.narration_enabled} onChange={(v) => onSettings({ narration_enabled: v })} label="Narração" />
            {s.narration_enabled && <>
              <Tabs value={s.narration_mode} onChange={(v) => onSettings({ narration_mode: v })} tabs={[{ value: "tts", label: "Voz por IA" }, { value: "upload", label: "Áudio próprio" }]} />
              {s.narration_mode === "tts" ? (
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Voz"><Select value={s.voice_gender} onChange={(e) => onSettings({ voice_gender: e.target.value as "female" | "male" })} options={[{ value: "female", label: "Feminina" }, { value: "male", label: "Masculina" }]} /></Field>
                  <Field label="Motor"><Select value={s.tts_provider ?? ""} onChange={(e) => onSettings({ tts_provider: e.target.value || null })} options={[{ value: "", label: "Padrão do servidor" }, ...providers.map((p) => ({ value: p, label: label(p) }))]} /></Field>
                  <Field label={`Velocidade: ${s.voice_speed.toFixed(2)}x`} className="col-span-2"><input type="range" min={0.7} max={1.4} step={0.05} value={s.voice_speed} onChange={(e) => onSettings({ voice_speed: Number(e.target.value) })} className="accent-[var(--color-ember)]" /></Field>
                  {s.tts_provider === "piper" && s.voice_gender === "female" && <p className="col-span-2 text-[11px] text-warn">Piper pt-BR só possui voz masculina; será usado o Kokoro.</p>}
                </div>
              ) : (
                <>
                  <AssetChip asset={project.narration_track} empty="Enviar narração gravada..." onPick={() => setPicker("audio")} onClear={() => onSettings({ narration_asset_id: null })} />
                  <p className="text-[11px] text-muted">O áudio começa junto com o vídeo. As legendas usam o texto de narração de cada cena, distribuído no tempo de cada cena.</p>
                </>
              )}
            </>}
          </div>
        </div>
      )}
      {tab === "brand" && (
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <p className="text-xs font-medium text-muted">Logotipo</p>
            <AssetChip asset={project.logo} empty="Nenhum logo" onPick={() => setPicker("logo")} onClear={() => onSettings({ logo_asset_id: null })} />
          </div>
          <div className="flex flex-col gap-3 rounded-lg border border-line p-3">
            <Toggle checked={s.watermark.enabled} onChange={(v) => onSettings({ watermark: { enabled: v } })} label="Marca d'água" />
            {s.watermark.enabled && <div className="grid grid-cols-2 gap-3">
              <Field label="Tipo"><Select value={s.watermark.type} onChange={(e) => onSettings({ watermark: { type: e.target.value as "text" | "image" } })} options={[{ value: "text", label: "Texto" }, { value: "image", label: "Logo" }]} /></Field>
              <Field label="Posição"><Select value={s.watermark.position} onChange={(e) => onSettings({ watermark: { position: e.target.value } })} options={[{ value: "top_right", label: "Superior direita" }, { value: "top_left", label: "Superior esquerda" }, { value: "bottom_right", label: "Inferior direita" }, { value: "bottom_left", label: "Inferior esquerda" }]} /></Field>
              {s.watermark.type === "text" && <Field label="Texto" className="col-span-2"><Input placeholder={c.name} value={s.watermark.text} onChange={(e) => onSettings({ watermark: { text: e.target.value } })} /></Field>}
              {s.watermark.type === "image" && !project.logo && <p className="col-span-2 text-[11px] text-warn">Escolha um logotipo acima.</p>}
              <Field label={`Opacidade: ${Math.round(s.watermark.opacity * 100)}%`} className="col-span-2"><input type="range" min={0.1} max={1} step={0.05} value={s.watermark.opacity} onChange={(e) => onSettings({ watermark: { opacity: Number(e.target.value) } })} className="accent-[var(--color-ember)]" /></Field>
            </div>}
          </div>
          <div className="flex flex-col gap-3 rounded-lg border border-line p-3">
            <Toggle checked={s.end_card.enabled} onChange={(v) => onSettings({ end_card: { enabled: v } })} label="Tela final com contato" />
            {s.end_card.enabled && <>
              <Field label="Chamada"><Input value={s.end_card.headline} onChange={(e) => onSettings({ end_card: { headline: e.target.value } })} /></Field>
              <Field label={`Duração: ${s.end_card.duration}s`}><input type="range" min={2} max={8} step={0.5} value={s.end_card.duration} onChange={(e) => onSettings({ end_card: { duration: Number(e.target.value) } })} className="accent-[var(--color-ember)]" /></Field>
              <div className="flex flex-col gap-2">
                <Toggle checked={s.end_card.show_phone} onChange={(v) => onSettings({ end_card: { show_phone: v } })} label="Mostrar WhatsApp/telefone" />
                <Toggle checked={s.end_card.show_instagram} onChange={(v) => onSettings({ end_card: { show_instagram: v } })} label="Mostrar Instagram" />
                <Toggle checked={s.end_card.show_address} onChange={(v) => onSettings({ end_card: { show_address: v } })} label="Mostrar endereço" />
              </div>
            </>}
          </div>
        </div>
      )}
      {tab === "company" && (
        <div className="flex flex-col gap-3">
          <Field label="Nome"><Input value={c.name} onChange={setC("name")} /></Field>
          <Field label="Segmento"><Input value={c.segment} onChange={setC("segment")} /></Field>
          <Field label="Descrição"><Textarea rows={3} value={c.description} onChange={setC("description")} /></Field>
          <Field label="Produto/serviço"><Input value={c.product} onChange={setC("product")} /></Field>
          <Field label="Oferta"><Input value={c.offer} onChange={setC("offer")} /></Field>
          <Field label="Público-alvo"><Input value={c.audience} onChange={setC("audience")} /></Field>
          <Field label="Diferenciais"><Input value={c.differentials} onChange={setC("differentials")} /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="WhatsApp"><Input value={c.whatsapp} onChange={setC("whatsapp")} /></Field>
            <Field label="Telefone"><Input value={c.phone} onChange={setC("phone")} /></Field>
          </div>
          <Field label="Instagram"><Input value={c.instagram} onChange={setC("instagram")} /></Field>
          <Field label="Endereço"><Input value={c.address} onChange={setC("address")} /></Field>
          <p className="text-[11px] text-muted">Alterações aqui valem para a tela final e para novos roteiros.</p>
        </div>
      )}
      <MediaPicker open={picker === "music"} onClose={() => setPicker(null)} kind="music" title="Escolher música" onPick={(a) => onSettings({ music_asset_id: a.id })} />
      <MediaPicker open={picker === "logo"} onClose={() => setPicker(null)} kind="logo" title="Escolher logotipo" onPick={(a) => onSettings({ logo_asset_id: a.id })} />
      <MediaPicker open={picker === "audio"} onClose={() => setPicker(null)} kind="audio" projectId={project.id} title="Narração própria" onPick={(a) => onSettings({ narration_asset_id: a.id })} />
    </div>
  );
}

export type { SettingsPatch };
