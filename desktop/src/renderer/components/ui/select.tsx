"use client";

import { DirectionProvider } from "@base-ui/react/direction-provider";
import { Select as SelectPrimitive } from "@base-ui/react/select";
import type * as React from "react";
import { CheckIcon, ChevronDownIcon, ChevronUpIcon } from "lucide-react";

import { cn } from "@/lib/utils";

type SelectProps = SelectPrimitive.Root.Props<string> & {
  dir?: "ltr" | "rtl";
};

type SelectContentProps = SelectPrimitive.Popup.Props &
  Pick<
    SelectPrimitive.Positioner.Props,
    | "align"
    | "alignItemWithTrigger"
    | "alignOffset"
    | "anchor"
    | "arrowPadding"
    | "collisionAvoidance"
    | "collisionBoundary"
    | "collisionPadding"
    | "disableAnchorTracking"
    | "positionMethod"
    | "side"
    | "sideOffset"
    | "sticky"
  >;

function Select({ dir, ...props }: SelectProps) {
  const root = <SelectPrimitive.Root {...props} />;

  return dir === undefined ? root : <DirectionProvider direction={dir}>{root}</DirectionProvider>;
}

function SelectGroup({ className, ...props }: SelectPrimitive.Group.Props) {
  return (
    <SelectPrimitive.Group
      data-slot="select-group"
      {...props}
      className={(state) =>
        cn("scroll-my-1 p-1", typeof className === "function" ? className(state) : className)
      }
    />
  );
}

function SelectValue({ className, ...props }: SelectPrimitive.Value.Props) {
  return (
    <SelectPrimitive.Value
      data-slot="select-value"
      {...props}
      className={(state) =>
        cn("flex flex-1 text-left", typeof className === "function" ? className(state) : className)
      }
    />
  );
}

function SelectTrigger({
  className,
  size = "default",
  children,
  ...props
}: SelectPrimitive.Trigger.Props & {
  size?: "sm" | "default";
}) {
  return (
    <SelectPrimitive.Trigger
      data-slot="select-trigger"
      data-size={size}
      {...props}
      className={(state) =>
        cn(
          "flex h-10 w-full items-center justify-between gap-2 rounded-base border-2 border-border bg-main px-3 py-2 text-sm font-base text-main-foreground whitespace-nowrap outline-hidden transition-colors select-none placeholder:text-foreground/50 focus-visible:border-ring focus-visible:outline-hidden disabled:cursor-not-allowed disabled:opacity-50 data-placeholder:text-main-foreground/70 data-[size=sm]:h-9 *:data-[slot=select-value]:line-clamp-1 *:data-[slot=select-value]:flex *:data-[slot=select-value]:items-center *:data-[slot=select-value]:gap-2 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
          typeof className === "function" ? className(state) : className,
        )
      }
    >
      {children}
      <SelectPrimitive.Icon
        render={<ChevronDownIcon className="pointer-events-none size-4 opacity-70" />}
      />
    </SelectPrimitive.Trigger>
  );
}

function SelectContent({
  align = "start",
  alignItemWithTrigger = false,
  alignOffset = 0,
  anchor,
  arrowPadding = 0,
  children,
  className,
  collisionAvoidance,
  collisionBoundary,
  collisionPadding = 0,
  disableAnchorTracking,
  positionMethod,
  side = "bottom",
  sideOffset = 4,
  sticky,
  ...props
}: SelectContentProps) {
  return (
    <SelectPrimitive.Portal>
      <SelectPrimitive.Positioner
        anchor={anchor}
        arrowPadding={arrowPadding}
        side={side}
        sideOffset={sideOffset}
        align={align}
        alignOffset={alignOffset}
        alignItemWithTrigger={alignItemWithTrigger}
        collisionAvoidance={collisionAvoidance}
        collisionBoundary={collisionBoundary}
        collisionPadding={collisionPadding}
        disableAnchorTracking={disableAnchorTracking}
        positionMethod={positionMethod}
        sticky={sticky}
        className="isolate z-50"
      >
        <SelectPrimitive.Popup
          data-slot="select-content"
          data-align-trigger={alignItemWithTrigger}
          {...props}
          className={(state) =>
            cn(
              "relative isolate z-50 flex max-h-[min(24rem,var(--available-height))] w-[calc(var(--anchor-width)+4px)] min-w-[8rem] origin-(--transform-origin) flex-col overflow-hidden rounded-base border-2 border-border bg-main font-base text-main-foreground duration-100 data-[align-trigger=true]:animate-none data-[side=bottom]:slide-in-from-top-2 data-[side=inline-end]:slide-in-from-left-2 data-[side=inline-start]:slide-in-from-right-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2 data-[side=none]:max-h-96 data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95 data-closed:animate-out data-closed:fade-out-0 data-closed:zoom-out-95",
              typeof className === "function" ? className(state) : className,
            )
          }
        >
          <SelectScrollUpButton />
          <SelectPrimitive.List className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
            {children}
          </SelectPrimitive.List>
          <SelectScrollDownButton />
        </SelectPrimitive.Popup>
      </SelectPrimitive.Positioner>
    </SelectPrimitive.Portal>
  );
}

