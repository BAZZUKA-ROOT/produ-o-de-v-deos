import { CheckCircle2, Info, XCircle } from "lucide-react";
import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

type Level = "success" | "error" | "info";
interface Toast { id: number; level: Level; text: string }
const Ctx = createContext<(text: string, level?: Level) => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((text: string, level: Level = "info") => {
    const id = Date.now() + Math.random();
    setItems((x) => [...x, { id, level, text }]);
    setTimeout(() => setItems((x) => x.filter((t) => t.id !== id)), level === "error" ? 7000 : 4000);
  }, []);
  return (
    <Ctx.Provider value={push}>
      {children}
      <div className="fixed bottom-4 right-4 z-[100] flex w-[min(380px,calc(100vw-2rem))] flex-col gap-2" role="status" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className="card flex items-start gap-3 bg-surface-2 p-3 text-sm shadow-2xl shadow-black/50 animate-slide-up">
            {t.level === "success" ? <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-ok" /> : t.level === "error" ? <XCircle className="mt-0.5 size-4 shrink-0 text-err" /> : <Info className="mt-0.5 size-4 shrink-0 text-info" />}
            <span className="leading-snug">{t.text}</span>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}
export const useToast = () => useContext(Ctx);
