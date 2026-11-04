export const fmtBytes = (b: number | null | undefined) => {
  if (!b) return "0 B";
  const u = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.min(Math.floor(Math.log(b) / Math.log(1024)), u.length - 1);
  return `${(b / 1024 ** i).toFixed(i ? 1 : 0)} ${u[i]}`;
};
export const fmtSec = (s: number | null | undefined) => {
  if (s == null) return "—";
  const m = Math.floor(s / 60);
  const r = Math.floor(s % 60);
  return `${m}:${String(r).padStart(2, "0")}`;
};
export const fmtDate = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleString("pt-BR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "—";
export const timeAgo = (iso: string) => {
  const d = (Date.now() - new Date(iso).getTime()) / 1000;
  if (d < 60) return "agora";
  if (d < 3600) return `há ${Math.floor(d / 60)} min`;
  if (d < 86400) return `há ${Math.floor(d / 3600)} h`;
  return `há ${Math.floor(d / 86400)} d`;
};

export const STATUS_LABEL: Record<string, string> = {
  draft: "Rascunho", scripting: "Gerando roteiro", ready: "Pronto p/ render", processing: "Processando",
  completed: "Finalizado", failed: "Falhou", cancelled: "Cancelado", queued: "Na fila", running: "Executando",
  cancelling: "Cancelando",
};
export const JOB_LABEL: Record<string, string> = {
  script: "Roteiro", images: "Imagens", narration: "Narração", preview: "Prévia", render: "Renderização", model_pull: "Download de modelo",
};
export const LABELS: Record<string, string> = {
  none: "Nenhum(a)", fade: "Esmaecer", fadeblack: "Fade preto", fadewhite: "Fade branco", dissolve: "Dissolver",
  slideleft: "Deslizar ←", slideright: "Deslizar →", slideup: "Deslizar ↑", slidedown: "Deslizar ↓",
  wipeleft: "Cortina ←", wiperight: "Cortina →", smoothleft: "Suave ←", smoothright: "Suave →",
  circleopen: "Círculo abre", circleclose: "Círculo fecha", radial: "Radial", zoomin: "Zoom", pixelize: "Pixelizar",
  hblur: "Desfoque", diagtl: "Diagonal", squeezeh: "Comprimir",
  zoom_in: "Aproximar", zoom_out: "Afastar", pan_left: "Panorâmica ←", pan_right: "Panorâmica →", pan_up: "Panorâmica ↑",
  pan_down: "Panorâmica ↓", zoom_in_left: "Zoom + ←", zoom_in_right: "Zoom + →",
  slide_up: "Subir", slide_left: "Entrar pela direita", pop: "Pop", typewriter: "Máquina de escrever", blur_in: "Foco",
  top: "Topo", center: "Centro", bottom: "Base", cover: "Preencher", contain_blur: "Inteira c/ fundo desfocado",
  clean: "Limpa", boxed: "Caixa", highlight: "Destaque por palavra", bold_outline: "Contorno forte",
  hook: "Gancho", problem: "Problema", product: "Produto", benefit: "Benefício", differential: "Diferencial", offer: "Oferta",
  social_proof: "Prova social", content: "Conteúdo", cta: "Chamada (CTA)",
  female: "Feminina", male: "Masculina", kokoro: "Kokoro (natural)", piper: "Piper", espeak: "eSpeak (leve)",
};
export const label = (k: string) => LABELS[k] ?? k;
