import { forwardRef, memo, type ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

type Variant = "primary" | "ghost" | "outline" | "ai" | "subtle";
type Size = "sm" | "md" | "icon";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

const variants: Record<Variant, string> = {
  primary:
    "bg-white/88 text-[#4766df] shadow-[0_0_24px_rgba(255,255,255,0.22),inset_0_1px_0_rgba(255,255,255,0.9)] hover:bg-white",
  ghost: "text-text-muted hover:bg-white/10 hover:text-white",
  outline: "glass-chip text-white hover:border-white/36 hover:bg-white/18",
  subtle: "glass-chip text-text-muted hover:text-white",
  ai: "border border-white/22 bg-white/13 text-white shadow-[0_0_22px_rgba(199,216,255,0.14)] hover:bg-white/20 hover:border-cyan-100/45",
};

const sizes: Record<Size, string> = {
  sm: "h-8 px-3 text-xs gap-1.5",
  md: "h-10 px-4 text-sm gap-2",
  icon: "size-8 p-0",
};

/**
 * Hover/active states are color-only CSS transitions (no layout, no JS) so they
 * register instantly. memo avoids re-rendering when parents update unrelated state.
 */
export const Button = memo(
  forwardRef<HTMLButtonElement, ButtonProps>(
    ({ className, variant = "outline", size = "md", ...props }, ref) => (
      <button
        ref={ref}
        className={cn(
          "inline-flex select-none items-center justify-center rounded-2xl font-semibold transition-[background-color,border-color,color,transform] duration-200 ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/35 active:translate-y-px disabled:pointer-events-none disabled:opacity-50",
          variants[variant],
          sizes[size],
          className
        )}
        {...props}
      />
    )
  )
);
Button.displayName = "Button";
