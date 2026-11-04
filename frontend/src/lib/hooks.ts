import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { api } from "./api";
import type { Options, Project } from "./types";

export function useOptions() {
  return useQuery({ queryKey: ["options"], queryFn: () => api<Options>("/meta/options"), staleTime: Infinity });
}

/** Carrega o projeto e faz polling enquanto houver tarefa ativa; dispara onJobDone ao concluir. */
export function useProject(id: string | undefined, onJobDone?: (p: Project) => void) {
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ["project", id], enabled: !!id, queryFn: () => api<Project>(`/projects/${id}`),
    refetchInterval: (query) => (query.state.data?.active_job ? 1500 : false),
  });
  const prevActive = useRef<string | null>(null);
  const cb = useRef(onJobDone);
  cb.current = onJobDone;
  useEffect(() => {
    const active = q.data?.active_job?.id ?? null;
    if (prevActive.current && !active && q.data) {
      cb.current?.(q.data);
      qc.invalidateQueries({ queryKey: ["timeline", id] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["notifications"] });
    }
    prevActive.current = active;
  }, [q.data, id, qc]);
  return q;
}
