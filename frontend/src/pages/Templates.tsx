import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { ArrowRight } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { TemplateThumb } from "@/components/shared";
import { Badge, PageHeader, PageLoader } from "@/components/ui";
import { api } from "@/lib/api";
import type { Template } from "@/lib/types";

interface TplResp { items: Template[]; categories: { slug: string; label: string; count: number }[] }

export function useTemplates() {
  return useQuery({ queryKey: ["templates"], queryFn: () => api<TplResp>("/templates"), staleTime: 60000 });
}

export function TemplateGrid({ onPick, selected }: { onPick: (t: Template) => void; selected?: string | null }) {
  const { data, isLoading } = useTemplates();
  const [cat, setCat] = useState("");
  if (isLoading || !data) return <PageLoader />;
  const items = data.items.filter((t) => !cat || t.category === cat);
  return (
    <div>
      <div className="mb-5 flex gap-2 overflow-x-auto pb-1">
        {[{ slug: "", label: "Todos", count: data.items.length }, ...data.categories].map((c) => (
          <button key={c.slug} onClick={() => setCat(c.slug)}
            className={clsx("shrink-0 rounded-full border px-3 py-1.5 text-xs transition", cat === c.slug ? "border-ember/50 bg-ember/10 text-ember" : "border-line text-muted hover:text-fg")}>
            {c.label} <span className="opacity-60">{c.count}</span>
          </button>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
        {items.map((t) => (
          <button key={t.id} onClick={() => onPick(t)} className={clsx("group card flex flex-col gap-2 p-2 text-left transition hover:border-line-strong", selected === t.id && "!border-ember ring-2 ring-ember/30")}>
            <TemplateThumb t={t} className="transition duration-300 group-hover:brightness-110" />
            <div className="px-1 pb-1">
              <p className="line-clamp-1 text-xs font-medium">{t.name.split("·").pop()?.trim()}</p>
              <p className="line-clamp-1 text-[11px] text-muted">{t.category_label}</p>
              <div className="mt-1.5 flex gap-1"><Badge>{t.style}</Badge><Badge>{t.scene_count} cenas</Badge></div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

export default function Templates() {
  const nav = useNavigate();
  return (
    <div className="animate-fade-in">
      <PageHeader title="Templates" subtitle="Modelos prontos por segmento. Escolha um e preencha os dados da empresa." actions={
        <span className="flex items-center gap-1 text-xs text-muted">Clique para usar <ArrowRight className="size-3" /></span>} />
      <TemplateGrid onPick={(t) => nav(`/novo?template=${t.id}`)} />
    </div>
  );
}
