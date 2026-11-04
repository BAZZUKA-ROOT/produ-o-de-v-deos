import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Clapperboard, FolderOpen, Image as ImageIcon, LayoutTemplate, Loader, Plus, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { JobRow, ProjectCard } from "@/components/shared";
import { Button, Card, Empty, PageHeader, PageLoader } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Asset, Job, ProjectSummary } from "@/lib/types";

interface Dash {
  videos_produced: number; projects_total: number; projects_in_progress: number; projects_completed: number;
  projects_failed: number; templates_available: number; library_items: number; recent_projects: ProjectSummary[];
  active_jobs: Job[]; recent_videos: Asset[];
}

function Stat({ icon, label, value, to }: { icon: React.ReactNode; label: string; value: number; to: string }) {
  return (
    <Link to={to} className="card flex items-center gap-4 p-4 transition hover:border-line-strong">
      <div className="flex size-10 items-center justify-center rounded-lg bg-surface-3 text-ember">{icon}</div>
      <div>
        <p className="text-2xl font-semibold tabular-nums">{value}</p>
        <p className="text-xs text-muted">{label}</p>
      </div>
    </Link>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard"], queryFn: () => api<Dash>("/dashboard"),
    refetchInterval: (q) => (q.state.data?.active_jobs.length ? 3000 : 20000),
  });
  if (isLoading || !data) return <PageLoader />;
  return (
    <div className="animate-fade-in">
      <PageHeader title={`Olá, ${user?.name.split(" ")[0]}`} subtitle="Acompanhe sua produção e crie novos vídeos comerciais."
        actions={<Link to="/novo"><Button variant="primary" icon={<Plus className="size-4" />}>Criar novo vídeo</Button></Link>} />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Stat icon={<Clapperboard className="size-5" />} label="Vídeos produzidos" value={data.videos_produced} to="/biblioteca" />
        <Stat icon={<Loader className="size-5" />} label="Projetos em andamento" value={data.projects_in_progress} to="/projetos" />
        <Stat icon={<CheckCircle2 className="size-5" />} label="Vídeos finalizados" value={data.projects_completed} to="/projetos?status=completed" />
        <Stat icon={<LayoutTemplate className="size-5" />} label="Templates disponíveis" value={data.templates_available} to="/templates" />
        <Stat icon={<ImageIcon className="size-5" />} label="Itens na biblioteca" value={data.library_items} to="/biblioteca" />
      </div>

      <div className="mt-8 grid gap-6 xl:grid-cols-[1fr_340px]">
        <section>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-medium">Projetos recentes</h2>
            <Link to="/projetos" className="text-sm text-muted hover:text-fg">Ver todos</Link>
          </div>
          {data.recent_projects.length ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {data.recent_projects.map((p) => <ProjectCard key={p.id} p={p} />)}
            </div>
          ) : (
            <Empty icon={<FolderOpen className="size-5" />} title="Nenhum projeto ainda" text="Informe os dados de uma empresa e a IA monta o roteiro, cenas e narração."
              action={<Link to="/novo"><Button variant="primary" icon={<Sparkles className="size-4" />}>Criar primeiro vídeo</Button></Link>} />
          )}
        </section>
        <aside className="flex flex-col gap-6">
          <Card className="p-4">
            <h2 className="mb-3 font-medium">Fila de processamento</h2>
            {data.active_jobs.length ? (
              <div className="flex flex-col gap-2">
                {data.active_jobs.map((j) => (
                  <Link key={j.id} to={j.project_id ? `/projetos/${j.project_id}/editor` : "#"}><JobRow job={j} /></Link>
                ))}
              </div>
            ) : <p className="text-sm text-muted">Nenhuma tarefa em execução.</p>}
          </Card>
          <Card className="p-4">
            <h2 className="mb-3 font-medium">Últimos vídeos</h2>
            {data.recent_videos.length ? (
              <div className="grid grid-cols-2 gap-2">
                {data.recent_videos.map((v) => (
                  <a key={v.id} href={v.download_url} className="group relative overflow-hidden rounded-lg bg-surface-2" title={v.name}>
                    <video src={v.url} preload="metadata" muted className="aspect-[9/16] w-full object-cover" />
                    <span className="absolute inset-x-0 bottom-0 truncate bg-gradient-to-t from-black/80 px-2 pb-1.5 pt-4 text-[11px]">{v.name}</span>
                  </a>
                ))}
              </div>
            ) : <p className="text-sm text-muted">Os vídeos renderizados aparecem aqui.</p>}
          </Card>
        </aside>
      </div>
    </div>
  );
}
