import * as React from "react";
import { useCallback, useState } from "react";
import { Moon, Sun } from "lucide-react";

import { Sidebar, type SidebarItem } from "@/components/shared/layout/sidebar";
import { SidebarBudget } from "@/components/shared/layout/sidebar-budget";
import { UsageView } from "@/components/app/views/usage-view";
import { ProvidersView } from "@/components/app/views/providers-view";
import { ModelConfigView } from "@/components/app/views/model-config-view";
import { MessagingView } from "@/components/app/views/messaging-view";
import { Button } from "@/components/ui/shadcn/button";
import { Toaster } from "@/components/ui/shadcn/sonner";
import { TooltipProvider } from "@/components/ui/shadcn/tooltip";
import { useJson } from "@/hooks/use-json";
import type { DashboardPayload } from "@/api/types";

const VIEWS: Array<SidebarItem & { title: string; eyebrow: string }> = [
  { id: "providers", label: "Providers", icon: <BoxesGlyph />, title: "Providers", eyebrow: "Connections · Keys · Status" },
  { id: "model_config", label: "Model Config", icon: <SlidersGlyph />, title: "Model Config", eyebrow: "Combo Routes · Fallbacks" },
  { id: "messaging", label: "Messaging", icon: <MessageGlyph />, title: "Messaging", eyebrow: "Channels · Agents" },
  { id: "usage", label: "Usage", icon: <BarsGlyph />, title: "Usage", eyebrow: "Tokens · Cost · Activity" },
];

function BoxesGlyph() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" width={18} height={18} aria-hidden="true">
      <path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z" />
      <path d="m3.3 7 8.7 5 8.7-5" />
      <path d="M12 22V12" />
    </svg>
  );
}
function SlidersGlyph() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" width={18} height={18} aria-hidden="true">
      <line x1="4" x2="4" y1="21" y2="14" />
      <line x1="4" x2="4" y1="10" y2="3" />
      <line x1="12" x2="12" y1="21" y2="12" />
      <line x1="12" x2="12" y1="8" y2="3" />
      <line x1="20" x2="20" y1="21" y2="16" />
      <line x1="20" x2="20" y1="12" y2="3" />
      <line x1="2" x2="6" y1="14" y2="14" />
      <line x1="10" x2="14" y1="8" y2="8" />
      <line x1="18" x2="22" y1="16" y2="16" />
    </svg>
  );
}
function MessageGlyph() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" width={18} height={18} aria-hidden="true">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  );
}
function BarsGlyph() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" width={18} height={18} aria-hidden="true">
      <line x1="12" x2="12" y1="20" y2="10" />
      <line x1="18" x2="18" y1="20" y2="4" />
      <line x1="6" x2="6" y1="20" y2="16" />
    </svg>
  );
}

export function App() {
  const [activeId, setActiveId] = useState<string>("providers");
  const [dark, setDark] = useState<boolean>(() => {
    try {
      return document.documentElement.classList.contains("dark");
    } catch {
      return false;
    }
  });
  const dashboard = useJson<DashboardPayload>("/admin/api/dashboard");

  const navigate = useCallback((id: string) => {
    setActiveId(id);
    window.location.hash = id;
  }, []);

  React.useEffect(() => {
    const applyHash = () => {
      const id = window.location.hash.replace("#", "");
      if (VIEWS.some((view) => view.id === id)) setActiveId(id);
    };
    applyHash();
    window.addEventListener("hashchange", applyHash);
    return () => window.removeEventListener("hashchange", applyHash);
  }, []);

  const toggleTheme = useCallback(() => {
    setDark((prev) => {
      const next = !prev;
      document.documentElement.classList.toggle("dark", next);
      try {
        localStorage.setItem("claudey.theme", next ? "dark" : "light");
      } catch {
        /* session-only is fine */
      }
      return next;
    });
  }, []);

  const view = VIEWS.find((item) => item.id === activeId) ?? VIEWS[0];

  return (
    <TooltipProvider>
      <div className="flex h-screen w-full overflow-hidden bg-canvas text-ink">
        <Sidebar
          activeId={activeId}
          onNavigate={navigate}
          footer={
            <SidebarBudget
              monthlySpendUsd={dashboard.data?.monthly_spend_usd ?? 0}
              monthlyLimitUsd={dashboard.data?.monthly_limit_usd ?? 0}
              onStatClick={() => navigate("usage")}
            />
          }
        />

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-16 shrink-0 items-center justify-between border-b border-hairline bg-canvas/80 px-6 backdrop-blur-sm">
            <div>
              <p className="font-mono text-[11px] font-bold tracking-[0.08em] text-ink-muted-48 uppercase">
                {view.eyebrow}
              </p>
              <h2 className="text-[17px] leading-tight font-semibold tracking-[-0.374px] text-ink">
                {view.title}
              </h2>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="utility" size="sm" onClick={toggleTheme} aria-label="Toggle dark mode">
                {dark ? <Sun size={14} /> : <Moon size={14} />}
              </Button>
            </div>
          </header>

          <main className="min-h-0 flex-1 overflow-hidden">
            {activeId === "providers" && <ProvidersView />}
            {activeId === "model_config" && <ModelConfigView />}
            {activeId === "messaging" && <MessagingView />}
            {activeId === "usage" && <UsageView />}
          </main>
        </div>
      </div>

      <Toaster />
    </TooltipProvider>
  );
}
