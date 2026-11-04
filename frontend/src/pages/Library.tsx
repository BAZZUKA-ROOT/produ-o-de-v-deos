import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { Download, FileAudio, Image as ImageIcon, Music, Pencil, Search, Trash2, Upload, Video } from "lucide-react";
import { useRef, useState } from "react";
import { useToast } from "@/components/toast";
import { Badge, Button, ConfirmModal, Empty, IconButton, Input, PageHeader, PageLoader, Progress, Select, Tabs } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtBytes, fmtDate, fmtSec } from "@/lib/format";
import type { Asset } from "@/lib/types";

type Kind = "image" | "video" | "music" | "audio";
interface Lib { items: Asset[]; total: number; usage_bytes: number; quota_bytes: number }

export function useUpload() {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: ({ file, kind, projectId }: { file: File; kind: string; projectId?: string }) => {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("kind", kind);
      if (projectId) fd.append("project_id", projectId);
      return api<Asset>("/assets", { body: fd });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["assets"] }),
    onError: (e) => toast((e as Error).message, "error"),
  });
}

export function AssetTile({ a, onClick, selected, actions }: { a: Asset; onClick?: () => void; selected?: boolean; actions?: React.ReactNode }) {
  return (
    <div className={clsx("card group relative overflow-hidden", selected && "!border-ember ring-2 ring-ember/30")}>
      <button type="button" onClick={onClick} className="block w-full text-left" disabled={!onClick}>
        <div className="flex aspect-square items-center justify-center overflow-hidden bg-surface-2">
          {a.kind === "image" || a.kind === "logo" ? <img src={a.url} alt={a.name} loading="lazy" className="size-full object-cover" />
            : a.kind === "video" ? <video src={a.url} preload="metadata" muted className="size-full object-cover" />
            : <div className="flex flex-col items-center gap-2 text-muted">{a.kind === "music" ? <Music className="size-7" /> : <FileAudio className="size-7" />}<span className="text-xs">{fmtSec(a.duration)}</span></div>}
        </div>
        <div className="p-2">
          <p className="truncate text-xs font-medium" title={a.name}>{a.name}</p>
          <div className="mt-1 flex items-center gap-1">
            <Badge>{a.is_system ? "sistema" : a.source === "upload" ? "enviado" : a.source === "ai" ? "IA" : a.source === "render" ? "render" : "gerado"}</Badge>
            {a.width && <span className="text-[10px] text-subtle">{a.width}×{a.height}</span>}
          </div>
        </div>
      </button>
      {actions && <div className="absolute right-1.5 top-1.5 flex gap-0.5 rounded-lg bg-black/70 opacity-100 backdrop-blur transition sm:opacity-0 sm:group-hover:opacity-100">{actions}</div>}
    </div>
  );
}

