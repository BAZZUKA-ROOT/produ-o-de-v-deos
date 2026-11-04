import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useToast } from "@/components/toast";
import { Button, Card, Field, Input, Select, Toggle } from "@/components/ui";
import { api } from "@/lib/api";

export type Values = Record<string, string | number | boolean>;
export interface FieldDef { key: string; label: string; type?: "text" | "number" | "bool" | "select"; options?: { value: string; label: string }[]; hint?: string; step?: number }
export interface AllSettings { values: Record<string, Values>; defaults: Record<string, Values>; env: Record<string, string> }

export function SettingsCard({ title, description, section, fields, values, children }: { title: string; description?: string; section: string; fields: FieldDef[]; values: Values; children?: React.ReactNode }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [form, setForm] = useState<Values>(values);
  useEffect(() => setForm(values), [values]);
  const save = useMutation({
    mutationFn: () => api(`/admin/settings/${section}`, { method: "PUT", body: { values: Object.fromEntries(fields.map((f) => [f.key, form[f.key]])) } }),
    onSuccess: () => { toast("Configurações salvas", "success"); qc.invalidateQueries({ queryKey: ["admin"] }); },
    onError: (e) => toast((e as Error).message, "error"),
  });
  const dirty = fields.some((f) => form[f.key] !== values[f.key]);
  return (
    <Card className="p-5">
      <div className="mb-4">
        <h2 className="font-medium">{title}</h2>
        {description && <p className="mt-1 text-sm text-muted">{description}</p>}
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {fields.map((f) => f.type === "bool" ? (
          <div key={f.key} className="flex items-center sm:col-span-2"><Toggle checked={!!form[f.key]} onChange={(v) => setForm({ ...form, [f.key]: v })} label={f.label} /></div>
        ) : (
          <Field key={f.key} label={f.label} hint={f.hint}>
            {f.type === "select" ? <Select value={String(form[f.key])} onChange={(e) => setForm({ ...form, [f.key]: e.target.value })} options={f.options ?? []} />
              : <Input type={f.type === "number" ? "number" : "text"} step={f.step} value={String(form[f.key] ?? "")} onChange={(e) => setForm({ ...form, [f.key]: f.type === "number" ? Number(e.target.value) : e.target.value })} />}
          </Field>
        ))}
      </div>
      {children}
      <div className="mt-5 flex justify-end"><Button variant="primary" disabled={!dirty} loading={save.isPending} onClick={() => save.mutate()}>Salvar</Button></div>
    </Card>
  );
}
