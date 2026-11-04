import { AlertTriangle, Copy, FolderOpen, ImageOff, Trash2, Wand2 } from "lucide-react";
import { useState } from "react";
import { optionList } from "@/components/shared";
import { Button, Field, Input, Select, Textarea } from "@/components/ui";
import { label } from "@/lib/format";
import type { Asset, Options, Scene } from "@/lib/types";
import { MediaPicker } from "./MediaPicker";

export function SceneInspector({ scene, index, opts, onChange, onDelete, onDuplicate, onGenerateImage, busy }: {
  scene: Scene; index: number; opts: Options; onChange: (patch: Partial<Scene> & { image_asset_id?: string | null; clear_image?: boolean }, image?: Asset | null) => void;
  onDelete: () => void; onDuplicate: () => void; onGenerateImage: () => void; busy: boolean;
}) {
  const [picker, setPicker] = useState(false);
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">Cena {index + 1} <span className="font-normal text-muted">· {label(scene.role)}</span></h3>
        <div className="flex gap-1">
          <Button size="sm" variant="ghost" icon={<Copy className="size-3.5" />} onClick={onDuplicate}>Duplicar</Button>
          <Button size="sm" variant="danger" icon={<Trash2 className="size-3.5" />} onClick={onDelete}>Remover</Button>
        </div>
      </div>

      <div className="overflow-hidden rounded-lg border border-line bg-surface-2">
        <div className="relative aspect-video bg-black/40">
          {scene.image ? <img src={scene.image.url} alt="" className="size-full object-cover" /> : (
            <div className="flex size-full flex-col items-center justify-center gap-1 text-xs text-muted"><ImageOff className="size-5" />Sem imagem — será gerada no render</div>
          )}
          {scene.image && <span className="absolute bottom-1.5 left-1.5 rounded bg-black/70 px-1.5 py-0.5 text-[10px]">{String(scene.image.meta?.engine ?? scene.image.source)}</span>}
        </div>
        <div className="grid grid-cols-3 gap-1 p-1.5">
          <Button size="sm" variant="ghost" icon={<Wand2 className="size-3.5" />} loading={busy} onClick={onGenerateImage}>Gerar IA</Button>
          <Button size="sm" variant="ghost" icon={<FolderOpen className="size-3.5" />} onClick={() => setPicker(true)}>Biblioteca</Button>
          <Button size="sm" variant="ghost" icon={<ImageOff className="size-3.5" />} disabled={!scene.image} onClick={() => onChange({ clear_image: true }, null)}>Remover</Button>
        </div>
      </div>
      <Field label="Layout da cena" hint={scene.layout === "auto" && scene.resolved_layout ? `Automático → ${label(scene.resolved_layout)}` : "Layouts de produto usam o recorte automático da foto"}>
        <Select value={scene.layout} onChange={(e) => onChange({ layout: e.target.value })} options={optionList(opts.layouts)} />
      </Field>
      <Field label="Prompt da imagem (inglês funciona melhor)"><Textarea rows={2} value={scene.image_prompt} onChange={(e) => onChange({ image_prompt: e.target.value })} /></Field>

      <Field label="Texto na tela" hint="Use *palavra* para destacar na cor de destaque">
        <Input value={scene.title} onChange={(e) => onChange({ title: e.target.value })} />
      </Field>
      <Field label="Subtítulo"><Input value={scene.subtitle} onChange={(e) => onChange({ subtitle: e.target.value })} /></Field>
      <Field label="Narração">
        <Textarea rows={3} value={scene.narration} onChange={(e) => onChange({ narration: e.target.value })} />
      </Field>
      {scene.narration_stale && <p className="-mt-2 flex items-center gap-1.5 text-[11px] text-warn"><AlertTriangle className="size-3" />Áudio desatualizado — será regerado ao renderizar ou em “Gerar narração”.</p>}
      <Field label="Destaques do produto (um por linha)" hint="Aparecem no layout “Produto + destaques”">
        <Textarea rows={3} value={scene.bullets} onChange={(e) => onChange({ bullets: e.target.value })} />
      </Field>
      <Field label="Legenda personalizada" hint="Vazio = usa o texto da narração"><Textarea rows={2} value={scene.caption_override} onChange={(e) => onChange({ caption_override: e.target.value })} /></Field>

      <div className="grid grid-cols-2 gap-3">
        <Field label={`Duração: ${scene.duration.toFixed(1)}s`}><input type="range" min={1} max={20} step={0.5} value={scene.duration} onChange={(e) => onChange({ duration: Number(e.target.value) })} className="accent-[var(--color-ember)]" /></Field>
        <Field label="Posição do texto"><Select value={scene.text_position} onChange={(e) => onChange({ text_position: e.target.value })} options={optionList(opts.text_positions)} /></Field>
        <Field label="Transição (saída)"><Select value={scene.transition} onChange={(e) => onChange({ transition: e.target.value })} options={optionList(opts.transitions)} /></Field>
        <Field label="Movimento"><Select value={scene.motion} onChange={(e) => onChange({ motion: e.target.value })} options={optionList(opts.motions)} /></Field>
        <Field label="Animação do texto"><Select value={scene.text_animation} onChange={(e) => onChange({ text_animation: e.target.value })} options={optionList(opts.text_animations)} /></Field>
        <Field label="Enquadramento"><Select value={scene.fit} onChange={(e) => onChange({ fit: e.target.value })} options={optionList(opts.fits)} /></Field>
        <Field label="Papel da cena" className="col-span-2"><Select value={scene.role} onChange={(e) => onChange({ role: e.target.value })} options={optionList(["hook", "problem", "product", "benefit", "differential", "offer", "social_proof", "content", "cta"])} /></Field>
      </div>
      <MediaPicker open={picker} onClose={() => setPicker(false)} kind="image" title="Escolher imagem" onPick={(a) => onChange({ image_asset_id: a.id }, a)} />
    </div>
  );
}
