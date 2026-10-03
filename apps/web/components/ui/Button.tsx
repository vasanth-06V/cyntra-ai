"use client";

import { motion, type HTMLMotionProps } from "framer-motion";
import { forwardRef, type ReactNode } from "react";
import { buttonClasses, type ButtonSize, type ButtonVariant } from "./button-styles";
import { Spinner } from "./Spinner";

type ButtonProps = Omit<HTMLMotionProps<"button">, "children"> & {
  children?: ReactNode;
  variant?: ButtonVariant;
  size?: ButtonSize;
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
        className={buttonClasses(variant, size, className)}
        {...props}
      >
        {loading && <Spinner size={size === "sm" ? 13 : 15} />}
        {children}
      </motion.button>
    );
  }
);
Button.displayName = "Button";