export default function Library() {
  const qc = useQueryClient();
  const toast = useToast();
  const [kind, setKind] = useState<Kind>("image");
  const [q, setQ] = useState("");
  const [del, setDel] = useState<Asset | null>(null);
  const [playing, setPlaying] = useState<Asset | null>(null);
  const [uploadKind, setUploadKind] = useState("image");
  const fileRef = useRef<HTMLInputElement>(null);
  const upload = useUpload();
  const kinds = kind === "image" ? "image,logo" : kind;
  const { data, isLoading } = useQuery({
    queryKey: ["assets", kinds, q], placeholderData: keepPreviousData,
    queryFn: () => api<Lib>(`/assets?kind=${kinds}&page_size=200${q ? `&q=${encodeURIComponent(q)}` : ""}`),
  });
  const remove = useMutation({
    mutationFn: (id: string) => api(`/assets/${id}`, { method: "DELETE" }),
    onSuccess: () => { toast("Arquivo excluído", "success"); setDel(null); qc.invalidateQueries({ queryKey: ["assets"] }); },
    onError: (e) => { toast((e as Error).message, "error"); setDel(null); },
  });
  const rename = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) => api(`/assets/${id}`, { method: "PATCH", body: { name } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["assets"] }),
  });
  const accept = uploadKind === "image" || uploadKind === "logo" ? "image/jpeg,image/png,image/webp" : "audio/*";

  return (
    <div className="animate-fade-in">
      <PageHeader title="Biblioteca" subtitle="Imagens, logos, trilhas e vídeos reutilizáveis em todos os projetos." actions={<>
        <Select className="w-40" value={uploadKind} onChange={(e) => setUploadKind(e.target.value)}
          options={[{ value: "image", label: "Imagem" }, { value: "logo", label: "Logo" }, { value: "music", label: "Música" }, { value: "audio", label: "Áudio/narração" }]} />
        <input ref={fileRef} type="file" hidden multiple accept={accept} onChange={async (e) => {
          const files = Array.from(e.target.files ?? []);
          e.target.value = "";
          for (const f of files) await upload.mutateAsync({ file: f, kind: uploadKind }).then(() => toast(`${f.name} enviado`, "success")).catch(() => {});
        }} />
        <Button variant="primary" icon={<Upload className="size-4" />} loading={upload.isPending} onClick={() => fileRef.current?.click()}>Enviar arquivos</Button>
      </>} />
      {data && (
        <div className="mb-5 max-w-sm">
          <div className="mb-1 flex justify-between text-xs text-muted"><span>Armazenamento usado</span><span>{fmtBytes(data.usage_bytes)} de {fmtBytes(data.quota_bytes)}</span></div>
          <Progress value={(data.usage_bytes / Math.max(data.quota_bytes, 1)) * 100} />
        </div>
      )}
      <div className="mb-5 flex flex-col gap-2 sm:flex-row">
        <Tabs className="sm:w-[420px]" value={kind} onChange={setKind} tabs={[
          { value: "image", label: "Imagens", icon: <ImageIcon className="size-3.5" /> }, { value: "video", label: "Vídeos", icon: <Video className="size-3.5" /> },
          { value: "music", label: "Músicas", icon: <Music className="size-3.5" /> }, { value: "audio", label: "Áudios", icon: <FileAudio className="size-3.5" /> }]} />
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-subtle" />
          <Input className="pl-9" placeholder="Buscar..." value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
      </div>
      {isLoading ? <PageLoader /> : !data?.items.length ? (
        <Empty icon={<ImageIcon className="size-5" />} title="Nada por aqui" text="Envie arquivos ou gere conteúdo nos projetos." />
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-6">
          {data.items.map((a) => (
            <AssetTile key={a.id} a={a} onClick={a.kind === "video" || a.kind === "music" || a.kind === "audio" ? () => setPlaying(a) : undefined} actions={<>
              <a href={a.download_url} aria-label="Baixar" title="Baixar" className="inline-flex size-8 items-center justify-center text-muted hover:text-fg"><Download className="size-3.5" /></a>
              {!a.is_system && <>
                <IconButton label="Renomear" onClick={() => { const n = prompt("Novo nome", a.name); if (n?.trim()) rename.mutate({ id: a.id, name: n.trim() }); }}><Pencil className="size-3.5" /></IconButton>
                <IconButton label="Excluir" className="hover:!text-err" onClick={() => setDel(a)}><Trash2 className="size-3.5" /></IconButton>
              </>}
            </>} />
          ))}
        </div>
      )}
      {playing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 animate-fade-in" onClick={() => setPlaying(null)}>
          <div className="card w-full max-w-md p-4" onClick={(e) => e.stopPropagation()}>
            <p className="mb-3 truncate text-sm font-medium">{playing.name} <span className="text-muted">· {fmtDate(playing.created_at)}</span></p>
            {playing.kind === "video" ? <video src={playing.url} controls autoPlay className="max-h-[70vh] w-full rounded-lg bg-black" /> : <audio src={playing.url} controls autoPlay className="w-full" />}
          </div>
        </div>
      )}
      <ConfirmModal open={!!del} danger title="Excluir arquivo" confirmLabel="Excluir" text={`Excluir "${del?.name}"? Esta ação não pode ser desfeita.`}
        loading={remove.isPending} onConfirm={() => del && remove.mutate(del.id)} onClose={() => setDel(null)} />
    </div>
  );
}
