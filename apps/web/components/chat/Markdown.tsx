import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * Renders a model reply as formatted text. Raw HTML in the reply is not
 * rendered (react-markdown escapes it) and unsafe link schemes are dropped.
 */
const components: Components = {
  h1: (p) => <h3 className="mb-2 mt-4 text-base font-semibold tracking-tight first:mt-0" {...strip(p)} />,
  h2: (p) => <h3 className="mb-2 mt-4 text-base font-semibold tracking-tight first:mt-0" {...strip(p)} />,
  h3: (p) => <h4 className="mb-1.5 mt-4 text-[15px] font-semibold tracking-tight first:mt-0" {...strip(p)} />,
  h4: (p) => <h5 className="mb-1 mt-3 text-sm font-semibold first:mt-0" {...strip(p)} />,
  h5: (p) => <h5 className="mb-1 mt-3 text-sm font-semibold first:mt-0" {...strip(p)} />,
  h6: (p) => <h5 className="mb-1 mt-3 text-sm font-semibold first:mt-0" {...strip(p)} />,
  p: (p) => <p className="my-2 first:mt-0 last:mb-0" {...strip(p)} />,
  ul: (p) => <ul className="my-2 list-disc space-y-1 pl-5 marker:text-muted-foreground" {...strip(p)} />,
  ol: (p) => <ol className="my-2 list-decimal space-y-1 pl-5 marker:text-muted-foreground" {...strip(p)} />,
  li: (p) => <li className="pl-0.5" {...strip(p)} />,
  strong: (p) => <strong className="font-semibold text-foreground" {...strip(p)} />,
  hr: () => <hr className="my-4 border-border" />,
  blockquote: (p) => (
    <blockquote className="my-3 border-l-2 border-primary/40 pl-3 text-muted-foreground" {...strip(p)} />
  ),
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="font-medium text-primary underline underline-offset-2 hover:opacity-80"
    >
      {children}
    </a>
  ),
  pre: (p) => (
    <pre
      className="my-3 overflow-x-auto rounded-lg border border-border bg-secondary/70 p-3 text-[13px] leading-5 [&>code]:bg-transparent [&>code]:p-0"
      {...strip(p)}
    />
  ),
  code: ({ children, className }) => (
    <code className={`rounded bg-secondary px-1 py-0.5 font-mono text-[0.85em] ${className ?? ""}`}>{children}</code>
  ),
  table: (p) => (
    <div className="my-3 overflow-x-auto">
      <table className="w-full border-collapse text-left text-[13px]" {...strip(p)} />
    </div>
  ),
  th: (p) => <th className="border-b border-border-strong px-2.5 py-1.5 font-semibold" {...strip(p)} />,
  td: (p) => <td className="border-b border-border px-2.5 py-1.5" {...strip(p)} />,
};

/** Drops the `node` prop react-markdown passes, so it doesn't reach the DOM. */
function strip<T extends { node?: unknown }>(props: T): Omit<T, "node"> {
  const rest = { ...props };
  delete rest.node;
  return rest;
}

export function Markdown({ children }: { children: string }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
      {children}
    </ReactMarkdown>
  );
}
