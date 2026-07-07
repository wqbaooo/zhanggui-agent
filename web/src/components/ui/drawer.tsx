"use client";

import { AnimatePresence, motion } from "framer-motion";
import type { ReactNode } from "react";
import { X } from "lucide-react";

interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  children: ReactNode;
  maxWidth?: string;
}

export function Drawer({ open, onClose, title, subtitle, children, maxWidth = "max-w-md" }: DrawerProps) {
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-40 bg-stone-900/40 backdrop-blur-sm"
            onClick={onClose}
          />
          <motion.aside
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
            className={`fixed right-0 top-0 z-50 flex h-full w-full ${maxWidth} flex-col bg-stone-50 shadow-2xl`}
          >
            <div className="h-1 w-full bg-gradient-to-r from-octo-500 via-sauce-500 to-octo-500" />
            <header className="flex items-start justify-between border-b border-stone-200 px-5 py-4">
              <div className="min-w-0">
                <h2 className="text-lg font-semibold text-stone-900">{title}</h2>
                {subtitle && <p className="mt-0.5 text-sm text-stone-500">{subtitle}</p>}
              </div>
              <button
                onClick={onClose}
                className="shrink-0 rounded-lg p-1.5 text-stone-400 transition-colors hover:bg-stone-100 hover:text-stone-600"
                aria-label="关闭"
              >
                <X className="h-5 w-5" />
              </button>
            </header>
            <div className="flex-1 overflow-y-auto px-5 py-4">{children}</div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