function SelectLabel({ className, ...props }: SelectPrimitive.GroupLabel.Props) {
  return (
    <SelectPrimitive.GroupLabel
      data-slot="select-label"
      {...props}
      className={(state) =>
        cn(
          "border-2 border-transparent py-1.5 pr-8 pl-2 text-sm font-base text-main-foreground/80",
          typeof className === "function" ? className(state) : className,
        )
      }
    />
  );
}

function SelectItem({ className, children, ...props }: SelectPrimitive.Item.Props) {
  return (
    <SelectPrimitive.Item
      data-slot="select-item"
      {...props}
      className={(state) =>
        cn(
          "relative flex w-full cursor-default items-center gap-2 rounded-base border-2 border-transparent py-1.5 pr-8 pl-2 text-sm font-base outline-hidden select-none data-highlighted:border-main-foreground data-disabled:pointer-events-none data-disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4 *:[span]:last:flex *:[span]:last:items-center *:[span]:last:gap-2",
          typeof className === "function" ? className(state) : className,
        )
      }
    >
      <SelectPrimitive.ItemText className="flex flex-1 shrink-0 gap-2 whitespace-nowrap">
        {children}
      </SelectPrimitive.ItemText>
      <SelectPrimitive.ItemIndicator
        render={
          <span className="pointer-events-none absolute right-2 flex size-4 items-center justify-center" />
        }
      >
        <CheckIcon className="pointer-events-none" />
      </SelectPrimitive.ItemIndicator>
    </SelectPrimitive.Item>
  );
}

function SelectSeparator({ className, ...props }: SelectPrimitive.Separator.Props) {
  return (
    <SelectPrimitive.Separator
      data-slot="select-separator"
      {...props}
      className={(state) =>
        cn(
          "pointer-events-none -mx-1 my-1 h-px bg-border",
          typeof className === "function" ? className(state) : className,
        )
      }
    />
  );
}

function SelectScrollUpButton({
  className,
  ...props
}: React.ComponentProps<typeof SelectPrimitive.ScrollUpArrow>) {
  return (
    <SelectPrimitive.ScrollUpArrow
      data-slot="select-scroll-up-button"
      {...props}
      className={(state) =>
        cn(
          "top-0 z-10 flex w-full cursor-default items-center justify-center bg-main py-1 [&_svg:not([class*='size-'])]:size-4",
          typeof className === "function" ? className(state) : className,
        )
      }
    >
      <ChevronUpIcon />
    </SelectPrimitive.ScrollUpArrow>
  );
}

function SelectScrollDownButton({
  className,
  ...props
}: React.ComponentProps<typeof SelectPrimitive.ScrollDownArrow>) {
  return (
    <SelectPrimitive.ScrollDownArrow
      data-slot="select-scroll-down-button"
      {...props}
      className={(state) =>
        cn(
          "bottom-0 z-10 flex w-full cursor-default items-center justify-center bg-main py-1 [&_svg:not([class*='size-'])]:size-4",
          typeof className === "function" ? className(state) : className,
        )
      }
    >
      <ChevronDownIcon />
    </SelectPrimitive.ScrollDownArrow>
  );
}

export {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectScrollDownButton,
  SelectScrollUpButton,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
};
