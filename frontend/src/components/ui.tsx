import clsx from "clsx";
import { Loader2, X } from "lucide-react";
import { useEffect, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
import { STATUS_LABEL } from "@/lib/format";

type Variant = "primary" | "secondary" | "ghost" | "danger";
const variants: Record<Variant, string> = {
  primary: "ember-gradient text-black font-semibold hover:brightness-110 shadow-lg shadow-ember/20",
  secondary: "bg-surface-3 text-fg border border-line hover:border-line-strong hover:bg-surface-2",
  ghost: "text-muted hover:text-fg hover:bg-surface-3",
  danger: "bg-err/10 text-err border border-err/30 hover:bg-err/20",
};

export function Button({ variant = "secondary", size = "md", loading, icon, className, children, disabled, ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: "sm" | "md" | "lg"; loading?: boolean; icon?: ReactNode }) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={clsx(
        "inline-flex items-center justify-center gap-2 rounded-lg transition-all duration-150 disabled:cursor-not-allowed disabled:opacity-50 whitespace-nowrap",
        size === "sm" ? "h-8 px-3 text-xs" : size === "lg" ? "h-11 px-5 text-sm" : "h-9 px-4 text-sm",
        variants[variant], className,
      )}
    >
      {loading ? <Loader2 className="size-4 animate-spin" /> : icon}
      {children}
    </button>
  );
}

