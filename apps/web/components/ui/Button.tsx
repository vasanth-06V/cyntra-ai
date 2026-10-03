"use client";

import { motion, type HTMLMotionProps } from "framer-motion";
import { forwardRef, type ReactNode } from "react";
import { Spinner } from "./Spinner";

type Variant = "primary" | "secondary" | "outline" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

const variantClasses: Record<Variant, string> = {
  primary: "bg-primary text-primary-foreground shadow-sm hover:bg-primary-hover hover:shadow-md",
  secondary:
    "bg-secondary text-secondary-foreground border border-border hover:border-border-strong hover:bg-accent hover:text-accent-foreground",
  outline:
    "border border-border-strong bg-card text-foreground shadow-xs hover:bg-secondary hover:border-input",
  ghost: "bg-transparent text-foreground hover:bg-secondary",
  danger:
    "bg-destructive-soft text-destructive border border-destructive/30 hover:bg-destructive hover:text-destructive-foreground",
};

const sizeClasses: Record<Size, string> = {
  sm: "h-8 gap-1.5 rounded-lg px-3 text-[13px]",
  md: "h-10 gap-2 rounded-lg px-4 text-sm",
  lg: "h-12 gap-2.5 rounded-xl px-6 text-[15px]",
};

type ButtonProps = Omit<HTMLMotionProps<"button">, "children"> & {
  children?: ReactNode;
  variant?: Variant;
  size?: Size;
  /** Shows a spinner, sets aria-busy and blocks clicks. Keep the label as children. */
  loading?: boolean;
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    { variant = "primary", size = "md", loading = false, className = "", disabled, children, ...props },
    ref
  ) => {
    const inactive = disabled || loading;
    return (
      <motion.button
        ref={ref}
        whileTap={inactive ? undefined : { scale: 0.97 }}
        transition={{ type: "spring", stiffness: 520, damping: 32 }}
        disabled={inactive}
        aria-busy={loading || undefined}
        className={`inline-flex shrink-0 select-none items-center justify-center whitespace-nowrap font-medium tracking-[-0.005em] transition-[background-color,border-color,color,box-shadow] duration-150 cursor-pointer disabled:cursor-not-allowed disabled:opacity-55 disabled:shadow-none ${sizeClasses[size]} ${variantClasses[variant]} ${className}`}
        {...props}
      >
        {loading && <Spinner size={size === "sm" ? 13 : 15} />}
        {children}
      </motion.button>
    );
  }
);
Button.displayName = "Button";
