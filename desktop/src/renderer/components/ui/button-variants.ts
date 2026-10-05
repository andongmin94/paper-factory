import { cva } from "class-variance-authority";

const raisedPress =
  "shadow-shadow hover:not-data-disabled:translate-x-pressX hover:not-data-disabled:translate-y-pressY hover:not-data-disabled:shadow-press active:not-data-disabled:translate-x-boxShadowX active:not-data-disabled:translate-y-boxShadowY active:not-data-disabled:shadow-[0_0_0_0_var(--border)]";

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-base text-sm font-base transition-[translate,box-shadow,background-color,color] duration-[140ms] ease-[ease] motion-reduce:transition-none gap-2 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0 focus-visible:outline-hidden focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 data-disabled:pointer-events-none data-disabled:opacity-50",
  {
    variants: {
      variant: {
        default: `text-main-foreground bg-main border-2 border-border ${raisedPress}`,
        outline: `bg-background text-foreground border-2 border-border ${raisedPress}`,
        ghost:
          "border-2 border-transparent bg-transparent text-foreground hover:border-border hover:bg-main hover:text-main-foreground",
        destructive: `bg-destructive text-destructive-foreground border-2 border-border ${raisedPress}`,
        link: "text-foreground underline-offset-4 hover:underline",
        noShadow: "text-main-foreground bg-main border-2 border-border",
        neutral: `bg-secondary-background text-foreground border-2 border-border ${raisedPress}`,
        reverse:
          "text-main-foreground bg-main border-2 border-border hover:not-data-disabled:translate-x-reverseBoxShadowX hover:not-data-disabled:translate-y-reverseBoxShadowY hover:not-data-disabled:shadow-shadow active:not-data-disabled:translate-x-0 active:not-data-disabled:translate-y-0 active:not-data-disabled:shadow-[0_0_0_0_var(--border)]",
      },
      size: {
        default: "h-10 px-4 py-2",
        xs: "h-7 px-2 text-xs",
        sm: "h-9 px-3",
        lg: "h-11 px-8",
        icon: "size-10",
        "icon-xs": "size-7",
        "icon-sm": "size-9",
        "icon-lg": "size-11",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export { buttonVariants };