export function IconButton({ label, className, children, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return (
    <button {...rest} aria-label={label} title={label}
      className={clsx("inline-flex size-8 items-center justify-center rounded-lg text-muted transition hover:bg-surface-3 hover:text-fg disabled:opacity-40", className)}>
      {children}
    </button>
  );
}

const fieldBase = "w-full rounded-lg border border-line bg-surface-2 px-3 text-sm text-fg placeholder:text-subtle transition focus:border-ember/60 focus:outline-none focus:ring-2 focus:ring-ember/20";

export function Field({ label, hint, error, children, className }: { label?: string; hint?: string; error?: string; children: ReactNode; className?: string }) {
  return (
    <label className={clsx("flex flex-col gap-1.5", className)}>
      {label && <span className="text-xs font-medium text-muted">{label}</span>}
      {children}
      {error ? <span className="text-xs text-err">{error}</span> : hint ? <span className="text-xs text-subtle">{hint}</span> : null}
    </label>
  );
}

export const Input = ({ className, ...p }: InputHTMLAttributes<HTMLInputElement>) => <input {...p} className={clsx(fieldBase, "h-9", className)} />;
export const Textarea = ({ className, ...p }: TextareaHTMLAttributes<HTMLTextAreaElement>) => <textarea {...p} className={clsx(fieldBase, "min-h-20 py-2 leading-relaxed", className)} />;
export function Select({ className, options, ...p }: SelectHTMLAttributes<HTMLSelectElement> & { options: { value: string; label: string }[] }) {
  return (
    <select {...p} className={clsx(fieldBase, "h-9 cursor-pointer appearance-none bg-[length:16px] bg-[right_8px_center] bg-no-repeat pr-8", className)}
      style={{ backgroundImage: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%238b93a7' stroke-width='2'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E\")" }}>
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
}

export function Toggle({ checked, onChange, label, disabled }: { checked: boolean; onChange: (v: boolean) => void; label?: string; disabled?: boolean }) {
  return (
    <button type="button" role="switch" aria-checked={checked} disabled={disabled} onClick={() => onChange(!checked)}
      className="flex items-center gap-2.5 text-sm disabled:opacity-50">
      <span className={clsx("relative h-5 w-9 rounded-full transition", checked ? "bg-ember" : "bg-surface-3 border border-line")}>
        <span className={clsx("absolute top-0.5 size-4 rounded-full bg-white shadow transition-all", checked ? "left-[18px]" : "left-0.5")} />
      </span>
      {label && <span className="text-fg/90">{label}</span>}
    </button>
  );
}

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={clsx("card", className)}>{children}</div>;
}

const statusColor: Record<string, string> = {
  completed: "bg-ok/10 text-ok border-ok/25", ready: "bg-info/10 text-info border-info/25",
  processing: "bg-ember/10 text-ember border-ember/30", running: "bg-ember/10 text-ember border-ember/30",
  scripting: "bg-ember/10 text-ember border-ember/30", queued: "bg-warn/10 text-warn border-warn/25",
  cancelling: "bg-warn/10 text-warn border-warn/25", failed: "bg-err/10 text-err border-err/25",
  cancelled: "bg-surface-3 text-muted border-line", draft: "bg-surface-3 text-muted border-line",
};
export function StatusBadge({ status }: { status: string }) {
  const live = ["processing", "running", "scripting", "queued", "cancelling"].includes(status);
  return (
    <span className={clsx("inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium", statusColor[status] ?? statusColor.draft)}>
      {live && <span className="size-1.5 animate-pulse rounded-full bg-current" />}
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}

export function Badge({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={clsx("inline-flex items-center rounded-md border border-line bg-surface-3 px-1.5 py-0.5 text-[11px] text-muted", className)}>{children}</span>;
}

export function Progress({ value, className }: { value: number; className?: string }) {
  return (
    <div className={clsx("h-1.5 w-full overflow-hidden rounded-full bg-surface-3", className)} role="progressbar" aria-valuenow={value} aria-valuemin={0} aria-valuemax={100}>
      <div className="ember-gradient h-full rounded-full transition-[width] duration-500" style={{ width: `${Math.max(2, Math.min(100, value))}%` }} />
    </div>
  );
}

export const Spinner = ({ className }: { className?: string }) => <Loader2 className={clsx("size-5 animate-spin text-muted", className)} />;

export function PageLoader() {
  return <div className="flex h-64 items-center justify-center"><Spinner className="size-6" /></div>;
}

export function Empty({ icon, title, text, action }: { icon: ReactNode; title: string; text?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-line px-6 py-14 text-center">
      <div className="flex size-12 items-center justify-center rounded-xl bg-surface-3 text-muted">{icon}</div>
      <div>
        <p className="font-medium">{title}</p>
        {text && <p className="mt-1 max-w-sm text-sm text-muted">{text}</p>}
      </div>
      {action}
    </div>
  );
}

export function Modal({ open, onClose, title, children, wide, footer }: { open: boolean; onClose: () => void; title: string; children: ReactNode; wide?: boolean; footer?: ReactNode }) {
  useEffect(() => {
    if (!open) return;
    const fn = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", fn);
    return () => window.removeEventListener("keydown", fn);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/70 p-0 backdrop-blur-sm animate-fade-in sm:items-center sm:p-4" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div role="dialog" aria-modal="true" aria-label={title}
        className={clsx("card flex max-h-[92vh] w-full flex-col bg-surface shadow-2xl animate-slide-up", wide ? "sm:max-w-4xl" : "sm:max-w-lg")}>
        <div className="flex items-center justify-between border-b border-line px-5 py-3.5">
          <h2 className="font-semibold">{title}</h2>
          <IconButton label="Fechar" onClick={onClose}><X className="size-4" /></IconButton>
        </div>
        <div className="overflow-y-auto p-5">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-line px-5 py-3">{footer}</div>}
      </div>
    </div>
  );
}

export function Tabs<T extends string>({ value, onChange, tabs, className }: { value: T; onChange: (v: T) => void; tabs: { value: T; label: string; icon?: ReactNode }[]; className?: string }) {
  return (
    <div className={clsx("flex gap-1 rounded-lg border border-line bg-surface-2 p-1", className)} role="tablist">
      {tabs.map((t) => (
        <button key={t.value} role="tab" aria-selected={value === t.value} onClick={() => onChange(t.value)}
          className={clsx("flex flex-1 items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition",
            value === t.value ? "bg-surface-3 text-fg shadow" : "text-muted hover:text-fg")}>
          {t.icon}{t.label}
        </button>
      ))}
    </div>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-xl font-semibold tracking-tight sm:text-2xl">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function ConfirmModal({ open, title, text, confirmLabel = "Confirmar", danger, loading, onConfirm, onClose }:
  { open: boolean; title: string; text: string; confirmLabel?: string; danger?: boolean; loading?: boolean; onConfirm: () => void; onClose: () => void }) {
  return (
    <Modal open={open} onClose={onClose} title={title}
      footer={<><Button variant="ghost" onClick={onClose}>Cancelar</Button><Button variant={danger ? "danger" : "primary"} loading={loading} onClick={onConfirm}>{confirmLabel}</Button></>}>
      <p className="text-sm text-muted">{text}</p>
    </Modal>
  );
}
