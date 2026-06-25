"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

interface Tab {
  key: string;
  label: string;
  icon?: React.ReactNode;
}

export function AnimatedTabs({
  tabs,
  activeTab,
  onTabChange,
  className,
}: {
  tabs: Tab[];
  activeTab: string;
  onTabChange: (key: string) => void;
  className?: string;
}) {
  return (
    <div className={cn("flex gap-1 relative", className)}>
      {tabs.map((tab) => {
        const isActive = activeTab === tab.key;
        return (
          <button
            key={tab.key}
            onClick={() => onTabChange(tab.key)}
            className={cn(
              "relative flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors",
              isActive
                ? "text-primary"
                : "text-on-surface-variant hover:text-on-background hover:bg-surface-container-high/40"
            )}
          >
            {tab.icon}
            <span>{tab.label}</span>
            {isActive && (
              <motion.div
                layoutId="activeTab"
                className="absolute inset-0 bg-primary/10 border border-primary/20 rounded-lg"
                style={{ zIndex: -1 }}
                transition={{
                  type: "spring",
                  stiffness: 500,
                  damping: 30,
                }}
              />
            )}
          </button>
        );
      })}
    </div>
  );
}

export function TabContent({
  activeTab,
  children,
}: {
  activeTab: string;
  children: Record<string, React.ReactNode>;
}) {
  return (
    <motion.div
      key={activeTab}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
    >
      {children[activeTab]}
    </motion.div>
  );
}