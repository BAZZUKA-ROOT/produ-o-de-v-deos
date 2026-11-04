import { closestCenter, DndContext, PointerSensor, useSensor, useSensors, type DragEndEvent } from "@dnd-kit/core";
import { horizontalListSortingStrategy, SortableContext, useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import clsx from "clsx";
import { AudioLines, GripVertical, Plus, Subtitles } from "lucide-react";
import { useRef } from "react";
import type { Project, Scene, Timeline } from "@/lib/types";

const PX = 34; // pixels por segundo

function Block({ sc, width, selected, onSelect, onResize, index }: { sc: Scene; width: number; selected: boolean; onSelect: () => void; onResize: (d: number) => void; index: number }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: sc.id });
  const startX = useRef(0);
  const startDur = useRef(sc.duration);
  const onPointerDown = (e: React.PointerEvent) => {
    e.stopPropagation();
    startX.current = e.clientX;
    startDur.current = sc.duration;
    const move = (ev: PointerEvent) => onResize(Math.max(1, Math.min(30, Math.round((startDur.current + (ev.clientX - startX.current) / PX) * 2) / 2)));
    const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };
  return (
    <div ref={setNodeRef} style={{ transform: CSS.Translate.toString(transform), transition, width, zIndex: isDragging ? 10 : undefined }}
      className={clsx("group relative h-16 shrink-0 overflow-hidden rounded-lg border-2 bg-surface-3 transition-[border-color]", selected ? "border-ember" : "border-transparent hover:border-line-strong", isDragging && "opacity-80 shadow-2xl")}
      onClick={onSelect}>
      {sc.image && <img src={sc.image.url} alt="" className="absolute inset-0 size-full object-cover opacity-60" draggable={false} />}
      <div className="absolute inset-0 bg-gradient-to-t from-black/80 to-transparent" />
      <button {...attributes} {...listeners} aria-label="Arrastar cena" className="absolute left-1 top-1 cursor-grab rounded bg-black/50 p-0.5 text-white/80 active:cursor-grabbing"><GripVertical className="size-3" /></button>
      <span className="absolute right-3 top-1 text-[10px] font-semibold text-white/80">{sc.duration.toFixed(1)}s</span>
      <p className="absolute inset-x-1.5 bottom-1 truncate text-[11px] font-medium text-white">{index + 1}. {sc.title || "Sem título"}</p>
      <div onPointerDown={onPointerDown} title="Arraste para alterar a duração" className="absolute inset-y-0 right-0 w-2 cursor-ew-resize bg-ember/0 transition group-hover:bg-ember/60" />
    </div>
  );
}

export function TimelineBar({ project, timeline, selectedId, onSelect, onReorder, onResize, onAdd, time, onSeek }: {
  project: Project; timeline: Timeline | undefined; selectedId: string | null; onSelect: (id: string) => void;
  onReorder: (ids: string[]) => void; onResize: (id: string, d: number) => void; onAdd: () => void; time: number; onSeek: (t: number) => void;
}) {
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }));
  const ids = project.scenes.map((s) => s.id);
  const tlById = new Map(timeline?.scenes.map((t) => [t.id, t]));
  const onDragEnd = (e: DragEndEvent) => {
    if (!e.over || e.active.id === e.over.id) return;
    const from = ids.indexOf(String(e.active.id));
    const to = ids.indexOf(String(e.over.id));
    const next = [...ids];
    next.splice(to, 0, next.splice(from, 1)[0]);
    onReorder(next);
  };
  const total = timeline?.total ?? 0;
  const endW = (timeline?.end_card_duration ?? 0) * PX;
  return (
    <div className="border-t border-line bg-surface">
      <div className="overflow-x-auto px-4 py-3">
        <div className="relative" style={{ minWidth: Math.max(total * PX + 160, 400) }}>
          <div className="mb-1 flex h-5 cursor-pointer items-end gap-0 text-[10px] text-subtle" onClick={(e) => { const r = e.currentTarget.getBoundingClientRect(); onSeek(Math.max(0, (e.clientX - r.left) / PX)); }}>
            {Array.from({ length: Math.ceil(total) + 1 }, (_, i) => (
              <span key={i} className="shrink-0 border-l border-line pl-0.5" style={{ width: PX }}>{i % 5 === 0 ? `${i}s` : ""}</span>
            ))}
          </div>
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
            <SortableContext items={ids} strategy={horizontalListSortingStrategy}>
              <div className="flex items-center gap-1">
                {project.scenes.map((sc, i) => {
                  const ts = tlById.get(sc.id);
                  const eff = ts ? ts.duration - (i < project.scenes.length - 1 || endW ? ts.trans_out : 0) : sc.duration;
                  return <Block key={sc.id} sc={sc} index={i} width={Math.max(eff * PX - 4, 44)} selected={selectedId === sc.id} onSelect={() => onSelect(sc.id)} onResize={(d) => onResize(sc.id, d)} />;
                })}
                {endW > 0 && (
                  <div className="flex h-16 shrink-0 items-center justify-center rounded-lg border border-dashed border-line-strong text-[11px] text-muted" style={{ width: endW - 4 }}>Tela final</div>
                )}
                <button onClick={onAdd} aria-label="Adicionar cena" className="flex h-16 w-12 shrink-0 items-center justify-center rounded-lg border border-dashed border-line text-muted hover:border-ember hover:text-ember"><Plus className="size-4" /></button>
              </div>
            </SortableContext>
          </DndContext>
          <div className="relative mt-1.5 h-5">
            <Subtitles className="absolute -left-0 top-0.5 size-3.5 text-subtle" />
            {timeline?.scenes.flatMap((ts) => ts.captions).map((c, i) => (
              <div key={i} title={c.text} className="absolute top-0 h-5 truncate rounded bg-info/15 px-1 text-[9px] leading-5 text-info" style={{ left: c.start * PX, width: Math.max((c.end - c.start) * PX - 2, 4) }}>{c.text}</div>
            ))}
          </div>
          <div className="relative mt-1 h-4">
            <AudioLines className="absolute top-0 size-3.5 text-subtle" />
            {timeline?.scenes.filter((t) => t.narr_start != null).map((t) => (
              <div key={t.id} className="absolute top-0.5 h-3 rounded bg-ok/25" style={{ left: t.narr_start! * PX, width: (t.narr_duration ?? 0) * PX }} />
            ))}
          </div>
          <div className="pointer-events-none absolute -top-1 bottom-0 w-0.5 bg-ember" style={{ left: time * PX }}>
            <div className="absolute -left-1 -top-0.5 size-2.5 rounded-full bg-ember" />
          </div>
        </div>
      </div>
    </div>
  );
}
