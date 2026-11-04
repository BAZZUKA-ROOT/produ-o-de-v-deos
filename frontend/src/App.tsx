import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "./components/AppLayout";
import { PageLoader } from "./components/ui";
import { useAuth } from "./lib/auth";
import { LoginPage, RegisterPage } from "./pages/Auth";

const Dashboard = lazy(() => import("./pages/Dashboard"));
const Projects = lazy(() => import("./pages/Projects"));
const NewProject = lazy(() => import("./pages/NewProject"));
const Editor = lazy(() => import("./pages/editor/Editor"));
const Templates = lazy(() => import("./pages/Templates"));
const Library = lazy(() => import("./pages/Library"));
const Account = lazy(() => import("./pages/Account"));
const AdminOverview = lazy(() => import("./pages/admin/Overview"));
const AdminUsers = lazy(() => import("./pages/admin/Users"));
const AdminProjects = lazy(() => import("./pages/admin/Projects"));
const AdminJobs = lazy(() => import("./pages/admin/Jobs"));
const AdminLogs = lazy(() => import("./pages/admin/Logs"));
const AdminAI = lazy(() => import("./pages/admin/AISettings"));
const AdminStorage = lazy(() => import("./pages/admin/Storage"));
const AdminTemplates = lazy(() => import("./pages/admin/AdminTemplates"));

function Protected({ children, admin }: { children: ReactNode; admin?: boolean }) {
  const { user, loading } = useAuth();
  if (loading) return <PageLoader />;
  if (!user) return <Navigate to="/login" replace />;
  if (admin && user.role !== "admin") return <Navigate to="/" replace />;
  return <>{children}</>;
}

function Public({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <PageLoader />;
  return user ? <Navigate to="/" replace /> : <>{children}</>;
}

export default function App() {
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        <Route path="/login" element={<Public><LoginPage /></Public>} />
        <Route path="/cadastro" element={<Public><RegisterPage /></Public>} />
        <Route element={<Protected><AppLayout /></Protected>}>
          <Route index element={<Dashboard />} />
          <Route path="projetos" element={<Projects />} />
          <Route path="projetos/:id/editor" element={<Editor />} />
          <Route path="novo" element={<NewProject />} />
          <Route path="templates" element={<Templates />} />
          <Route path="biblioteca" element={<Library />} />
          <Route path="conta" element={<Account />} />
        </Route>
        <Route path="admin" element={<Protected admin><AppLayout admin /></Protected>}>
          <Route index element={<AdminOverview />} />
          <Route path="usuarios" element={<AdminUsers />} />
          <Route path="projetos" element={<AdminProjects />} />
          <Route path="tarefas" element={<AdminJobs />} />
          <Route path="logs" element={<AdminLogs />} />
          <Route path="ia" element={<AdminAI />} />
          <Route path="armazenamento" element={<AdminStorage />} />
          <Route path="templates" element={<AdminTemplates />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
