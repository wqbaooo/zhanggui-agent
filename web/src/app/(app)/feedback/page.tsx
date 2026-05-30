"use client";

import { useState } from "react";
import { FeedbackView } from "@/components/feedback/FeedbackView";
import { FeedbackModal } from "@/components/shared/FeedbackModal";
import type { FeedbackItem } from "@/domain/types";

export default function FeedbackPage() {
  const [fbList, setFbList] = useState<FeedbackItem[]>([]);
  const [fbOpen, setFbOpen] = useState(false);

  function addFeedback(fb: FeedbackItem) {
    setFbList((p) => [...p, fb]);
    setFbOpen(false);
  }

  return (
    <>
      <FeedbackView items={fbList} onOpen={() => setFbOpen(true)} />
      {fbOpen && <FeedbackModal onClose={() => setFbOpen(false)} onSubmit={addFeedback} />}
    </>
  );
}
