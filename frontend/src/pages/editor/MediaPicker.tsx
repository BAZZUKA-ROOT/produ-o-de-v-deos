import { useQuery } from "@tanstack/react-query";
import { Upload } from "lucide-react";
import { useRef } from "react";
import { useToast } from "@/components/toast";
import { Button, Empty, Modal, PageLoader } from "@/components/ui";
import { api } from "@/lib/api";
import type { Asset } from "@/lib/types";
import { AssetTile, useUpload } from "../Library";

export function MediaPicker({ open, onClose, kind, onPick, projectId, title }: {
  open: boolean; onClose: () => void; kind: "image" | "music" | "audio" | "logo"; onPick: (a: Asset) => void; projectId?: string; title: string;
}) {
  const toast = useToast();
  const fileRef = useRef<HTMLInputElement>(null);
  const upload = useUpload();
  const kinds = kind === "image" || kind === "logo" ? "image,logo" : kind;
  const { data, isLoading } = useQuery({ queryKey: ["assets", kinds, "picker"], enabled: open, queryFn: () => api<{ items: Asset[] }>(`/assets?kind=${kinds}&page_size=200`) });
  const accept = kind === "image" || kind === "logo" ? "image/jpeg,image/png,image/webp" : "audio/*";
  return (
    <Modal open={open} onClose={onClose} title={title} wide footer={<>
      <input ref={fileRef} type="file" hidden accept={accept} onChange={async (e) => {
        const f = e.target.files?.[0];
        e.target.value = "";
        if (!f) return;
        try {
          const a = await upload.mutateAsync({ file: f, kind, projectId: kind === "audio" ? projectId : undefined });
          toast("Arquivo enviado", "success");
          onPick(a);
          onClose();
        } catch { /* toast já exibido */ }
      }} />
      <Button variant="primary" icon={<Upload className="size-4" />} loading={upload.isPending} onClick={() => fileRef.current?.click()}>Enviar do computador</Button>
    </>}>
      {isLoading ? <PageLoader /> : !data?.items.length ? <Empty icon={<Upload className="size-5" />} title="Biblioteca vazia" text="Envie um arquivo para usar no projeto." /> : (
        <div className="grid grid-cols-3 gap-3 sm:grid-cols-4 md:grid-cols-5">
          {data.items.map((a) => <AssetTile key={a.id} a={a} onClick={() => { onPick(a); onClose(); }} />)}
        </div>
      )}
    </Modal>
  );
}
