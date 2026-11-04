import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, RefreshCw, Trash2 } from "lucide-react";
import { useState } from "react";
import { TemplateThumb } from "@/components/shared";
import { useToast } from "@/components/toast";
import { Badge, Button, ConfirmModal, Field, IconButton, Input, Modal, PageHeader, PageLoader, Select, Textarea, Toggle } from "@/components/ui";
import { api } from "@/lib/api";
import { useOptions } from "@/lib/hooks";
import type { Template } from "@/lib/types";

interface Form { id?: string; slug: string; category: string; name: string; description: string; style: string; video_type: string; is_active: boolean; config: string }

const blank: Form = {
  slug: "", category: "empresas", name: "", description: "", style: "moderno", video_type: "anuncio", is_active: true,
  config: JSON.stringify({ category_label: "Empresas em geral", palette: ["#111827", "#7C3AED", "#F472B6", "#FFFFFF"], font: "Poppins", music_mood: "upbeat", image_style: "professional commercial photography", cta: "Fale com a gente pelo WhatsApp!", blueprint: [{ role: "hook", title: "Conheça a {empresa}", narration: "Conheça a {empresa}.", image: "modern office", share: 0.3 }, { role: "cta", title: "{cta}", narration: "{cta} {contato_frase}", image: "happy customer", share: 0.3 }] }, null, 2),
};

export default function AdminTemplates() {
  const qc = useQueryClient();
  const toast = useToast();
  const { data: opts } = useOptions();
  const [form, setForm] = useState<Form | null>(null);
  const [del, setDel] = useState<Template | null>(null);
  const { data } = useQuery({ queryKey: ["admin", "templates"], queryFn: () => api<Template[]>("/admin/templates") });
  const refresh = () => { qc.invalidateQueries({ queryKey: ["admin", "templates"] }); qc.invalidateQueries({ queryKey: ["templates"] }); };
  const save = useMutation({
    mutationFn: (f: Form) => {
      let config: unknown;
      try { config = JSON.parse(f.config); } catch { throw new Error("Configuração JSON inválida"); }
      const body = { slug: f.slug, category: f.category, name: f.name, description: f.description, style: f.style, video_type: f.video_type, is_active: f.is_active, config };
      return f.id ? api(`/admin/templates/${f.id}`, { method: "PUT", body }) : api("/admin/templates", { body });
    },
    onSuccess: () => { toast("Template salvo", "success"); setForm(null); refresh(); }, onError: (e) => toast((e as Error).message, "error"),
  });
  const toggle = useMutation({
    mutationFn: (t: Template) => api(`/admin/templates/${t.id}`, { method: "PUT", body: { slug: t.slug, category: t.category, name: t.name, description: t.description, style: t.style, video_type: t.video_type, is_active: !t.is_active, config: t.config } }),
    onSuccess: refresh,
  });
  const remove = useMutation({ mutationFn: (id: string) => api(`/admin/templates/${id}`, { method: "DELETE" }), onSuccess: () => { setDel(null); refresh(); } });
  const reseed = useMutation({ mutationFn: () => api<{ created: number }>("/admin/templates/reseed", { method: "POST" }), onSuccess: (r) => { toast(`${r.created} template(s) restaurado(s)`, "success"); refresh(); } });
  if (!data || !opts) return <PageLoader />;
  return (
    <div className="animate-fade-in">
      <PageHeader title="Templates" subtitle={`${data.length} templates`} actions={<>
        <Button icon={<RefreshCw className="size-4" />} loading={reseed.isPending} onClick={() => reseed.mutate()}>Restaurar padrões</Button>
        <Button variant="primary" icon={<Plus className="size-4" />} onClick={() => setForm(blank)}>Novo template</Button>
      </>} />
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {data.map((t) => (
          <div key={t.id} className="card flex gap-3 p-3">
            <TemplateThumb t={t} className="!w-16 shrink-0 !p-1.5 [&>span]:text-[8px]" />
            <div className="min-w-0 flex-1">
              <button className="line-clamp-1 text-left text-sm font-medium hover:text-ember" onClick={() => setForm({ id: t.id, slug: t.slug, category: t.category, name: t.name, description: t.description, style: t.style, video_type: t.video_type, is_active: t.is_active, config: JSON.stringify(t.config, null, 2) })}>{t.name}</button>
              <p className="line-clamp-1 text-xs text-muted">{t.slug}</p>
              <div className="mt-1.5 flex flex-wrap gap-1"><Badge>{t.style}</Badge><Badge>{t.video_type}</Badge><Badge>{t.scene_count} cenas</Badge></div>
              <div className="mt-2 flex items-center justify-between">
                <Toggle checked={t.is_active} onChange={() => toggle.mutate(t)} label={t.is_active ? "Ativo" : "Inativo"} />
                <IconButton label="Excluir" className="hover:!text-err" onClick={() => setDel(t)}><Trash2 className="size-4" /></IconButton>
              </div>
            </div>
          </div>
        ))}
      </div>
      <Modal open={!!form} onClose={() => setForm(null)} title={form?.id ? "Editar template" : "Novo template"} wide
        footer={<><Button variant="ghost" onClick={() => setForm(null)}>Cancelar</Button><Button variant="primary" loading={save.isPending} onClick={() => form && save.mutate(form)}>Salvar</Button></>}>
        {form && <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Nome"><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
          <Field label="Slug" hint="minúsculas, números, - e _"><Input value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value })} /></Field>
          <Field label="Categoria (slug)"><Input value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} /></Field>
          <Field label="Descrição"><Input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
          <Field label="Estilo"><Select value={form.style} onChange={(e) => setForm({ ...form, style: e.target.value })} options={Object.entries(opts.styles).map(([value, label]) => ({ value, label }))} /></Field>
          <Field label="Tipo"><Select value={form.video_type} onChange={(e) => setForm({ ...form, video_type: e.target.value })} options={Object.entries(opts.video_types).map(([value, label]) => ({ value, label }))} /></Field>
          <Field label="Configuração (JSON)" className="sm:col-span-2" hint="blueprint: cenas com role, title, narration, image, share. Placeholders: {empresa} {produto} {oferta} {oferta_frase} {diferencial_1} {diferenciais_frase} {descricao_curta} {cta} {contato_frase}">
            <Textarea rows={16} className="font-mono text-xs" value={form.config} onChange={(e) => setForm({ ...form, config: e.target.value })} />
          </Field>
          <Toggle checked={form.is_active} onChange={(v) => setForm({ ...form, is_active: v })} label="Ativo" />
        </div>}
      </Modal>
      <ConfirmModal open={!!del} danger title="Excluir template" text={`Excluir "${del?.name}"? Projetos existentes não são afetados.`} onConfirm={() => del && remove.mutate(del.id)} onClose={() => setDel(null)} />
    </div>
  );
}
