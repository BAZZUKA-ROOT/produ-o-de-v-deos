import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import {
  Activity, Bell, Boxes, ChevronLeft, Cpu, FileVideo, FolderOpen, Gauge, HardDrive, Image as ImageIcon, LayoutDashboard,
  LayoutTemplate, LogOut, Menu, Plus, ScrollText, Settings, Shield, Sparkles, Users, X,
} from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { timeAgo } from "@/lib/format";
import type { Notification } from "@/lib/types";
import { useToast } from "./toast";

export const APP_NAME = import.meta.env.VITE_APP_NAME ?? "Forja Studio";

export function Logo({ compact }: { compact?: boolean }) {
  return (
    <Link to="/" className="flex items-center gap-2.5">
      <img src="/favicon.svg" alt="" className="size-8" />
      {!compact && <span className="text-[15px] font-semibold tracking-tight">{APP_NAME}</span>}
    </Link>
  );
}

interface NavItem { to: string; label: string; icon: ReactNode; end?: boolean }
const userNav: NavItem[] = [
  { to: "/", label: "Painel", icon: <LayoutDashboard className="size-4" />, end: true },
  { to: "/projetos", label: "Projetos", icon: <FolderOpen className="size-4" /> },
  { to: "/templates", label: "Templates", icon: <LayoutTemplate className="size-4" /> },
  { to: "/biblioteca", label: "Biblioteca", icon: <ImageIcon className="size-4" /> },
  { to: "/conta", label: "Minha conta", icon: <Settings className="size-4" /> },
];
const adminNav: NavItem[] = [
  { to: "/admin", label: "Visão geral", icon: <Gauge className="size-4" />, end: true },
  { to: "/admin/usuarios", label: "Usuários", icon: <Users className="size-4" /> },
  { to: "/admin/projetos", label: "Projetos", icon: <FileVideo className="size-4" /> },
  { to: "/admin/tarefas", label: "Tarefas e renders", icon: <Activity className="size-4" /> },
  { to: "/admin/logs", label: "Logs de erros", icon: <ScrollText className="size-4" /> },
  { to: "/admin/ia", label: "Modelos de IA", icon: <Cpu className="size-4" /> },
  { to: "/admin/armazenamento", label: "Armazenamento", icon: <HardDrive className="size-4" /> },
  { to: "/admin/templates", label: "Templates", icon: <Boxes className="size-4" /> },
];

function NavList({ items, onNavigate }: { items: NavItem[]; onNavigate?: () => void }) {
  return (
    <nav className="flex flex-col gap-0.5">
      {items.map((i) => (
        <NavLink key={i.to} to={i.to} end={i.end} onClick={onNavigate}
          className={({ isActive }) => clsx("flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition",
            isActive ? "bg-surface-3 text-fg" : "text-muted hover:bg-surface-2 hover:text-fg")}>
          {i.icon}{i.label}
        </NavLink>
      ))}
    </nav>
  );
}

