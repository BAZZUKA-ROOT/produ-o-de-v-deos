import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FlaskConical } from "lucide-react";
import { useState } from "react";
import { JobRow } from "@/components/shared";
import { useToast } from "@/components/toast";
import { Badge, Button, Card, Field, Input, Modal, PageHeader, PageLoader } from "@/components/ui";
import { api } from "@/lib/api";
import type { Job } from "@/lib/types";
import { SettingsCard, type AllSettings } from "./settingsForm";

type Svc = { ollama?: { online: boolean; models: string[]; model_ready: boolean; error?: string }; comfyui?: { online: boolean; checkpoints: string[]; devices?: string[]; error?: string }; tts?: { providers: Record<string, boolean> } };

export default function AdminAI() {
  const qc = useQueryClient();
  const toast = useToast();
  const [model, setModel] = useState("qwen2.5:7b-instruct");
  const [pullJob, setPullJob] = useState<string | null>(null);
  const [test, setTest] = useState<null | { seconds: number; engine: string; notes: string[]; script: { title: string; scenes: { title: string; narration: string }[] } }>(null);
  const { data } = useQuery({ queryKey: ["admin", "settings"], queryFn: () => api<AllSettings>("/admin/settings") });
  const { data: svc } = useQuery({ queryKey: ["admin", "services"], queryFn: () => api<Svc>("/admin/services"), refetchInterval: 15000 });
  const { data: job } = useQuery({ queryKey: ["admin", "job", pullJob], enabled: !!pullJob, queryFn: () => api<Job>(`/admin/jobs/${pullJob}`), refetchInterval: (q) => (q.state.data && !["queued", "running"].includes(q.state.data.status) ? false : 1500) });
  const pull = useMutation({ mutationFn: () => api<Job>("/admin/ai/pull", { body: { model } }), onSuccess: (j) => setPullJob(j.id), onError: (e) => toast((e as Error).message, "error") });
  const runTest = useMutation({ mutationFn: () => api<NonNullable<typeof test>>("/admin/ai/test-llm", { method: "POST" }), onSuccess: setTest, onError: (e) => toast((e as Error).message, "error") });
  if (!data) return <PageLoader />;
  const ai = data.values.ai;
  const tts = svc?.tts?.providers ?? {};
  return (
    <div className="flex max-w-4xl flex-col gap-4 animate-fade-in">
      <PageHeader title="Modelos de IA" subtitle="Todos os modelos rodam localmente. Configure provedores, modelos e fallbacks." />
      <SettingsCard title="Roteiros (LLM via Ollama)" section="ai" values={ai}
        description="Sem Ollama disponível, a plataforma usa automaticamente o gerador por templates (sem IA)."
        fields={[
          { key: "llm_provider", label: "Provedor", type: "select", options: [{ value: "ollama", label: "Ollama (LLM local)" }, { value: "template", label: "Somente templates (sem LLM)" }] },
          { key: "ollama_url", label: "URL do Ollama" },
          { key: "ollama_model", label: "Modelo", hint: "Recomendados: qwen2.5:7b-instruct (Apache-2.0) · leve: qwen2.5:1.5b-instruct" },
          { key: "llm_temperature", label: "Temperatura", type: "number", step: 0.1 },
          { key: "llm_timeout_seconds", label: "Tempo limite (s)", type: "number" },
        ]}>
        <div className="mt-5 rounded-lg border border-line p-4">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className={svc?.ollama?.online ? "text-ok" : "text-err"}>● {svc?.ollama?.online ? "Ollama online" : `Ollama offline${svc?.ollama?.error ? ` (${svc.ollama.error.slice(0, 60)})` : ""}`}</span>
            {svc?.ollama?.models.map((m) => <Badge key={m} className={m === ai.ollama_model ? "!text-ember" : ""}>{m}</Badge>)}
          </div>
          <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-end">
            <Field label="Baixar modelo no Ollama" className="flex-1"><Input value={model} onChange={(e) => setModel(e.target.value)} /></Field>
            <Button icon={<Download className="size-4" />} loading={pull.isPending} onClick={() => pull.mutate()}>Baixar</Button>
            <Button icon={<FlaskConical className="size-4" />} loading={runTest.isPending} onClick={() => runTest.mutate()}>Testar geração</Button>
          </div>
          {job && <div className="mt-3"><JobRow job={job} /></div>}
          {job?.status === "completed" && <Button size="sm" variant="ghost" className="mt-2" onClick={() => { setPullJob(null); qc.invalidateQueries({ queryKey: ["admin", "services"] }); }}>Atualizar lista</Button>}
        </div>
      </SettingsCard>
      <SettingsCard title="Imagens das cenas" section="ai" values={ai}
        description="Ordem automática: ComfyUI (IA local, ideal com GPU) → Pexels (fotos reais gratuitas, chave grátis em pexels.com/api) → fundo procedural. Fotos enviadas pelo usuário sempre têm prioridade."
        fields={[
          { key: "image_provider", label: "Provedor", type: "select", options: [{ value: "auto", label: "Automático (ComfyUI → Pexels → procedural)" }, { value: "comfyui", label: "ComfyUI (SDXL / SD 1.5)" }, { value: "pexels", label: "Pexels (fotos reais grátis)" }, { value: "procedural", label: "Somente fundos procedurais" }] },
          { key: "pexels_api_key", label: "Chave da API Pexels (gratuita)", hint: "Fotos com licença livre para uso comercial" },
          { key: "comfyui_url", label: "URL do ComfyUI" },
          { key: "comfyui_checkpoint", label: "Checkpoint", hint: svc?.comfyui?.checkpoints.length ? `Disponíveis: ${svc.comfyui.checkpoints.join(", ")}` : "Ex.: sd_xl_base_1.0.safetensors" },
          { key: "comfyui_base_resolution", label: "Resolução base", type: "number", hint: "1024 para SDXL · 512 para SD 1.5" },
          { key: "comfyui_steps", label: "Passos", type: "number", hint: "25–30 SDXL · 4–8 com LCM-LoRA" },
          { key: "comfyui_cfg", label: "CFG", type: "number", step: 0.5, hint: "6–7 SDXL · 1–2 com LCM" },
          { key: "comfyui_sampler", label: "Sampler", hint: "dpmpp_2m · lcm" },
          { key: "comfyui_scheduler", label: "Scheduler", hint: "karras · sgm_uniform" },
          { key: "comfyui_lora", label: "LoRA (opcional)", hint: "Ex.: lcm-lora-sdv1-5.safetensors" },
          { key: "comfyui_lora_strength", label: "Força da LoRA", type: "number", step: 0.1 },
          { key: "comfyui_timeout_seconds", label: "Tempo limite (s)", type: "number" },
          { key: "negative_prompt", label: "Prompt negativo" },
        ]}>
        <p className="mt-4 text-sm"><span className={svc?.comfyui?.online ? "text-ok" : "text-muted"}>● {svc?.comfyui?.online ? `ComfyUI online (${svc.comfyui.devices?.join(", ")})` : "ComfyUI offline"}</span></p>
      </SettingsCard>
      <SettingsCard title="Voz (TTS)" section="ai" values={ai} description="Kokoro tem vozes pt-BR feminina e masculina. Piper (faber) é masculino. eSpeak NG é o fallback universal (robótico)."
        fields={[
          { key: "tts_provider", label: "Provedor padrão", type: "select", options: [{ value: "kokoro", label: "Kokoro-82M" }, { value: "piper", label: "Piper" }, { value: "espeak", label: "eSpeak NG" }] },
          { key: "kokoro_model_file", label: "Arquivo do modelo Kokoro" },
          { key: "kokoro_voices_file", label: "Arquivo de vozes Kokoro" },
          { key: "piper_voice_male", label: "Voz Piper masculina" },
        ]}>
        <p className="mt-4 flex gap-3 text-sm">{Object.entries(tts).map(([k, v]) => <span key={k} className={v ? "text-ok" : "text-err"}>● {k} {v ? "instalado" : "ausente"}</span>)}</p>
      </SettingsCard>
      <SettingsCard title="Renderização" section="render" values={data.values.render}
        fields={[
          { key: "default_quality", label: "Qualidade padrão", type: "select", options: ["720p", "1080p"].map((v) => ({ value: v, label: v })) },
          { key: "preview_quality", label: "Qualidade da prévia", type: "select", options: ["360p", "540p"].map((v) => ({ value: v, label: v })) },
          { key: "x264_preset", label: "Preset x264", type: "select", options: ["ultrafast", "veryfast", "faster", "fast", "medium", "slow"].map((v) => ({ value: v, label: v })), hint: "Mais lento = arquivo menor/melhor" },
          { key: "crf", label: "CRF (qualidade)", type: "number", hint: "18 alta · 20 padrão · 23 menor" },
          { key: "fps", label: "FPS", type: "number" },
          { key: "max_retries", label: "Retentativas automáticas", type: "number" },
        ]} />
      <SettingsCard title="Geral" section="general" values={data.values.general} fields={[{ key: "allow_registration", label: "Permitir cadastro público de novos usuários", type: "bool" }]} />
      <Card className="p-5 text-sm text-muted">
        Pastas do servidor: modelos em <code className="text-fg">{data.env.models_dir}</code>. Para baixar Kokoro/Piper execute <code className="text-fg">scripts/download-models.sh</code>.
      </Card>
      <Modal open={!!test} onClose={() => setTest(null)} title="Teste de geração de roteiro" wide>
        {test && <div className="flex flex-col gap-2 text-sm">
          <p className="text-muted">{test.engine} · {test.seconds}s {test.notes.join(" ")}</p>
          <p className="font-medium">{test.script.title}</p>
          {test.script.scenes.map((s, i) => <p key={i}><span className="text-ember">{s.title}</span> — {s.narration}</p>)}
        </div>}
      </Modal>
    </div>
  );
}
