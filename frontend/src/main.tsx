import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { ToastProvider } from "./components/toast";
import "./index.css";
import { AuthProvider } from "./lib/auth";

const qc = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 5000 } } });

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <ToastProvider>
          <AuthProvider>
            <App />
          </AuthProvider>
        </ToastProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
