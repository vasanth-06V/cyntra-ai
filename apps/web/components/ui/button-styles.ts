export type ButtonVariant = "primary" | "secondary" | "outline" | "ghost" | "danger";
export type ButtonSize = "sm" | "md" | "lg";

const variantClasses: Record<ButtonVariant, string> = {
  primary: "bg-primary text-primary-foreground shadow-sm hover:bg-primary-hover hover:shadow-md",
  secondary:
    "bg-secondary text-secondary-foreground border border-border hover:border-border-strong hover:bg-accent hover:text-accent-foreground",
  outline:
    "border border-border-strong bg-card text-foreground shadow-xs hover:bg-secondary hover:border-input",
  ghost: "bg-transparent text-foreground hover:bg-secondary",
  danger:
    "bg-destructive-soft text-destructive border border-destructive/30 hover:bg-destructive hover:text-destructive-foreground",
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: "h-8 gap-1.5 rounded-lg px-3 text-[13px]",
  md: "h-10 gap-2 rounded-lg px-4 text-sm",
  lg: "h-12 gap-2.5 rounded-xl px-6 text-[15px]",
};

/** Class string shared by <Button> and <LinkButton>, so a link can look like a button without nesting one in the other. */
export function buttonClasses(variant: ButtonVariant = "primary", size: ButtonSize = "md", extra = "") {
  return `inline-flex shrink-0 select-none items-center justify-center whitespace-nowrap font-medium tracking-[-0.005em] transition-[background-color,border-color,color,box-shadow] duration-150 cursor-pointer active:translate-y-px disabled:cursor-not-allowed disabled:opacity-55 disabled:shadow-none ${sizeClasses[size]} ${variantClasses[variant]} ${extra}`;
}
