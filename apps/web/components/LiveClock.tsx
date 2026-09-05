"use client";

import { useEffect, useState } from "react";

export function LiveClock() {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <span className="font-mono text-[11px] tracking-[0.04em] text-faint">
      {now.toLocaleTimeString("en-GB", { hour12: false })}
    </span>
  );
}
