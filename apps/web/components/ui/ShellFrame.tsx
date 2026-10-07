"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type KeyboardEvent, type PointerEvent, type ReactNode } from "react";
import { Logo } from "./Logo";
import { NavLinks } from "./NavLinks";
import { CloseIcon, MenuIcon, SidebarIcon } from "./icons";

const MIN_WIDTH = 200;
const MAX_WIDTH = 360;
const DEFAULT_WIDTH = 240;
const COLLAPSED_WIDTH = 68;
const COLLAPSE_BELOW = 150; // dragging narrower than this collapses the sidebar
const STORAGE_KEY = "cyntra.sidebar";

type Item = { href: string; label: string };

const clamp = (n: number) => Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, Math.round(n)));

function readStored(): { width: number; collapsed: boolean } | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { width?: unknown; collapsed?: unknown };
    return {
      width: typeof parsed.width === "number" ? clamp(parsed.width) : DEFAULT_WIDTH,
      collapsed: parsed.collapsed === true,
    };
  } catch {
    return null;
  }
}

/**
 * The dashboard frame: a sidebar that can be dragged wider or narrower,
 * collapsed to icons, and (below md) turned into a slide-in drawer, plus the
 * column holding the header, page and footer. The choice is remembered per browser.
 */
export function ShellFrame({
  navItems,
  header,
  actions,
  banner,
  footer,
  children,
}: {
  navItems: Item[];
  header: ReactNode;
  actions: ReactNode;
  banner?: ReactNode;
  footer: ReactNode;
  children: ReactNode;
}) {
  const pathname = usePathname();
  const [width, setWidth] = useState(DEFAULT_WIDTH);
  const [collapsed, setCollapsed] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const drawerRef = useRef<HTMLElement>(null);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const loaded = useRef(false);

  // Restore the saved layout after mount (keeps server and first client render identical).
  useEffect(() => {
    const t = setTimeout(() => {
      const saved = readStored();
      if (saved) {
        setWidth(saved.width);
        setCollapsed(saved.collapsed);
      }
      loaded.current = true;
    }, 0);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    if (!loaded.current || dragging) return;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ width, collapsed }));
    } catch {
      /* storage unavailable: the layout just won't be remembered */
    }
  }, [width, collapsed, dragging]);

  // A route change closes the drawer.
  useEffect(() => {
    const t = setTimeout(() => setDrawerOpen(false), 0);
    return () => clearTimeout(t);
  }, [pathname]);

  // Drawer: Escape closes, the page behind doesn't scroll, focus moves in and back out.
  useEffect(() => {
    if (!drawerOpen) return;
    const button = menuButtonRef.current;
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key === "Escape") setDrawerOpen(false);
    };
    document.addEventListener("keydown", onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    drawerRef.current?.querySelector<HTMLElement>("a, button")?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
      button?.focus();
    };
  }, [drawerOpen]);

  const startDrag = useCallback(
    (e: PointerEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.currentTarget.setPointerCapture(e.pointerId);
      setDragging(true);
    },
    []
  );
  const onDrag = useCallback((e: PointerEvent<HTMLDivElement>) => {
    if (!e.currentTarget.hasPointerCapture(e.pointerId)) return;
    if (e.clientX < COLLAPSE_BELOW) {
      setCollapsed(true);
    } else {
      setCollapsed(false);
      setWidth(clamp(e.clientX));
    }
  }, []);
  const endDrag = useCallback((e: PointerEvent<HTMLDivElement>) => {
    if (e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId);
    setDragging(false);
  }, []);
  const onHandleKey = useCallback((e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
      e.preventDefault();
      const delta = e.key === "ArrowRight" ? 16 : -16;
      setCollapsed(false);
      setWidth((w) => clamp(w + delta));
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      setCollapsed((c) => !c);
    } else if (e.key === "Home") {
      e.preventDefault();
      setCollapsed(false);
      setWidth(DEFAULT_WIDTH);
    }
  }, []);

  const sidebarWidth = collapsed ? COLLAPSED_WIDTH : width;

  return (
    // --shell-offset: space the header, footer and page padding take, used by
    // the full-height chat and interview screens (.fill-screen).
    <div className="flex min-h-screen [--shell-offset:9.5rem]">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded-lg focus:bg-primary focus:px-3 focus:py-2 focus:text-primary-foreground"
      >
        Skip to content
      </a>

      {/* Desktop sidebar */}
      <aside
        style={{ width: sidebarWidth }}
        className={`sticky top-0 z-30 hidden h-screen shrink-0 flex-col border-r border-border bg-card/70 py-5 md:flex print:hidden ${
          dragging ? "" : "transition-[width] duration-200 ease-out motion-reduce:transition-none"
        } ${collapsed ? "px-3" : "px-4"}`}
      >
        <div className={`mb-7 flex items-center ${collapsed ? "justify-center" : "justify-between gap-2"}`}>
          <Link href="/dashboard" className="min-w-0 rounded-lg px-1.5" aria-label="CyntraAI dashboard">
            <Logo showWordmark={!collapsed} />
          </Link>
          {!collapsed && (
            <button
              type="button"
              onClick={() => setCollapsed(true)}
              aria-label="Collapse sidebar"
              title="Collapse sidebar"
              className="shrink-0 rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
            >
              <SidebarIcon size={18} />
            </button>
          )}
        </div>
        <nav aria-label="Main" className="flex flex-col gap-0.5">
          <NavLinks items={navItems} collapsed={collapsed} />
        </nav>
        {collapsed ? (
          <button
            type="button"
            onClick={() => setCollapsed(false)}
            aria-label="Expand sidebar"
            title="Expand sidebar"
            className="mx-auto mt-auto rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
          >
            <SidebarIcon size={18} />
          </button>
        ) : (
          <p className="mt-auto px-2 text-xs leading-5 text-muted-foreground">
            Practice makes calm.
            <br />
            Your keys, your data.
          </p>
        )}

        {/* Drag to resize; arrow keys, Enter and Home work too. */}
        <div
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize sidebar"
          aria-valuemin={MIN_WIDTH}
          aria-valuemax={MAX_WIDTH}
          aria-valuenow={sidebarWidth}
          tabIndex={0}
          onPointerDown={startDrag}
          onPointerMove={onDrag}
          onPointerUp={endDrag}
          onPointerCancel={endDrag}
          onKeyDown={onHandleKey}
          onDoubleClick={() => setCollapsed((c) => !c)}
          className="group absolute -right-1.5 top-0 z-10 h-full w-3 cursor-col-resize touch-none outline-none"
        >
          <span
            aria-hidden="true"
            className={`absolute left-1/2 top-0 h-full w-0.5 -translate-x-1/2 rounded-full transition-colors group-hover:bg-primary/50 group-focus-visible:bg-primary ${
              dragging ? "bg-primary" : "bg-transparent"
            }`}
          />
        </div>
      </aside>

      {/* Mobile drawer */}
      <div
        className={`fixed inset-0 z-40 md:hidden print:hidden ${drawerOpen ? "" : "pointer-events-none"}`}
        aria-hidden={drawerOpen ? undefined : true}
      >
        <button
          type="button"
          tabIndex={-1}
          aria-label="Close menu"
          onClick={() => setDrawerOpen(false)}
          className={`absolute inset-0 bg-black/40 backdrop-blur-[2px] transition-opacity duration-200 motion-reduce:transition-none ${
            drawerOpen ? "opacity-100" : "opacity-0"
          }`}
        />
        <aside
          ref={drawerRef}
          role="dialog"
          aria-modal="true"
          aria-label="Menu"
          className={`absolute inset-y-0 left-0 flex w-[min(18rem,85vw)] flex-col border-r border-border bg-card px-4 py-5 shadow-xl transition-transform duration-200 ease-out motion-reduce:transition-none ${
            drawerOpen ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          <div className="mb-6 flex items-center justify-between gap-2">
            <Link href="/dashboard" className="rounded-lg px-1.5" aria-label="CyntraAI dashboard">
              <Logo />
            </Link>
            <button
              type="button"
              onClick={() => setDrawerOpen(false)}
              aria-label="Close menu"
              className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
            >
              <CloseIcon size={20} />
            </button>
          </div>
          <nav aria-label="Main" className="flex flex-col gap-0.5 overflow-y-auto">
            <NavLinks items={navItems} onNavigate={() => setDrawerOpen(false)} />
          </nav>
          <p className="mt-auto px-2 pt-4 text-xs leading-5 text-muted-foreground">
            Practice makes calm.
            <br />
            Your keys, your data.
          </p>
        </aside>
      </div>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-14 items-center justify-between gap-3 border-b border-border bg-background/80 px-3 backdrop-blur-md sm:px-6 print:hidden">
          <div className="flex min-w-0 items-center gap-2">
            <button
              ref={menuButtonRef}
              type="button"
              onClick={() => setDrawerOpen(true)}
              aria-label="Open menu"
              aria-expanded={drawerOpen}
              className="shrink-0 rounded-lg p-2 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground md:hidden"
            >
              <MenuIcon size={20} />
            </button>
            {header}
          </div>
          <div className="flex shrink-0 items-center gap-1.5 sm:gap-2">{actions}</div>
        </header>
        {banner}
        <main id="main" className="mx-auto w-full max-w-[84rem] flex-1 p-3 sm:p-6">
          {children}
        </main>
        {footer}
      </div>
    </div>
  );
}
