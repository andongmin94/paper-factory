"use client";

import { Progress as ProgressPrimitive } from "@base-ui/react/progress";

import { cn } from "@/lib/utils";

type ProgressProps = Omit<ProgressPrimitive.Root.Props, "value"> & {
  value?: number | null;
};

function Progress({ children, className, value = null, ...props }: ProgressProps) {
  return (
    <ProgressPrimitive.Root
      data-slot="progress"
      value={value}
      {...props}
      className={(state) =>
        cn(
          "flex w-full flex-wrap gap-3",
          typeof className === "function" ? className(state) : className,
        )
      }
    >
      {children}
      <ProgressTrack>
        <ProgressIndicator />
      </ProgressTrack>
    </ProgressPrimitive.Root>
  );
}

function ProgressTrack({ className, ...props }: ProgressPrimitive.Track.Props) {
  return (
    <ProgressPrimitive.Track
      data-slot="progress-track"
      {...props}
      className={(state) =>
        cn(
          "relative flex h-4 w-full items-center overflow-hidden rounded-base border-2 border-border bg-secondary-background",
          typeof className === "function" ? className(state) : className,
        )
      }
    />
  );
}

function ProgressIndicator({ className, ...props }: ProgressPrimitive.Indicator.Props) {
  return (
    <ProgressPrimitive.Indicator
      data-slot="progress-indicator"
      {...props}
      className={(state) =>
        cn(
          "h-full border-r-2 border-border bg-main transition-all",
          typeof className === "function" ? className(state) : className,
        )
      }
    />
  );
}

function ProgressLabel({ className, ...props }: ProgressPrimitive.Label.Props) {
  return (
    <ProgressPrimitive.Label
      data-slot="progress-label"
      {...props}
      className={(state) =>
        cn("text-sm font-heading", typeof className === "function" ? className(state) : className)
      }
    />
  );
}

function ProgressValue({ className, ...props }: ProgressPrimitive.Value.Props) {
  return (
    <ProgressPrimitive.Value
      data-slot="progress-value"
      {...props}
      className={(state) =>
        cn(
          "ml-auto text-sm font-base text-foreground tabular-nums",
          typeof className === "function" ? className(state) : className,
        )
      }
    />
  );
}

export { Progress, ProgressTrack, ProgressIndicator, ProgressLabel, ProgressValue };
