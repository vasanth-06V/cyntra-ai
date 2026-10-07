"use client";

import { useEffect } from "react";

/**
 * Behaviour for the landing page: all of it is decoration or convenience, so the
 * page is complete without it. Nothing here touches React-managed state; it adds
 * classes, styles and listeners to the server-rendered markup and removes them
 * again when the page unmounts.
 */
export function LandingEffects() {
  useEffect(() => {
    const root = document.querySelector<HTMLElement>(".lp");
    if (!root) return;

    const cleanups: Array<() => void> = [];
    const q = <T extends Element>(sel: string) => root.querySelector<T>(sel);
    const qa = <T extends Element>(sel: string) => Array.from(root.querySelectorAll<T>(sel));
    const on = (
      target: EventTarget,
      type: string,
      fn: EventListenerOrEventListenerObject,
      opts?: AddEventListenerOptions
    ) => {
      target.addEventListener(type, fn, opts);
      cleanups.push(() => target.removeEventListener(type, fn, opts));
    };

    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    /* header gets a border once the page scrolls */
    const bar = q<HTMLElement>("#topbar");
    const onScroll = () => bar?.classList.toggle("scrolled", window.scrollY > 8);
    on(window, "scroll", onScroll, { passive: true });
    onScroll();
    cleanups.push(() => bar?.classList.remove("scrolled"));

    /* count-up for the hero facts: the final numbers are already in the markup */
    if (!reduce) {
      qa<HTMLElement>(".facts strong[data-to]").forEach((el, i) => {
        const to = Number(el.dataset.to);
        if (!to) return;
        let raf = 0;
        let start: number | null = null;
        const dur = 900 + i * 120;
        el.textContent = "0";
        const timer = window.setTimeout(() => {
          const step = (t: number) => {
            if (start === null) start = t;
            const p = Math.min(1, (t - start) / dur);
            el.textContent = String(Math.round(to * (1 - Math.pow(1 - p, 3))));
            if (p < 1) raf = requestAnimationFrame(step);
            else el.textContent = String(to);
          };
          raf = requestAnimationFrame(step);
        }, 500);
        cleanups.push(() => {
          window.clearTimeout(timer);
          cancelAnimationFrame(raf);
          el.textContent = String(to);
        });
      });
    }

    /* pointer glow on cards */
    qa<HTMLElement>(".glow").forEach((card) => {
      on(card, "pointermove", (e) => {
        const ev = e as PointerEvent;
        const r = card.getBoundingClientRect();
        card.style.setProperty("--mx", `${ev.clientX - r.left}px`);
        card.style.setProperty("--my", `${ev.clientY - r.top}px`);
      });
    });

    /* gentle tilt on the hero screens (fine pointers only) */
    const stack = q<HTMLElement>("#stack");
    const tilt = q<HTMLElement>("#tilt");
    if (stack && tilt && !reduce && window.matchMedia("(pointer: fine)").matches) {
      on(stack, "pointermove", (e) => {
        const ev = e as PointerEvent;
        const r = stack.getBoundingClientRect();
        const x = (ev.clientX - r.left) / r.width - 0.5;
        const y = (ev.clientY - r.top) / r.height - 0.5;
        tilt.style.transform = `rotateY(${(x * 6).toFixed(2)}deg) rotateX(${(-y * 5).toFixed(2)}deg)`;
      });
      on(stack, "pointerleave", () => {
        tilt.style.transform = "";
      });
      cleanups.push(() => {
        tilt.style.transform = "";
      });
    }

    if ("IntersectionObserver" in window) {
      /* active nav link while scrolling */
      const links = new Map<string, HTMLElement>();
      qa<HTMLAnchorElement>(".nav a").forEach((a) => links.set(a.getAttribute("href") ?? "", a));
      const navObserver = new IntersectionObserver(
        (entries) => {
          entries.forEach((en) => {
            if (!en.isIntersecting) return;
            links.forEach((el, href) => el.classList.toggle("on", href === `#${en.target.id}`));
          });
        },
        { rootMargin: "-45% 0px -50% 0px" }
      );
      ["products", "features", "how", "trust", "faq"].forEach((id) => {
        const s = q(`#${id}`);
        if (s) navObserver.observe(s);
      });
      cleanups.push(() => navObserver.disconnect());

      /* the score line draws when it comes into view */
      const hist = q<HTMLElement>("#hist");
      if (hist && !reduce) {
        const histObserver = new IntersectionObserver(
          (es) =>
            es.forEach((e) => {
              if (e.isIntersecting) {
                hist.classList.add("play");
                histObserver.disconnect();
              }
            }),
          { threshold: 0.4 }
        );
        histObserver.observe(hist);
        cleanups.push(() => {
          histObserver.disconnect();
          hist.classList.remove("play");
        });
      }

      /* sticky call to action once the hero is behind you (phones) */
      const hero = q<HTMLElement>("#hero");
      const sticky = q<HTMLElement>("#sticky");
      if (hero && sticky) {
        const stickyObserver = new IntersectionObserver(
          (es) => es.forEach((e) => sticky.classList.toggle("on", !e.isIntersecting)),
          { threshold: 0 }
        );
        stickyObserver.observe(hero);
        cleanups.push(() => {
          stickyObserver.disconnect();
          sticky.classList.remove("on");
        });
      }
    }

    /* product tabs: click, arrow keys, and a slow auto-advance that stops on the first touch */
    const tabs = qa<HTMLButtonElement>(".tab");
    const panels = tabs.map((t) => document.getElementById(t.getAttribute("aria-controls") ?? ""));
    let current = 0;
    let timer: number | undefined;
    let auto = !reduce;
    let hovering = false;

    const schedule = () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => {
        if (auto && !hovering && !document.hidden) select((current + 1) % tabs.length, false);
        else if (auto) schedule();
      }, 7000);
    };

    function select(i: number, byUser: boolean) {
      if (byUser) {
        auto = false;
        window.clearTimeout(timer);
      }
      current = i;
      tabs.forEach((t, k) => {
        const isOn = k === i;
        t.setAttribute("aria-selected", isOn ? "true" : "false");
        t.tabIndex = isOn ? 0 : -1;
        t.classList.remove("auto");
        const panel = panels[k];
        if (panel) {
          panel.hidden = !isOn;
          panel.classList.remove("show");
        }
      });
      void document.body.offsetWidth; // restart the panel animations
      panels[i]?.classList.add("show");
      if (auto) {
        void tabs[i].offsetWidth;
        tabs[i].classList.add("auto");
        schedule();
      }
    }

    tabs.forEach((t, i) => {
      on(t, "click", () => select(i, true));
      on(t, "keydown", (e) => {
        const k = (e as KeyboardEvent).key;
        let n: number | null = null;
        if (k === "ArrowRight") n = (i + 1) % tabs.length;
        else if (k === "ArrowLeft") n = (i - 1 + tabs.length) % tabs.length;
        else if (k === "Home") n = 0;
        else if (k === "End") n = tabs.length - 1;
        if (n !== null) {
          e.preventDefault();
          select(n, true);
          tabs[n].focus();
        }
      });
    });
    const stage = q<HTMLElement>(".stage");
    if (stage) {
      on(stage, "pointerenter", () => {
        hovering = true;
      });
      on(stage, "pointerleave", () => {
        hovering = false;
      });
    }
    if (tabs.length) select(0, false);
    cleanups.push(() => window.clearTimeout(timer));

    return () => cleanups.forEach((fn) => fn());
  }, []);

  return null;
}