function Notifications() {
  const qc = useQueryClient();
  const toast = useToast();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const seen = useRef<Set<string> | null>(null);
  const ref = useRef<HTMLDivElement>(null);
  const { data } = useQuery({ queryKey: ["notifications"], queryFn: () => api<{ items: Notification[]; unread: number }>("/notifications"), refetchInterval: 10000 });
  const readAll = useMutation({ mutationFn: () => api("/notifications/read-all", { method: "POST" }), onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }) });

  useEffect(() => {
    if (!data) return;
    if (seen.current === null) {
      seen.current = new Set(data.items.map((n) => n.id));
      return;
    }
    for (const n of data.items) {
      if (!seen.current.has(n.id)) {
        seen.current.add(n.id);
        if (!n.read) toast(`${n.title}${n.message ? ` — ${n.message}` : ""}`, n.level === "error" ? "error" : n.level === "success" ? "success" : "info");
        qc.invalidateQueries({ queryKey: ["dashboard"] });
      }
    }
  }, [data, toast, qc]);

  useEffect(() => {
    const fn = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", fn);
    return () => document.removeEventListener("mousedown", fn);
  }, []);

  return (
    <div className="relative" ref={ref}>
      <button aria-label="Notificações" onClick={() => setOpen(!open)} className="relative flex size-9 items-center justify-center rounded-lg text-muted hover:bg-surface-3 hover:text-fg">
        <Bell className="size-4" />
        {!!data?.unread && <span className="absolute right-1.5 top-1.5 flex size-4 items-center justify-center rounded-full bg-ember text-[10px] font-bold text-black">{Math.min(data.unread, 9)}</span>}
      </button>
      {open && (
        <div className="card absolute right-0 top-11 z-40 w-[min(360px,calc(100vw-2rem))] bg-surface-2 shadow-2xl animate-slide-up">
          <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
            <span className="text-sm font-medium">Notificações</span>
            <button className="text-xs text-muted hover:text-fg" onClick={() => readAll.mutate()}>Marcar todas como lidas</button>
          </div>
          <div className="max-h-96 overflow-y-auto">
            {!data?.items.length && <p className="px-4 py-8 text-center text-sm text-muted">Nenhuma notificação</p>}
            {data?.items.map((n) => (
              <button key={n.id} onClick={() => { setOpen(false); void api(`/notifications/${n.id}/read`, { method: "POST" }).then(() => qc.invalidateQueries({ queryKey: ["notifications"] })); if (n.link) nav(n.link); }}
                className={clsx("flex w-full gap-3 border-b border-line/60 px-4 py-3 text-left hover:bg-surface-3", !n.read && "bg-ember/[0.04]")}>
                <span className={clsx("mt-1.5 size-2 shrink-0 rounded-full", n.level === "error" ? "bg-err" : n.level === "success" ? "bg-ok" : "bg-info", n.read && "opacity-30")} />
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-medium">{n.title}</span>
                  {n.message && <span className="line-clamp-2 block text-xs text-muted">{n.message}</span>}
                  <span className="mt-1 block text-[11px] text-subtle">{timeAgo(n.created_at)}</span>
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function AppLayout({ admin = false }: { admin?: boolean }) {
  const { user, logout } = useAuth();
  const [drawer, setDrawer] = useState(false);
  const loc = useLocation();
  const isEditor = /\/projetos\/[^/]+\/editor/.test(loc.pathname);
  useEffect(() => setDrawer(false), [loc.pathname]);

  const sidebar = (
    <div className="flex h-full flex-col gap-6 p-4">
      <div className="flex items-center justify-between px-1"><Logo />{admin && <span className="rounded-md bg-ember/15 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-ember">Admin</span>}</div>
      {!admin && (
        <Link to="/novo" className="ember-gradient flex h-10 items-center justify-center gap-2 rounded-lg text-sm font-semibold text-black shadow-lg shadow-ember/20 transition hover:brightness-110">
          <Plus className="size-4" /> Novo vídeo
        </Link>
      )}
      <NavList items={admin ? adminNav : userNav} />
      <div className="mt-auto flex flex-col gap-2">
        {user?.role === "admin" && (
          <NavLink to={admin ? "/" : "/admin"} className="flex items-center gap-3 rounded-lg border border-line px-3 py-2 text-sm text-muted hover:border-line-strong hover:text-fg">
            {admin ? <><ChevronLeft className="size-4" /> Voltar ao estúdio</> : <><Shield className="size-4" /> Painel administrativo</>}
          </NavLink>
        )}
        <div className="flex items-center gap-3 rounded-lg bg-surface-2 p-2.5">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-surface-3 text-xs font-semibold uppercase">{user?.name.slice(0, 2)}</div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">{user?.name}</p>
            <p className="truncate text-[11px] text-muted">{user?.email}</p>
          </div>
          <button aria-label="Sair" title="Sair" onClick={logout} className="text-muted hover:text-err"><LogOut className="size-4" /></button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex h-full">
      <aside className={clsx("hidden w-60 shrink-0 border-r border-line bg-surface lg:block", isEditor && "lg:hidden")}>{sidebar}</aside>
      {drawer && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-black/70 animate-fade-in" onClick={() => setDrawer(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 border-r border-line bg-surface animate-slide-up">
            <button aria-label="Fechar menu" className="absolute right-3 top-4 text-muted" onClick={() => setDrawer(false)}><X className="size-5" /></button>
            {sidebar}
          </aside>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        {!isEditor && (
          <header className="flex h-14 shrink-0 items-center gap-3 border-b border-line bg-bg/80 px-4 backdrop-blur lg:px-8">
            <button aria-label="Abrir menu" className="text-muted lg:hidden" onClick={() => setDrawer(true)}><Menu className="size-5" /></button>
            <div className="lg:hidden"><Logo compact /></div>
            <div className="flex-1" />
            {!admin && <Link to="/novo" className="hidden items-center gap-1.5 text-sm text-muted hover:text-fg sm:flex lg:hidden"><Sparkles className="size-4" /> Novo vídeo</Link>}
            <Notifications />
          </header>
        )}
        <main className={clsx("min-h-0 flex-1 overflow-y-auto", !isEditor && "px-4 py-6 lg:px-8 lg:py-8")}>
          <div className={clsx(!isEditor && "mx-auto max-w-7xl")}><Outlet /></div>
        </main>
      </div>
    </div>
  );
}
